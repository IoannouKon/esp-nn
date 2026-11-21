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

#if defined(CNN_DISPATCH_PROBE) || defined(CNN_MEAN_STRESS_ONLY)
#include <cstdio>
#include <cstring>
#include <vector>
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "tensorflow/lite/micro/kernels/internal/quantization_util.h"
#include "tensorflow/lite/micro/kernels/internal/reference/reduce.h"
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

bool ScaleForArea(int area, int32_t multiplier, int shift, MeanData& data) {
    if (area < 1 || area > 4095 || multiplier <= 0 || shift < -30 || shift > 30)
        return false;
    int log_area = 0;
    for (int n = area; n > 1; n >>= 1) ++log_area;
    // Match TFLM's integer division of its already quantized scale.
    const int extra = std::min(log_area, 31 + shift);
    const int effective_shift = shift - extra;
    if (effective_shift < -30 || effective_shift > 0) return false;
    data.shift = effective_shift;
    data.multiplier = static_cast<int>((static_cast<int64_t>(multiplier) << extra) / area);
    return true;
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
            ScaleForArea(static_cast<int>(area), data->reference.multiplier,
                         data->reference.shift, *data)) {
            data->h = x[1];
            data->w = x[2];
            data->channels = x[3];
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

#ifdef CNN_DISPATCH_PROBE
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
#if defined(CNN_DISPATCH_PROBE) || defined(CNN_MEAN_STRESS_ONLY)
        std::puts("CNN_MEAN route=tflm_reference");
#endif
        return RunOriginal(context, node, data);
    }
#ifdef CNN_DISPATCH_PROBE
    TF_LITE_ENSURE_OK(context, Verify(context, node, data, in->data.int8, out->data.int8));
#endif
    RunEspNn(in->data.int8, out->data.int8, data);
    return kTfLiteOk;
}
}  // namespace

TFLMRegistration RegisterEspNnGlobalMean() {
    return RegisterOp(Init, Prepare, Eval);
}


#ifdef CNN_MEAN_STRESS_ONLY
bool ValidateEspNnGlobalMean() {
    // The same ScaleForArea/RunEspNn functions are used by the registered adapter.
    const int shapes[][3] = {{1,1,1}, {1,1,16}, {1,7,4}, {3,3,16}, {7,9,17},
                             {8,8,32}, {16,16,32}, {11,13,64}, {31,31,16}, {63,65,16}};
    const double ratios[] = {0x1p-20, 0x1p-12, 0.015625, 0.03125, 0.1, 0.5,
                             0.9375, 1.0, 1.125, 3.14159, 7.5, 15.999};
    const int points[] = {-128, -127, -73, -1, 0, 1, 57, 126, 127};
    unsigned tested = 0, rejected = 0, compared = 0, mismatches = 0;
    uint32_t rng = 0x271981e3u;
    const int axes[2] = {1, 2};
    for (const auto& shape : shapes) {
        const int area = shape[0] * shape[1];
        const int channels = shape[2];
        const int size = area * channels;
        auto* input = static_cast<int8_t*>(heap_caps_aligned_alloc(
            16, (size + 15) & ~15u, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
        if (!input) return false;
        unsigned shape_tested = 0;
        alignas(16) int8_t candidate[64];
        alignas(16) int8_t expected[64];
        int32_t sums[64];
        MeanData range{};
        range.h = shape[0]; range.w = shape[1]; range.channels = channels;
        if (BuffersEligible(input, input, range) ||
            BuffersEligible(input + 1, candidate, range) ||
            BuffersEligible(input, candidate + 1, range)) {
            heap_caps_free(input);
            return false;
        }
        const int dims[4] = {1, shape[0], shape[1], channels};
        const int out_dims[4] = {1, 1, 1, channels};
        for (int trial = 0; trial < 864; ++trial) {
            MeanData d{};
            d.h = shape[0]; d.w = shape[1]; d.channels = channels;
            d.reference.input_zp = points[(trial / 12) % 9];
            d.reference.output_zp = points[(trial / 108 + trial % 12) % 9];
            int32_t multiplier;
            int shift;
            tflite::micro::QuantizeMultiplier(ratios[trial % 12], &multiplier, &shift);
            if (!ScaleForArea(area, multiplier, shift, d)) { ++rejected; continue; }
            for (int i = 0; i < size; ++i) {
                rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
                switch ((trial / 12) % 8) {
                    case 0: input[i] = -128; break;
                    case 1: input[i] = 127; break;
                    case 2: input[i] = d.reference.input_zp; break;
                    case 3: input[i] = (i / channels) % 2 ? -128 : 127; break;
                    case 4: input[i] = i % 2 ? -127 : 126; break;
                    case 5: input[i] = static_cast<int>((i + trial) % 256) - 128; break;
                    case 6: input[i] = static_cast<int>((trial * 47u) % 256) - 128; break;
                    default: input[i] = static_cast<int>(rng & 255u) - 128; break;
                }
            }
            int index[4], resolved[2];
            bool ok = tflite::micro::reference_ops::QuantizedMeanOrSum(
                input, d.reference.input_zp, dims, 4, expected, multiplier, shift,
                d.reference.output_zp, out_dims, 4, axes, 2, true, index, resolved, sums, false);
            if (!ok || !BuffersEligible(input, candidate, d)) {
                heap_caps_free(input);
                return false;
            }
            RunEspNn(input, candidate, d);
            for (int i = 0; i < channels; ++i) mismatches += expected[i] != candidate[i];
            ++tested; ++shape_tested;
            compared += channels;
            if ((tested & 15u) == 0) vTaskDelay(1);
        }
        heap_caps_free(input);
        std::printf("MEAN_STRESS_SHAPE h=%d w=%d channels=%d tested=%u mismatches_cumulative=%u\n",
                    shape[0], shape[1], channels, shape_tested, mismatches);
    }
    std::printf("MEAN_STRESS_DONE tested=%u guard_rejected=%u compared=%u mismatches=%u\n",
                tested, rejected, compared, mismatches);
    return tested >= 2000 && mismatches == 0;
}
#endif
