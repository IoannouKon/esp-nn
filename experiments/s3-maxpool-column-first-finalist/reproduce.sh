#!/usr/bin/env bash
set -eo pipefail

evidence="$(cd "$(dirname "$0")" && pwd)"
repo="$(git -C "$evidence" rev-parse --show-toplevel)"
base=dafea5932861701ac79c7830a29b487442e50cc6
master=9fd985a931a69ef15a3d9e151f46261a36d51581
usage() {
    echo 'Usage: reproduce.sh build LABEL SCRATCH | capture LABEL SCRATCH RUN [PORT]' >&2
    echo '       reproduce.sh interleave SCRATCH [PORT]' >&2
    exit 2
}

action=$1
if [[ "$action" == interleave ]]; then
    scratch=$2
    port=$3
    if [[ -z "$port" ]]; then port=/dev/ttyACM0; fi
    for round in 1 2 3 4 5; do
        case "$round" in
            1|4) order=(master v0 finalist);;
            2|5) order=(v0 finalist master);;
            3) order=(finalist master v0);;
        esac
        for name in "${order[@]}"; do
            "$0" capture "$name" "$scratch" "$round" "$port"
        done
    done
    exit
fi

label=$2
scratch=$3
if [[ -z "$scratch" || -z "$label" || -z "$IDF_PATH" ]]; then usage; fi
mkdir -p "$scratch"
scratch="$(cd "$scratch" && pwd)"
if [[ "$(git -C "$IDF_PATH" rev-parse HEAD)" != fff9895c82d744c7237be8847347bdd1b07c6643 ]]; then
    echo 'Source export.sh from the pinned ESP-IDF v6.1 checkout before running.' >&2
    exit 1
fi
export IDF_PY_BUILD_JOBS="${IDF_PY_BUILD_JOBS:-4}"
app=bench_app
version=pr68-locality
revision=$base
board="$evidence/config/board.defaults"
extra=""
patch=""
case "$label" in
    master|v0)
        if [[ "$label" == master ]]; then revision=$master; fi
        version=pr68-repro
        patch="$evidence/reference/bench.patch"
        board="$evidence/reference/config/board.defaults"
        ;;
    finalist)
        patch="$evidence/patches/measured-standalone.patch"
        board="$evidence/reference/config/board.defaults"
        ;;
    measured-sweep) patch="$evidence/patches/measured-sweep.patch";;
    variants) patch="$evidence/patches/experiment.patch";;
    order) patch="$evidence/patches/order-probe.patch";;
    control32-64|control64-32|control64-4way)
        patch="$evidence/patches/experiment.patch"
        case "$label" in
            control32-64) extra=";$evidence/config/cache32-line64.defaults";;
            control64-32) extra=";$evidence/config/cache64-line32.defaults";;
            control64-4way) extra=";$evidence/config/cache64-ways4.defaults";;
        esac
        ;;
    cleanup-test|cleanup-bench)
        revision="$(git -C "$repo" rev-parse HEAD)"
        board="$evidence/reference/config/board.defaults"
        if [[ "$label" == cleanup-test ]]; then
            app=test_app
        else
            patch="$evidence/patches/validation-bench.patch"
        fi
        ;;
    *) usage;;
esac
tree="$scratch/worktrees/$label/esp-nn"
build="$scratch/build/$label"
logs="$scratch/logs/$label"
if [[ "$action" == build ]]; then
    if [[ -e "$tree" || -e "$build" || -e "$logs" ]]; then
        echo "Choose a fresh scratch directory for $label." >&2
        exit 1
    fi
    mkdir -p "$(dirname "$tree")" "$build" "$logs"
    git -C "$repo" worktree add --detach "$tree" "$revision"
    if [[ -n "$patch" ]]; then
        git -C "$tree" apply "$patch"
    fi
    (
        cd "$tree/$app"
        idf.py --ccache -B "$build" -DIDF_TARGET=esp32s3 -DPROJECT_VER="$version" \
            "-DSDKCONFIG=$build/sdkconfig" \
            "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.esp32s3;$board$extra" build
    ) >"$logs/build.log" 2>&1
    cp "$build/sdkconfig" "$build/compile_commands.json" "$build/flasher_args.json" "$logs/"
    (cd "$build" && sha256sum "$app.elf" "$app.bin") >"$logs/firmware.sha256"
    echo "Built $label under $scratch."
elif [[ "$action" == capture ]]; then
    run=$4
    port=$5
    if [[ -z "$run" ]]; then usage; fi
    if [[ -z "$port" ]]; then port=/dev/ttyACM0; fi
    test -c "$port"
    test ! -e "$logs/run-$run.log"
    test ! -e "$logs/flash-$run.log"
    (
        cd "$build"
        sha256sum -c "$logs/firmware.sha256"
        python -m esptool --chip esp32s3 -p "$port" -b 460800 \
            --before default-reset --after hard-reset write-flash @flash_args
    ) >"$logs/flash-$run.log" 2>&1
    python "$evidence/capture.py" "$tree/$app" "$port" "$logs/run-$run.log" --build-dir "$build"
else
    usage
fi
