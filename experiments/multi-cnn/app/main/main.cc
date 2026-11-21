#include <algorithm>
#include <array>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <limits>
#include <vector>

#include "esp_heap_caps.h"
#include "esp_memory_utils.h"
#include "esp_psram.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "mean_bridge.h"
#include "tensorflow/lite/micro/kernels/kernel_util.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"

namespace {
struct ModelBlob {
    const char* name;
    const uint8_t* model;
    const uint8_t* model_end;
    const uint8_t* input;
    const uint8_t* input_end;
    const uint8_t* validation;
    const uint8_t* validation_end;
};
#include "suite_models.h"

constexpr int kWarmups = 5;
constexpr int kSamples = 30;
#ifndef CNN_ARENA_BYTES
#define CNN_ARENA_BYTES (2 * 1024 * 1024)
#endif
constexpr size_t kArenaBytes = CNN_ARENA_BYTES;

bool Failure(const char* why) {
    std::printf("CNN_MODEL_ERROR reason=%s\n", why);
    return false;
}

// The supplied Dense lowering uses two INT32 shape-vector products.
TfLiteStatus ShapeProduct(TfLiteContext* context, TfLiteNode* node) {
    using namespace tflite::micro;
    TF_LITE_ENSURE_EQ(context, NumInputs(node), 2);
    TF_LITE_ENSURE_EQ(context, NumOutputs(node), 1);
    auto* input = GetEvalInput(context, node, 0);
    auto* axis = GetEvalInput(context, node, 1);
    auto* output = GetEvalOutput(context, node, 0);
    TF_LITE_ENSURE(context, input->type == kTfLiteInt32 && axis->type == kTfLiteInt32 &&
                            output->type == kTfLiteInt32 && input->dims->size == 1 &&
                            axis->dims->size == 1 && axis->dims->data[0] == 1 &&
                            output->dims->size == 0 && axis->data.i32[0] == 0);
    int32_t product = 1;
    for (int i = 0; i < input->dims->data[0]; ++i) {
        const int32_t dimension = input->data.i32[i];
        TF_LITE_ENSURE(context, dimension >= 0);
        const int64_t next = static_cast<int64_t>(product) * dimension;
        TF_LITE_ENSURE(context, next <= std::numeric_limits<int32_t>::max());
        product = static_cast<int32_t>(next);
    }
    output->data.i32[0] = product;
    return kTfLiteOk;
}

// Preserve upstream GATHER for data tensors. This adds INT32 shape vectors.
TfLiteStatus PrepareShapeGather(TfLiteContext* context, TfLiteNode* node) {
    using namespace tflite::micro;
    const auto* in = GetEvalInput(context, node, 0);
    if (in->type != kTfLiteInt32) return Register_GATHER().prepare(context, node);
    TF_LITE_ENSURE_EQ(context, NumInputs(node), 2);
    TF_LITE_ENSURE_EQ(context, NumOutputs(node), 1);
    const auto* index = GetEvalInput(context, node, 1);
    const auto* out = GetEvalOutput(context, node, 0);
    const auto* p = static_cast<const TfLiteGatherParams*>(node->builtin_data);
    TF_LITE_ENSURE(context, p && (p->axis == 0 || p->axis == -1) && p->batch_dims == 0);
    TF_LITE_ENSURE(context, in->dims->size == 1 && index->type == kTfLiteInt32 &&
                            out->type == kTfLiteInt32 && index->dims->size == 1 &&
                            out->dims->size == 1 && out->dims->data[0] == index->dims->data[0]);
    return kTfLiteOk;
}

TfLiteStatus EvalShapeGather(TfLiteContext* context, TfLiteNode* node) {
    using namespace tflite::micro;
    const auto* in = GetEvalInput(context, node, 0);
    if (in->type != kTfLiteInt32) return Register_GATHER().invoke(context, node);
    const auto* index = GetEvalInput(context, node, 1);
    auto* out = GetEvalOutput(context, node, 0);
    for (int i = 0; i < index->dims->data[0]; ++i) {
        const int value = index->data.i32[i];
        TF_LITE_ENSURE(context, value >= 0 && value < in->dims->data[0]);
        out->data.i32[i] = in->data.i32[value];
    }
    return kTfLiteOk;
}

class Resolver : public tflite::MicroMutableOpResolver<36> {
    using Base = tflite::MicroMutableOpResolver<36>;

public:
    using Base::FindOp;

