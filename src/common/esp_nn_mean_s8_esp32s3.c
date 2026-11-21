/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * ESP32-S3 mean reduction over the spatial dimensions of an NHWC int8 tensor.
 * EXP-MEAN: Use 16-lane QACC reduction when inputs are aligned, channel
 * stride is a multiple of 16, and spatial area <= 4095. Otherwise retain
 * the original scalar implementation. Exact integer requantization unchanged.
 */

#include <stdint.h>
#include <common_functions.h>

int32_t esp_nn_get_mean_scratch_size_esp32s3(const int32_t height, const int32_t width,
                                             const int32_t channels)
{
    (void) height;
    (void) width;
    (void) channels;
    return 0;
}

void esp_nn_set_mean_scratch_buf_esp32s3(void *buffer)
{
    (void) buffer;
}

static inline int8_t mean_requant(int32_t sum, const int32_t multiplier, const int32_t shift,
                                  const int32_t output_zero_point)
{
    int32_t result = esp_nn_multiply_by_quantized_mult(sum, multiplier, shift);
    result += output_zero_point;
    result = max(result, -128);
    result = min(result, 127);
    return (int8_t) result;
}


/*
 * ESP32-S3 PIE/TIE728 helper. Computes 16 signed INT8 channel sums.
 * raw[] is a 64-byte, 16-byte-aligned packed dump of 16 signed 20-bit lanes:
 *   lanes 0..7  in raw words 0..4; lanes 8..15 in raw words 8..12.
 * The 20-bit QACC lanes saturate. The caller limits area to 4095 so even
 * 4095 * (-128) = -524160 remains within [-524288, 524287].
 */
extern void esp_nn_mean_s8_16ch_qacc(const int8_t *input, uint32_t elements,
                                    uint32_t channels, uint32_t raw[16]);

static inline int32_t mean_qacc_lane20(const uint32_t *raw, uint32_t lane)
{
    const uint32_t *half = raw + ((lane >= 8u) ? 8u : 0u);
    const uint32_t bit = (lane & 7u) * 20u;
    const uint32_t word = bit >> 5;
    const uint32_t shift = bit & 31u;
    uint32_t value = half[word] >> shift;
    if (shift > 12u) {
        value |= half[word + 1u] << (32u - shift);
    }
    value &= 0xfffffu;
    return (value & 0x80000u) ? (int32_t)value - 0x100000 : (int32_t)value;
}

void esp_nn_mean_nhwc_s8_esp32s3(const int8_t *input,
                                  int8_t *output,
                                  const int32_t height,
                                  const int32_t width,
                                  const int32_t channels,
                                  const int32_t input_zero_point,
                                  const int32_t output_zero_point,
                                  const int32_t multiplier,
                                  const int32_t shift)
{
    const int32_t num_elements = height * width;
    const int32_t zp_correction = num_elements * input_zero_point;
    int32_t c = 0;

    /*
     * The 16-byte load requires 16-byte aligned input and a stride that
     * preserves alignment. The C output store has no output alignment need.
     * Keep the existing 4-channel loop as an exact fallback for all other
     * shapes, including large reductions where QACC could saturate.
     */
    /* Avoid changing behavior for in-place or overlapping tensor aliases. */
    const uintptr_t in_addr = (uintptr_t)input;
    const uintptr_t out_addr = (uintptr_t)output;
    const uint64_t input_bytes = (uint64_t)(uint32_t)num_elements * (uint32_t)channels;
    const int no_overlap = out_addr < in_addr
            ? (in_addr - out_addr >= (uintptr_t)channels)
            : ((uint64_t)(out_addr - in_addr) >= input_bytes);
    if (num_elements > 0 && num_elements <= 4095 && channels >= 16 &&
            (channels & 15) == 0 && ((in_addr & 15u) == 0) && no_overlap) {
        uint32_t raw[16] __attribute__((aligned(16)));
        for (c = 0; c < channels; c += 16) {
            esp_nn_mean_s8_16ch_qacc(input + c, (uint32_t)num_elements,
                                     (uint32_t)channels, raw);
            for (uint32_t lane = 0; lane < 16u; lane++) {
                const int32_t sum = mean_qacc_lane20(raw, lane);
                output[c + lane] = mean_requant(sum - zp_correction,
                                               multiplier, shift, output_zero_point);
            }
        }
        return;
    }

    for (; c + 4 <= channels; c += 4) {
        int32_t s0 = 0, s1 = 0, s2 = 0, s3 = 0;
        const int8_t *ptr = input + c;
        for (int32_t i = 0; i < num_elements; i++) {
            s0 += ptr[0];
            s1 += ptr[1];
            s2 += ptr[2];
            s3 += ptr[3];
            ptr += channels;
        }
        output[c + 0] = mean_requant(s0 - zp_correction, multiplier, shift, output_zero_point);
        output[c + 1] = mean_requant(s1 - zp_correction, multiplier, shift, output_zero_point);
        output[c + 2] = mean_requant(s2 - zp_correction, multiplier, shift, output_zero_point);
        output[c + 3] = mean_requant(s3 - zp_correction, multiplier, shift, output_zero_point);
    }
    for (; c < channels; c++) {
        int32_t sum = 0;
        const int8_t *ptr = input + c;
        for (int32_t i = 0; i < num_elements; i++) {
            sum += *ptr;
            ptr += channels;
        }
        output[c] = mean_requant(sum - zp_correction, multiplier, shift, output_zero_point);
    }
}
