# Benchmark evidence

- [CNN_RESULTS.md](CNN_RESULTS.md) lists model provenance, measured latency, output parity, dispatch and memory usage.
- [Comparison CSV](analysis/compare.csv) contains one row per model and firmware. [Comparison JSON](analysis/compare.json) also contains every timing and cycle sample, complete output bytes, boot medians and pairwise comparisons.
- [Timed captures](logs/) contain serial logs, build and flash logs, SDK configuration and flashed ELF verification for each boot.
- [Diagnostics](diagnostics/) contain untimed dispatch traces and MEAN reference checks. [Excluded attempts](attempts/) preserve initial captures and recovery evidence.
- [Replay commands](EXPERIMENT_COMMANDS.md) document the environment and procedure. [Provenance](provenance/) contains compiler and source path evidence. The package also includes all frozen model and input bytes in [models](../models/).
