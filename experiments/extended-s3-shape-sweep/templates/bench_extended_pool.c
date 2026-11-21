/* SPDX-License-Identifier: Apache-2.0 */
/* Based on Espressif ESP-NN v1.5.0 benchmark methodology. */
/* ESP-NN extended INT8 maxpool shape sweep (experiment only).
 * Follows Espressif's v1.5.0 bench_app/main/bench_pooling.c for reference,
 * output-size formula, deterministic inputs and standard bench_run harness.
 */
#include <stdio.h>
#include <esp_nn.h>
#include "bench_ops.h"

typedef struct {
    int in_wd, in_ht, ch, f_wd, f_ht, stride, pad;
    bench_mem_t mem;
} pool_shape_t;
static const pool_shape_t s_shapes[] = {
/* BEGIN_GENERATED_POOL */
/* END_GENERATED_POOL */
};
typedef struct {
    const pool_shape_t *s;
    int out_wd, out_ht;
    const int8_t *input[2];
} pool_ctx_t;
#define POOL_ARGS(c, in, out) (in), (c)->s->in_wd, (c)->s->in_ht, (out), \
    (c)->out_wd, (c)->out_ht, (c)->s->stride, (c)->s->stride, \
    (c)->s->f_wd, (c)->s->f_ht, (c)->s->pad, (c)->s->pad, \
    -128, 127, (c)->s->ch
static void max_ref(void *p, int v, int8_t *out)
{
    const pool_ctx_t *c = p;
    esp_nn_max_pool_s8_ansi(POOL_ARGS(c, c->input[v], out));
}
static void max_opt(void *p, int v, int8_t *out)
{
    const pool_ctx_t *c = p;
    esp_nn_max_pool_s8(POOL_ARGS(c, c->input[v], out));
}
static const bench_variant_t s_variants[] = { { "esp_nn", max_opt } };
static void run_shape(const pool_shape_t *s)
{
    const int out_wd = (s->in_wd + 2 * s->pad - s->f_wd) / s->stride + 1;
    const int out_ht = (s->in_ht + 2 * s->pad - s->f_ht) / s->stride + 1;
    const size_t in_size = (size_t)s->in_wd * (size_t)s->in_ht * (size_t)s->ch;
    const size_t out_size = (size_t)out_wd * (size_t)out_ht * (size_t)s->ch;
    pool_ctx_t c = { .s = s, .out_wd = out_wd, .out_ht = out_ht };
    int8_t *in[2] = { bench_alloc(in_size, s->mem), bench_alloc(in_size, s->mem) };
    char shape[96];
    snprintf(shape, sizeof(shape), "input %dx%dx%d, filter %dx%d, pad %d, stride %d",
             s->in_wd, s->in_ht, s->ch, s->f_wd, s->f_ht, s->pad, s->stride);
    if (in[0] && in[1]) {
        bench_seed_case("pool", shape);
        bench_fill(in[0], in_size);
        bench_fill(in[1], in_size);
        c.input[0] = in[0];
        c.input[1] = in[1];
        const bench_case_t bc = {
            .op = "max_pool", .shape = shape, .mem = s->mem, .out_size = out_size,
            .ref = max_ref, .variants = s_variants, .n_variants = 1, .ctx = &c,
        };
        bench_run(&bc);
    } else {
        bench_skip("max_pool", shape, s->mem);
    }
    bench_free(in[0]);
    bench_free(in[1]);
}
void bench_extended_pooling(void)
{
    for (size_t i = 0; i < sizeof(s_shapes) / sizeof(s_shapes[0]); ++i) {
        run_shape(&s_shapes[i]);
    }
}
