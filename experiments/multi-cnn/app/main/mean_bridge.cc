#include "mean_bridge.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <new>

#include "esp_nn.h"
#include "tensorflow/lite/micro/kernels/kernel_util.h"
#include "tensorflow/lite/micro/kernels/reduce.h"
#include "tensorflow/lite/micro/micro_context.h"

#ifdef CNN_DIAGNOSTIC
#include <cstdio>
#include <cstring>
#include <vector>
#endif

namespace {
using namespace tflite::micro;

struct MeanData {
    OpDataReduce reference{};
    int h = 0;
    int w = 0;
    int channels = 0;
    int multiplier = 0;
    int shift = 0;
};

void* Init(TfLiteContext* context, const char*, size_t) {
    void* storage = context->AllocatePersistentBuffer(context, sizeof(MeanData));
    return storage ? new (storage) MeanData() : nullptr;
}

bool PerTensorInt8(const TfLiteTensor* tensor) {
    if (!tensor || tensor->type != kTfLiteInt8 ||
        tensor->quantization.type != kTfLiteAffineQuantization) return false;
    auto* affine = static_cast<const TfLiteAffineQuantization*>(tensor->quantization.params);
    return affine && affine->scale && affine->scale->size == 1 &&
           affine->zero_point && affine->zero_point->size == 1 &&
           std::isfinite(tensor->params.scale) && tensor->params.scale > 0 &&
           tensor->params.scale == affine->scale->data[0] &&
           tensor->params.zero_point == affine->zero_point->data[0] &&
           tensor->params.zero_point >= -128 && tensor->params.zero_point <= 127;
}

bool SpatialAxes(const TfLiteEvalTensor* axis) {
    if (axis->type != kTfLiteInt32 || axis->dims->size != 1 ||
        axis->dims->data[0] != 2 || !axis->data.i32) return false;
    const int32_t* a = axis->data.i32;
    return (a[0] == 1 && a[1] == 2) || (a[0] == 2 && a[1] == 1);
}

TfLiteStatus Prepare(TfLiteContext* context, TfLiteNode* node) {
    auto* data = static_cast<MeanData*>(node->user_data);
    TF_LITE_ENSURE(context, data != nullptr);
    TF_LITE_ENSURE_OK(context, PrepareMeanOrSumHelper(context, node, &data->reference));
#if defined(TFLITE_SINGLE_ROUNDING) && TFLITE_SINGLE_ROUNDING
    return kTfLiteOk;
#endif
    auto* micro = GetMicroContext(context);
    TfLiteTensor* in = micro->AllocateTempInputTensor(node, 0);
    TfLiteTensor* out = micro->AllocateTempOutputTensor(node, 0);
    if (PerTensorInt8(in) && PerTensorInt8(out) && in->dims->size == 4 &&
        out->dims->size == 4 &&
        static_cast<const TfLiteReducerParams*>(node->builtin_data)->keep_dims) {
        const int* x = in->dims->data;
        const int* y = out->dims->data;
        const int64_t area = static_cast<int64_t>(x[1]) * x[2];
        if (x[0] == 1 && x[1] > 0 && x[2] > 0 && area <= 4095 &&
            x[3] > 0 && area * x[3] <= std::numeric_limits<int32_t>::max() &&
            y[0] == 1 && y[1] == 1 && y[2] == 1 && y[3] == x[3] &&
            data->reference.multiplier > 0 && data->reference.shift >= -30 &&
            data->reference.shift <= 30) {
            int log_area = 0;
            for (int n = static_cast<int>(area); n > 1; n >>= 1) ++log_area;
            // Mirror QuantizedMeanOrSum's integer division of its prequantized scale.
            const int extra = std::min(log_area, 31 + data->reference.shift);
            const int shift = data->reference.shift - extra;
            if (shift >= -30 && shift <= 0) {
                data->h = x[1];
                data->w = x[2];
                data->channels = x[3];
                data->shift = shift;
                data->multiplier = static_cast<int>(
                    (static_cast<int64_t>(data->reference.multiplier) << extra) / area);
            }
        }
    }
    if (out) micro->DeallocateTempTfLiteTensor(out);
    if (in) micro->DeallocateTempTfLiteTensor(in);
    return kTfLiteOk;
}

bool BuffersEligible(const int8_t* input, const int8_t* output, const MeanData& data) {
    const uintptr_t in = reinterpret_cast<uintptr_t>(input);
    const uintptr_t out = reinterpret_cast<uintptr_t>(output);
    if (!in || !out || ((in | out) & 15u)) return false;
    const size_t channels = data.channels;
    const size_t input_bytes = static_cast<size_t>(data.h) * data.w * channels;
    return out < in ? in - out >= channels : out - in >= input_bytes;
}

TfLiteStatus RunOriginal(TfLiteContext* context, TfLiteNode* node, MeanData& data) {
    // The upstream registration expects exactly its own operation state.
    static const auto original = tflite::Register_MEAN();
    void* state = node->user_data;
    node->user_data = &data.reference;
    const auto status = original.invoke(context, node);
    node->user_data = state;
    return status;
}

void RunEspNn(const int8_t* input, int8_t* output, const MeanData& data) {
    esp_nn_mean_nhwc_s8(input, output, data.h, data.w, data.channels,
                       data.reference.input_zp, data.reference.output_zp,
                       data.multiplier, data.shift);
}

#ifdef CNN_DIAGNOSTIC
TfLiteStatus Verify(TfLiteContext* context, TfLiteNode* node, MeanData& data,
                    int8_t* input, int8_t* output) {
    const size_t bytes = static_cast<size_t>(data.h) * data.w * data.channels;
    const std::vector<int8_t> original(input, input + bytes);
    std::vector<int8_t> expected(data.channels);
    constexpr int kTests = 6;
    unsigned mismatches = 0;
    for (int trial = 0; trial < kTests; ++trial) {
        for (size_t i = 0; trial != 0 && i < bytes; ++i) {
            switch (trial) {
                case 1: input[i] = -128; break;
                case 2: input[i] = 127; break;
                case 3: input[i] = data.reference.input_zp; break;
                case 4: input[i] = i / data.channels % 2 ? 127 : -128; break;
                case 5: input[i] = static_cast<int>((i * 127 + i / 11) % 256) - 128; break;
            }
        }
        const auto status = EvalMeanHelper(context, node, &data.reference);
        if (status != kTfLiteOk) {
            std::memcpy(input, original.data(), bytes);
            return status;
        }
        std::memcpy(expected.data(), output, expected.size());
        const auto original_status = RunOriginal(context, node, data);
        if (original_status != kTfLiteOk) {
            std::memcpy(input, original.data(), bytes);
            return original_status;
        }
        for (int i = 0; i < data.channels; ++i) mismatches += output[i] != expected[i];
        RunEspNn(input, output, data);
        for (int i = 0; i < data.channels; ++i) mismatches += output[i] != expected[i];
    }
    std::memcpy(input, original.data(), bytes);
    std::printf("CNN_MEAN route=esp_nn shape=%dx%dx%d input=%p output=%p "
                "zp_in=%d zp_out=%d multiplier=%d shift=%d trials=%d compared=%u mismatches=%u\n",
                data.h, data.w, data.channels, input, output, data.reference.input_zp,
                data.reference.output_zp, data.multiplier, data.shift, kTests,
                unsigned(2 * kTests * data.channels), mismatches);
    return mismatches ? kTfLiteError : kTfLiteOk;
}
#endif

TfLiteStatus Eval(TfLiteContext* context, TfLiteNode* node) {
    auto& data = *static_cast<MeanData*>(node->user_data);
    const auto* in = GetEvalInput(context, node, 0);
    auto* out = GetEvalOutput(context, node, 0);
    if (!data.channels || !SpatialAxes(GetEvalInput(context, node, 1)) ||
        !BuffersEligible(in->data.int8, out->data.int8, data)) {
#ifdef CNN_DIAGNOSTIC
        std::puts("CNN_MEAN route=tflm_reference");
#endif
        return RunOriginal(context, node, data);
    }
#ifdef CNN_DIAGNOSTIC
    TF_LITE_ENSURE_OK(context, Verify(context, node, data, in->data.int8, out->data.int8));
#endif
    RunEspNn(in->data.int8, out->data.int8, data);
    return kTfLiteOk;
}
}  // namespace

TFLMRegistration RegisterEspNnGlobalMean() {
    return RegisterOp(Init, Prepare, Eval);
}
