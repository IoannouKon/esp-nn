#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_memory_utils.h"
#include "sdkconfig.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"

extern const uint8_t model_start[] asm("_binary_model_tflite_start");
extern const uint8_t input_start[] asm("_binary_input_bin_start");
extern const uint8_t input_end[] asm("_binary_input_bin_end");

namespace {
constexpr size_t kArenaBytes = 96 * 1024;
constexpr int kOutputElements = 10;
static_assert(CONFIG_FREERTOS_UNICORE == 1);

void require(bool success, const char *step)
{
    if (!success) {
        std::printf("CNN_ERROR %s\n", step);
        std::abort();
    }
}
}

extern "C" void app_main()
{
    const tflite::Model *model = tflite::GetModel(model_start);
    require(model->version() == TFLITE_SCHEMA_VERSION, "model schema");

    tflite::MicroMutableOpResolver<4> resolver;
    require(resolver.AddConv2D() == kTfLiteOk, "register conv");
    require(resolver.AddMaxPool2D() == kTfLiteOk, "register max pool");
    require(resolver.AddReshape() == kTfLiteOk, "register reshape");
    require(resolver.AddFullyConnected() == kTfLiteOk, "register fully connected");

    auto *arena = static_cast<uint8_t *>(heap_caps_aligned_alloc(
        16, kArenaBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    require(arena != nullptr && esp_ptr_external_ram(arena), "PSRAM tensor arena");
    tflite::MicroInterpreter interpreter(model, resolver, arena, kArenaBytes);
    require(interpreter.AllocateTensors() == kTfLiteOk, "allocate tensors");
    TfLiteTensor *input = interpreter.input(0);
    TfLiteTensor *output = interpreter.output(0);
    require(input->type == kTfLiteInt8 && input->bytes == size_t(input_end - input_start),
            "input tensor");
    require(output->type == kTfLiteInt8 && output->bytes == kOutputElements, "output tensor");
    std::memcpy(input->data.int8, input_start, input->bytes);

    std::printf("CNN_START cpu_mhz=%d arena=psram arena_address=%p arena_bytes=%u arena_used=%u\n",
                CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, static_cast<void *>(arena), unsigned(kArenaBytes),
                unsigned(interpreter.arena_used_bytes()));

#ifdef PROBE_OPT2
    require(interpreter.Invoke() == kTfLiteOk, "diagnostic invoke");
#else
    constexpr int kWarmup = 3;
    constexpr int kSamples = 20;
    struct Sample {
        int64_t micros;
        int8_t output[kOutputElements];
    };
    Sample samples[kSamples];
    for (int i = 0; i < kWarmup; ++i) {
        require(interpreter.Invoke() == kTfLiteOk, "warm-up invoke");
    }
    for (Sample &sample : samples) {
        const int64_t begin = esp_timer_get_time();
        const TfLiteStatus status = interpreter.Invoke();
        sample.micros = esp_timer_get_time() - begin;
        require(status == kTfLiteOk, "timed invoke");
        std::memcpy(sample.output, output->data.int8, sizeof(sample.output));
    }
    for (int i = 0; i < kSamples; ++i) {
        std::printf("CNN_RUN %02d us=%" PRId64 " output=", i + 1, samples[i].micros);
        for (int j = 0; j < kOutputElements; ++j) {
            std::printf("%s%d", j ? "," : "", int(samples[i].output[j]));
        }
        std::printf("\n");
    }
#endif
    std::printf("CNN_DONE\n");
}
