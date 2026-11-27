# Reproduce the ESP32-S3-EYE finalist

The archived board used ESP-IDF v6.1 (fff9895c82d744c7237be8847347bdd1b07c6643), Xtensa GCC 15.2.0, a 240 MHz CPU, 80 MHz octal PSRAM and, unless labeled otherwise, a 64 KiB eight-way data cache with 64-byte lines. Use a complete ESP-NN clone, including the history through upstream 9fd985a and original PR tip dafea59. The script creates detached worktrees and writes new measurements to a scratch directory.

Install ESP-IDF's ESP32-S3 toolchain and source its export script before building.

    git clone --branch v6.1 --depth 1 --recurse-submodules https://github.com/espressif/esp-idf.git
    ./esp-idf/install.sh esp32s3
    . ./esp-idf/export.sh

Run the following from this experiment directory. The cleanup check uses the source and tests on this branch. The two measured benchmark patches preserve the exact research source behind the original reviewer-case and 62/64 claims.

    scratch="$(mktemp -d)"
    ./reproduce.sh build cleanup-test "$scratch"
    ./reproduce.sh capture cleanup-test "$scratch" 1
    ./reproduce.sh build cleanup-bench "$scratch"
    for round in 1 2 3 4 5; do
        ./reproduce.sh capture cleanup-bench "$scratch" "$round"
    done

    ./reproduce.sh build measured-sweep "$scratch"
    for round in 1 2 3 4 5; do
        ./reproduce.sh capture measured-sweep "$scratch" "$round"
    done
    python3 analyze.py measured-sweep --logs-dir "$scratch/logs"

    for label in master v0 finalist; do
        ./reproduce.sh build "$label" "$scratch"
    done
    ./reproduce.sh interleave "$scratch"

The capture command flashes the selected build, resets the board and accepts serial data only when the boot fingerprint matches the built ELF and the app reaches its completion marker. The optional last argument to capture and interleave is the serial device, which defaults to /dev/ttyACM0. The variants, order, control32-64, control64-32 and control64-4way labels build the wider research matrix, the order reversal probe and the cache controls. The cache-control builds reuse the archived full-variants source, so their firmware layout can differ from earlier diagnostic runs.

To verify the published captures with Python's standard library, run these commands from this directory.

    python3 summarize_controls.py tests
    python3 summarize_controls.py interleaved
    python3 summarize_controls.py direct-sweep
    python3 summarize_controls.py order
    python3 summarize_controls.py controls

The extended sweep pairs master, V0 and the direct finalist in each boot, over identical input buffers and the same ANSI references. The timing loop takes the minimum of eight calls after one warm-up, and the reported result is the median of five boot minima. It checks output equality and both guard areas, verifies memory placement and records separate hardware-counter samples. The archive contains original runtime serial bytes, generated sdkconfigs, build and firmware records and extracted data. Flash transcripts and host compile databases stay in the local research workspace.

[Results](RESULTS.md) · [Investigation](INVESTIGATION.md) · [Original baseline](reference/RESULTS.md) · [Kernel review](final-review/TECHNICAL_REVIEW.md)