    const TFLMRegistration* FindOp(tflite::BuiltinOperator op) const override {
        return op == tflite::BuiltinOperator_REDUCE_PROD ? &shape_product_ : Base::FindOp(op);
    }

    tflite::TfLiteBridgeBuiltinParseFunction GetOpDataParser(
        tflite::BuiltinOperator op) const override {
        return op == tflite::BuiltinOperator_REDUCE_PROD
                   ? tflite::ParseReducer : Base::GetOpDataParser(op);
    }

private:
    const TFLMRegistration shape_product_ = [] {
        auto registration = tflite::micro::RegisterOp(nullptr, nullptr, ShapeProduct);
        registration.builtin_code = tflite::BuiltinOperator_REDUCE_PROD;
        return registration;
    }();
};

bool RegisterOps(Resolver& r) {
    const TfLiteStatus registrations[] = {
        r.AddConv2D(), r.AddDepthwiseConv2D(), r.AddMaxPool2D(), r.AddAveragePool2D(),
        r.AddMean(RegisterEspNnGlobalMean()), r.AddFullyConnected(), r.AddReshape(),
        r.AddAdd(), r.AddMul(), r.AddSoftmax(), r.AddPad(), r.AddQuantize(),
        r.AddDequantize(), r.AddLogistic(), r.AddRelu(), r.AddRelu6(), r.AddHardSwish(),
        r.AddConcatenation(), r.AddSqueeze(), r.AddTranspose(), r.AddSub(), r.AddShape(),
        r.AddRsqrt(), r.AddPack(), r.AddStridedSlice(), r.AddPadV2(), r.AddResizeBilinear(),
        r.AddSplit(), r.AddMinimum(), r.AddMaximum(),
        r.AddGather(tflite::micro::RegisterOp(nullptr, PrepareShapeGather, EvalShapeGather)), r.AddSum(),
    };
    return std::all_of(std::begin(registrations), std::end(registrations),
                       [](TfLiteStatus status) { return status == kTfLiteOk; });
}

// Each recorded sample uses the kit's Invoke-only timer boundary. Serial output,
// output comparisons and input setup stay outside it.
bool Run(const ModelBlob& blob, const Resolver& resolver) {
    const auto* model = tflite::GetModel(blob.model);
    if (model->version() != TFLITE_SCHEMA_VERSION) return Failure("schema");
    const auto* graph = model->subgraphs()->Get(0);
    if (graph->inputs()->size() != 1 || graph->outputs()->size() != 1)
        return Failure("requires_single_input_and_output");
    std::unique_ptr<uint8_t, decltype(&std::free)> arena(
        static_cast<uint8_t*>(heap_caps_aligned_alloc(
            16, kArenaBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)), &std::free);
    if (!arena || !esp_ptr_external_ram(arena.get())) return Failure("psram_arena");
    tflite::MicroInterpreter interpreter(model, resolver, arena.get(), kArenaBytes);
    if (interpreter.AllocateTensors() != kTfLiteOk) return Failure("allocate_tensors");
    auto* in = interpreter.input(0);
    auto* out = interpreter.output(0);
    if (!in || !out) return Failure("input_output");
    if ((in->type != kTfLiteInt8 && in->type != kTfLiteUInt8) ||
        (out->type != kTfLiteInt8 && out->type != kTfLiteUInt8))
        return Failure("input_or_output_not_8bit");
    if (in->bytes != static_cast<size_t>(blob.input_end - blob.input))
        return Failure("input_size");
    std::memcpy(in->data.raw, blob.input, in->bytes);
    std::printf("CNN_START cpu_mhz=%d model_bytes=%u input_bytes=%u output_bytes=%u "
                "arena=psram arena_cap=%u arena_used=%u in_type=%d out_type=%d\n",
                CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, unsigned(blob.model_end - blob.model),
                unsigned(in->bytes), unsigned(out->bytes), unsigned(kArenaBytes),
                unsigned(interpreter.arena_used_bytes()), in->type, out->type);

#ifndef CNN_DIAGNOSTIC
    const bool large = blob.model_end - blob.model > 1024 * 1024;
    // The arena planner may reuse the graph input once its final consumer runs.
    for (int i = 0; i < kWarmups; ++i) {
        std::memcpy(in->data.raw, blob.input, in->bytes);
        if (interpreter.Invoke() != kTfLiteOk) return Failure("warmup");
        if (large) vTaskDelay(1);
    }
    std::array<int64_t, kSamples> times{};
    std::vector<uint8_t> reference(out->bytes);
    bool stable = true;
    for (int i = 0; i < kSamples; ++i) {
        std::memcpy(in->data.raw, blob.input, in->bytes);
        const int64_t start = esp_timer_get_time();
        const TfLiteStatus status = interpreter.Invoke();
        times[i] = esp_timer_get_time() - start;
        if (status != kTfLiteOk) return Failure("timed_invoke");
        if (large) vTaskDelay(1);
        if (i == 0) std::memcpy(reference.data(), out->data.raw, out->bytes);
        else if (std::memcmp(reference.data(), out->data.raw, out->bytes)) stable = false;
    }
    for (int i = 0; i < kSamples; ++i)
        std::printf("CNN_RUN index=%d us=%" PRId64 "\n", i, times[i]);
    uint32_t checksum = 2166136261u;
    for (auto byte : reference) checksum = (checksum ^ byte) * 16777619u;
    std::printf("CNN_OUTPUT bytes=%u hash_fnv1a=%08" PRIx32 " stable=%d hex=",
                unsigned(reference.size()), checksum, int(stable));
    for (auto byte : reference) std::printf("%02x", byte);
    std::putchar('\n');
    if (blob.validation) {
        const size_t bytes = blob.validation_end - blob.validation;
        if (bytes % in->bytes) return Failure("validation_input_size");
        for (size_t offset = 0; offset < bytes; offset += in->bytes) {
            std::memcpy(in->data.raw, blob.validation + offset, in->bytes);
            if (interpreter.Invoke() != kTfLiteOk) return Failure("validation_invoke");
            std::printf("CNN_VALIDATION index=%u hex=", unsigned(offset / in->bytes + 1));
            for (size_t i = 0; i < out->bytes; ++i)
                std::printf("%02x", static_cast<unsigned char>(out->data.raw[i]));
            std::putchar('\n');
        }
    }
    return stable;
#else
    return interpreter.Invoke() == kTfLiteOk || Failure("diagnostic_invoke");
#endif
}
}  // namespace

#ifdef CNN_DIAGNOSTIC
void ProbeReset();
void ProbeReport();
#endif

extern "C" void app_main() {
    std::printf("CNN_SUITE_BEGIN cpu_mhz=%d cores=%d psram_bytes=%u mode=%s\n",
                CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, CONFIG_FREERTOS_NUMBER_OF_CORES,
                unsigned(esp_psram_get_size()),
#ifdef CNN_DIAGNOSTIC
                "diagnostic"
#else
                "timed"
#endif
    );
    Resolver resolver;
    if (!RegisterOps(resolver)) {
        std::puts("CNN_FATAL resolver");
        return;
    }
    for (const auto& model : kModels) {
        std::printf("CNN_MODEL_BEGIN name=%s\n", model.name);
#ifdef CNN_DIAGNOSTIC
        ProbeReset();
#endif
        const bool ok = Run(model, resolver);
#ifdef CNN_DIAGNOSTIC
        ProbeReport();
#endif
        std::printf("CNN_MODEL_DONE name=%s ok=%d\n", model.name, int(ok));
    }
    std::puts("CNN_SUITE_DONE");
    std::fflush(stdout);
}
