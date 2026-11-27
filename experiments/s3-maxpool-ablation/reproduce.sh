#!/usr/bin/env bash
set -eo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
reference="$here/../s3-maxpool-column-first-finalist"
repo="$(git -C "$here" rev-parse --show-toplevel)"
mode=$1
scratch=$2
port=$3
if [[ -z "$scratch" || -z "$IDF_PATH" ]]; then
    echo 'Usage: reproduce.sh initial|sweep|tests-0|tests-1|tests-2 SCRATCH [PORT]' >&2
    exit 2
fi
if [[ "$(git -C "$IDF_PATH" rev-parse HEAD)" != fff9895c82d744c7237be8847347bdd1b07c6643 ]]; then
    echo 'Source export.sh from the pinned ESP-IDF v6.1 checkout.' >&2
    exit 1
fi
if [[ -z "$port" ]]; then port=/dev/ttyACM0; fi
test -c "$port"
export IDF_PY_BUILD_JOBS=4
mkdir -p "$scratch"
scratch="$(cd "$scratch" && pwd)"
tree="$scratch/esp-nn"
if [[ ! -e "$tree" ]]; then
    git -C "$repo" worktree add --detach "$tree" dafea5932861701ac79c7830a29b487442e50cc6
    git -C "$tree" apply "$here/ablation-harness.patch"
fi
app=bench_app
runs=5
case "$mode" in
    initial) definition=-DABLATION_STAGE=0 ;;
    sweep) definition=-DABLATION_STAGE=1 ;;
    tests-0|tests-1|tests-2)
        app=test_app
        runs=1
        definition="-DABLATION_TEST_BANK=$(cut -d- -f2 <<<"$mode")"
        ;;
    *) echo "Unknown stage $mode" >&2; exit 2 ;;
esac
out="$scratch/logs/$mode"
build="$scratch/build/$mode"
test ! -e "$out/run-1.log"
mkdir -p "$out" "$build"
cd "$tree/$app"
idf.py --ccache -B "$build" -DIDF_TARGET=esp32s3 -DPROJECT_VER=pr68-ablation \
    "$definition" "-DSDKCONFIG=$build/sdkconfig" \
    "-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.esp32s3;$reference/config/board.defaults" \
    build >"$out/build.log" 2>&1
cp "$build/sdkconfig" "$out/"
(cd "$build" && sha256sum "$app.elf" "$app.bin") >"$out/firmware.sha256"
(
    cd "$build"
    sha256sum -c "$out/firmware.sha256"
    python -m esptool --chip esp32s3 -p "$port" -b 460800 \
        --before default-reset --after hard-reset write-flash @flash_args
) >"$out/flash.log" 2>&1
for ((i=1; i<=runs; ++i)); do
    python "$reference/capture.py" "$tree/$app" "$port" "$out/run-$i.log" \
        --build-dir "$build" --timeout 300
done
