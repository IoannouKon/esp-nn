# ESP32-S3 MaxPool column-first finalist

The normal ESP-NN entry point on this branch uses the cleaned finalist. The exact source used to measure the prototype is preserved in [the five-run sweep patch](patches/measured-sweep.patch) and [the reviewer-case patch](patches/measured-standalone.patch). Those patches apply to the original PR tip, dafea59. The cleaned implementation passed 861 dual-core checks and five benchmark boots. The prototype beat master on 62/64 shape-and-memory configurations across five interleaved boots. The two remaining losses were already present in the original PR. [Results](RESULTS.md) · [Kernel review and cleanup validation](final-review/TECHNICAL_REVIEW.md)

## Production transfer

Only these three implementation files belong in a kernel-only production change.

- [esp_nn_max_pool_s8_esp32s3.c](../../src/pooling/esp_nn_max_pool_s8_esp32s3.c) adds the full-range dispatch, the bounded local ring and the direct paired-row driver.
- [esp_nn_max_pool_s8_esp32s3.S](../../src/pooling/esp_nn_max_pool_s8_esp32s3.S) adds the scheduled streaming and paired SIMD leaves.
- [esp_nn_max_pool_s8_esp32s3.h](../../src/pooling/esp_nn_max_pool_s8_esp32s3.h) defines the private row descriptor offsets shared with assembly.

[The kernel-only patch](final-review/production.patch) applies those changes to dafea59. [pooling_test.c](../../tests/src/pooling_test.c) adds nine correctness cases and is kept separate from that patch. The benchmark variants, scripts and captures live under this experiment directory.

The streamer completes the channel groups of each column in batches of up to 128 channels and uses an aligned 512-byte history ring. The 32-channel 3×3 path processes both groups in one call per row and holds both histories in SIMD registers. The original clamped path handles narrower INT8 limits and single-group inputs. The dispatch uses no tensor-size cutoff. [Algorithm, traversal, register allocation and scheduling](final-review/TECHNICAL_REVIEW.md) · [Investigation](INVESTIGATION.md) · [Reproduction](REPRODUCE.md)
