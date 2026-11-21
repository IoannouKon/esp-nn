#include <cstdint>
#include <cstdio>

namespace {
unsigned sliding_rows;
}

extern "C" void __real_esp_nn_max_pool_s8_esp32s3_sliding_row_asm(
    const int8_t *, int8_t *, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t,
    int32_t, int32_t);
extern "C" void __wrap_esp_nn_max_pool_s8_esp32s3_sliding_row_asm(
    const int8_t *input, int8_t *output, uint32_t width, uint32_t channels,
    uint32_t row_bytes, uint32_t rows, uint32_t pad, int32_t min, int32_t max)
{
    ++sliding_rows;
    __real_esp_nn_max_pool_s8_esp32s3_sliding_row_asm(
        input, output, width, channels, row_bytes, rows, pad, min, max);
}

extern "C" void __real_esp_nn_max_pool_s8_esp32s3(
    const int8_t *, uint16_t, uint16_t, int8_t *, uint16_t, uint16_t,
    uint16_t, uint16_t, uint16_t, uint16_t, uint16_t, uint16_t, int32_t, int32_t, uint16_t);
extern "C" void __wrap_esp_nn_max_pool_s8_esp32s3(
    const int8_t *input, uint16_t width, uint16_t height, int8_t *output,
    uint16_t out_width, uint16_t out_height, uint16_t stride_w, uint16_t stride_h,
    uint16_t filter_w, uint16_t filter_h, uint16_t pad_w, uint16_t pad_h,
    int32_t min, int32_t max, uint16_t channels)
{
    sliding_rows = 0;
    __real_esp_nn_max_pool_s8_esp32s3(input, width, height, output, out_width, out_height,
                                    stride_w, stride_h, filter_w, filter_h, pad_w, pad_h,
                                    min, max, channels);
    std::printf("CNN_POOL input=%p output=%p shape=%ux%ux%u out=%ux%u filter=%ux%u "
                "stride=%ux%u pad=%ux%u sliding_rows=%u\n",
                static_cast<const void *>(input), static_cast<void *>(output),
                unsigned(width), unsigned(height), unsigned(channels), unsigned(out_width),
                unsigned(out_height), unsigned(filter_w), unsigned(filter_h),
                unsigned(stride_w), unsigned(stride_h), unsigned(pad_w), unsigned(pad_h), sliding_rows);
}

namespace {
unsigned qacc_blocks;
}

extern "C" void __real_esp_nn_mean_s8_16ch_qacc(
    const int8_t*, uint32_t, uint32_t, uint32_t*);
extern "C" void __wrap_esp_nn_mean_s8_16ch_qacc(
    const int8_t* input, uint32_t elements, uint32_t channels, uint32_t* raw) {
    ++qacc_blocks;
    __real_esp_nn_mean_s8_16ch_qacc(input, elements, channels, raw);
}

void ProbeReset() { qacc_blocks = 0; }
void ProbeReport() { std::printf("CNN_QACC diagnostic_blocks=%u\n", qacc_blocks); }
