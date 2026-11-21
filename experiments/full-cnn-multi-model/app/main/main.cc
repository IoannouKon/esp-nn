// Multi-CNN portable ESP-TFLM runner. Does NOT claim built-in MEAN is ESP-NN.
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "esp_heap_caps.h"
#include "esp_timer.h"
#ifdef CNN_WATCHDOG_MS
#include "esp_task_wdt.h"
#endif
#include "esp_cpu.h"
#include "esp_memory_utils.h"
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"

extern const uint8_t model_start[] asm("_binary_model_tflite_start");
extern const uint8_t model_end[] asm("_binary_model_tflite_end");
extern const uint8_t input_start[] asm("_binary_input_bin_start");
extern const uint8_t input_end[] asm("_binary_input_bin_end");

#ifndef CNN_WARMUP
#define CNN_WARMUP 5
#endif
#ifndef CNN_SAMPLES
#define CNN_SAMPLES 30
#endif
#ifndef CNN_ARENA_BYTES
#define CNN_ARENA_BYTES (2 * 1024 * 1024)
#endif

static void check(bool ok, const char *why) {
    if (!ok) { std::printf("CNN_ERROR %s\n", why); std::abort(); }
}

#ifdef CNN_DISPATCH_PROBE
void ProbeReset();
void ProbeReport();
#endif

