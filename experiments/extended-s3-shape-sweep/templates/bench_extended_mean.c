/* SPDX-License-Identifier: Apache-2.0 */
/* Based on Espressif ESP-NN v1.5.0 benchmark methodology. */
/* ESP-NN extended INT8 mean shape sweep (experiment only).
 * The case callbacks, quantization and timing harness follow Espressif's
 * bench_app/main/bench_softmax_mean.c at ESP-NN v1.5.0.
 * All kernels are linked from the checked-out ESP-NN worktree; none are copied.
 */
#include <math.h>
#include <stdio.h>
#include <esp_nn.h>
#include "bench_ops.h"

typedef struct {
    int height, width, channels;
    int32_t mult, shift;
    const int8_t *input[2];
    bench_mem_t mem;
} mean_ctx_t;

#define MEAN_ARGS(c, in, out) (in), (out), (c)->height, (c)->width, (c)->channels, \
    -128, -128, (c)->mult, (c)->shift

static void mean_quant(int n, int32_t *mult, int32_t *shift)
{
    int e;
    const double q = frexp(1.0 / n, &e);
    int64_t m = llround(q * 2147483648.0);
    if (m == (1LL << 31)) {
        m /= 2;
        e++;
    }
    *mult = (int32_t)m;
    *shift = e;
}
static void mean_ref(void *p, int v, int8_t *out)
{
    const mean_ctx_t *c = p;
    esp_nn_mean_nhwc_s8_ansi(MEAN_ARGS(c, c->input[v], out));
}
static void mean_opt(void *p, int v, int8_t *out)
{
    const mean_ctx_t *c = p;
    esp_nn_mean_nhwc_s8(MEAN_ARGS(c, c->input[v], out));
}
static const bench_variant_t s_variants[] = { { "esp_nn", mean_opt } };

typedef struct { int h, w, ch; bench_mem_t mem; } mean_shape_t;
static const mean_shape_t s_shapes[] = {
/* BEGIN_GENERATED_MEAN */
/* END_GENERATED_MEAN */
};
static void run_shape(const mean_shape_t *s)
{
    const size_t size = (size_t)s->h * (size_t)s->w * (size_t)s->ch;
    mean_ctx_t c = { .height = s->h, .width = s->w, .channels = s->ch, .mem = s->mem };
    const int scratch_size = esp_nn_get_mean_scratch_size(s->h, s->w, s->ch);
    int8_t *in[2] = { bench_alloc(size, s->mem), bench_alloc(size, s->mem) };
    void *scratch = scratch_size > 0 ? bench_alloc(scratch_size, BENCH_MEM_INT) : NULL;
    char shape[48];
    snprintf(shape, sizeof(shape), "input %dx%dx%d", s->h, s->w, s->ch);
    if (in[0] && in[1] && (scratch_size <= 0 || scratch)) {
        bench_seed_case("mean", shape);
        bench_fill(in[0], size);
        bench_fill(in[1], size);
        c.input[0] = in[0];
        c.input[1] = in[1];
        mean_quant(s->h * s->w, &c.mult, &c.shift);
        esp_nn_set_mean_scratch_buf(scratch);
        const bench_case_t bc = {
            .op = "mean", .shape = shape, .mem = s->mem, .out_size = (size_t)s->ch,
            .ref = mean_ref, .variants = s_variants, .n_variants = 1, .ctx = &c,
        };
        bench_run(&bc);
        esp_nn_set_mean_scratch_buf(NULL);
    } else {
        bench_skip("mean", shape, s->mem);
    }
    bench_free(in[0]);
    bench_free(in[1]);
    bench_free(scratch);
}
void bench_extended_mean(void)
{
    for (size_t i = 0; i < sizeof(s_shapes) / sizeof(s_shapes[0]); ++i) {
        run_shape(&s_shapes[i]);
    }
}
