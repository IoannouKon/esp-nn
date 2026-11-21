#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <esp_nn.h>

extern void esp_nn_mean_s8_16ch_qacc(const int8_t *, uint32_t, uint32_t, uint32_t *);

enum { CHANNELS = 16, MAX_AREA = 4096, GUARD = 16 };
static _Alignas(16) int8_t input[MAX_AREA * CHANNELS + 1];
static const int8_t pixels[CHANNELS] = {
    -128, 127, -125, 113, -108, 99, -85, 81, -75, 66, -51, 43, -32, 22, -11, 0,
};

static void check(bool ok, const char *label)
{
    if (!ok) {
        printf("MEAN_EDGE_FAIL %s\n", label);
        abort();
    }
}

static void check_dump(void)
{
    _Alignas(16) uint32_t guarded[24];
    uint32_t expected[24];
    uint32_t *raw = guarded + GUARD / sizeof(uint32_t);
    for (size_t i = 0; i < 24; ++i) {
        guarded[i] = expected[i] = 0xa5a5a5a5u;
    }
    for (int half = 0; half < 2; ++half) {
        uint32_t *words = expected + GUARD / sizeof(uint32_t) + half * 8;
        memset(words, 0, 5 * sizeof(*words));
        for (int lane = 0; lane < 8; ++lane) {
            uint32_t signed_sum = (uint32_t)(4095 * pixels[half * 8 + lane]);
            for (int bit = 0; bit < 20; ++bit) {
                int offset = lane * 20 + bit;
                words[offset / 32] |= ((signed_sum >> bit) & 1u) << (offset % 32);
            }
        }
    }
    check(((uintptr_t)raw & 15u) == 0, "raw alignment");
    esp_nn_mean_s8_16ch_qacc(input, 4095, CHANNELS, raw);
    check(memcmp(guarded, expected, sizeof(expected)) == 0, "raw bytes and guards");
    printf("MEAN_EDGE_PASS area=4095 raw=%p bytes_written=40 padding_and_guards=ok\n", (void *)raw);
}

static void check_output(const int8_t *data, int area, const char *path)
{
    int exponent;
    int32_t multiplier = (int32_t)llround(frexp(1.0 / area, &exponent) * 2147483648.0);
    int8_t reference[CHANNELS];
    int8_t output[CHANNELS + 2];
    memset(output, 0x5a, sizeof(output));
    esp_nn_mean_nhwc_s8_ansi(data, reference, 1, area, CHANNELS, -3, 5, multiplier, exponent);
    esp_nn_mean_nhwc_s8(data, output + 1, 1, area, CHANNELS, -3, 5, multiplier, exponent);
    check(memcmp(reference, output + 1, sizeof(reference)) == 0 &&
          output[0] == 0x5a && output[CHANNELS + 1] == 0x5a, path);
    printf("MEAN_EDGE_PASS area=%d input_offset=%u output=bit_exact path=%s\n",
           area, (unsigned)((uintptr_t)data & 15u), path);
}

void app_main(void)
{
    for (int i = 0; i < MAX_AREA; ++i) {
        memcpy(input + i * CHANNELS, pixels, CHANNELS);
    }
    check_dump();
    check_output(input, 4095, "qacc");
    check_output(input, 4096, "area_fallback");
    check_output(input + 1, 4095, "unaligned_fallback");
    puts("MEAN_EDGE_DONE");
}