extern "C" void app_main(void) {
#ifdef CNN_WATCHDOG_MS
    const esp_task_wdt_config_t watchdog{
        .timeout_ms = CNN_WATCHDOG_MS, .idle_core_mask = 1, .trigger_panic = false};
    check(esp_task_wdt_reconfigure(&watchdog) == ESP_OK, "task watchdog configuration");
    std::printf("CNN_WATCHDOG timeout_ms=%u\n", unsigned(CNN_WATCHDOG_MS));
#endif
    auto *model = tflite::GetModel(model_start);
    check(model->version() == TFLITE_SCHEMA_VERSION, "schema");
    tflite::MicroMutableOpResolver<32> resolver;
    check(resolver.AddConv2D() == kTfLiteOk, "conv");
    check(resolver.AddDepthwiseConv2D() == kTfLiteOk, "depthwise");
    check(resolver.AddMaxPool2D() == kTfLiteOk, "maxpool");
    check(resolver.AddAveragePool2D() == kTfLiteOk, "avgpool");
    check(resolver.AddMean() == kTfLiteOk, "mean");
    check(resolver.AddFullyConnected() == kTfLiteOk, "fc");
    check(resolver.AddReshape() == kTfLiteOk, "reshape");
    check(resolver.AddAdd() == kTfLiteOk, "add");
    check(resolver.AddMul() == kTfLiteOk, "mul");
    check(resolver.AddSoftmax() == kTfLiteOk, "softmax");
    check(resolver.AddPad() == kTfLiteOk, "pad");
    check(resolver.AddQuantize() == kTfLiteOk, "quantize");
    check(resolver.AddDequantize() == kTfLiteOk, "dequantize");
    check(resolver.AddLogistic() == kTfLiteOk, "logistic");
    check(resolver.AddRelu() == kTfLiteOk, "relu");
    check(resolver.AddRelu6() == kTfLiteOk, "relu6");
    check(resolver.AddHardSwish() == kTfLiteOk, "hard_swish");
    check(resolver.AddSub() == kTfLiteOk, "sub");
    check(resolver.AddConcatenation() == kTfLiteOk, "concat");
    check(resolver.AddMaximum() == kTfLiteOk, "maximum");
    check(resolver.AddSqueeze() == kTfLiteOk, "squeeze");
    check(resolver.AddResizeBilinear() == kTfLiteOk, "resize_bilinear");
    check(resolver.AddStridedSlice() == kTfLiteOk, "strided_slice");
    check(resolver.AddTranspose() == kTfLiteOk, "transpose");
    // Non-supported ops must fail explicitly at AllocateTensors(), not be hidden.
    uint8_t *arena = static_cast<uint8_t *>(heap_caps_aligned_alloc(
        16, CNN_ARENA_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    check(arena && esp_ptr_external_ram(arena), "psram arena");
    tflite::MicroInterpreter interpreter(model, resolver, arena, CNN_ARENA_BYTES);
    check(interpreter.AllocateTensors() == kTfLiteOk, "AllocateTensors (unsupported op/arena?)");
    TfLiteTensor *in = interpreter.input(0);
    TfLiteTensor *out = interpreter.output(0);
    check(in && out, "input/output");
    check(in->type == kTfLiteInt8 && out->type == kTfLiteInt8, "int8 I/O");
    check(in->bytes == static_cast<size_t>(input_end - input_start), "input size");
    std::memcpy(in->data.int8, input_start, in->bytes);
    std::printf("CNN_START cpu_mhz=%d model_bytes=%u input_bytes=%u output_bytes=%u arena=psram arena_cap=%u arena_used=%u\n",
        CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, static_cast<unsigned>(model_end - model_start),
        static_cast<unsigned>(in->bytes), static_cast<unsigned>(out->bytes), unsigned(CNN_ARENA_BYTES),
        static_cast<unsigned>(interpreter.arena_used_bytes()));
    // Important: built-in TFLM MEAN is reference implementation, NOT ESP-NN!
    std::printf("CNN_ROUTING max_pool=requires_dispatch_probe mean=builtin_tflm_reference_not_esp_nn\n");
#ifdef CNN_DISPATCH_PROBE
    ProbeReset();
    check(interpreter.Invoke() == kTfLiteOk, "diagnostic invoke");
    ProbeReport();
    std::puts("CNN_PROBE_DONE");
    return;
#endif
    for (int i = 0; i < CNN_WARMUP; ++i) {
        // TFLM can reuse the input buffer after the input's last consumer.
        std::memcpy(in->data.int8, input_start, in->bytes);
        check(interpreter.Invoke() == kTfLiteOk, "warmup");
        vTaskDelay(1);
    }
    std::vector<int64_t> times;
    std::vector<uint32_t> cycles;
    times.reserve(CNN_SAMPLES); cycles.reserve(CNN_SAMPLES);
    std::vector<uint8_t> reference(out->bytes);
    bool equal_outputs = true;
    uint32_t checksum = 2166136261u;
    for (int i = 0; i < CNN_SAMPLES; ++i) {
        std::memcpy(in->data.int8, input_start, in->bytes);
        const uint32_t cycle_start = esp_cpu_get_cycle_count();
        const int64_t start = esp_timer_get_time();
        const TfLiteStatus status = interpreter.Invoke();
        const int64_t elapsed = esp_timer_get_time() - start;
        const uint32_t elapsed_cycles = esp_cpu_get_cycle_count() - cycle_start;
        check(status == kTfLiteOk, "timed invoke");
        times.push_back(elapsed); cycles.push_back(elapsed_cycles);
        if (i == 0) std::memcpy(reference.data(), out->data.int8, out->bytes);
        else if (std::memcmp(reference.data(), out->data.int8, out->bytes)) equal_outputs = false;
        vTaskDelay(1);
    }
    for (int i = 0; i < CNN_SAMPLES; ++i) {
        std::printf("CNN_RUN index=%d us=%" PRId64 " cycles=%" PRIu32 "\n", i, times[i], cycles[i]);
    }
    for (size_t i = 0; i < reference.size(); ++i)
        checksum = (checksum ^ reference[i]) * 16777619u;
    std::printf("CNN_OUTPUT bytes=%u hash_fnv1a=%08" PRIx32 " stable=%d hex=",
                static_cast<unsigned>(reference.size()), checksum, int(equal_outputs));
    for (size_t i=0; i < reference.size(); ++i) std::printf("%02x", reference[i]);
    std::printf("\n");
    std::printf("CNN_STACK high_water_bytes=%u\n", unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    std::sort(times.begin(), times.end());
    std::sort(cycles.begin(),cycles.end());
    std::printf("CNN_DONE samples=%d median_us=%" PRId64 " min_us=%" PRId64 " max_us=%" PRId64 " median_cycles=%" PRIu32 " min_cycles=%" PRIu32 " max_cycles=%" PRIu32 "\n",
                CNN_SAMPLES, times[times.size()/2], times.front(), times.back(),
                cycles[cycles.size()/2],cycles.front(),cycles.back());
}
