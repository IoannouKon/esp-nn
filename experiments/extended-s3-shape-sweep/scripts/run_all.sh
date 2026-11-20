#!/usr/bin/env bash
# Run in an ESP-IDF v5.5.1 environment, with ESP32-S3-EYE connected.
# Never checks out an existing user branch and never changes its HEAD.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$(cd "$SCRIPT_DIR/.." && pwd)"
STOCK=ace42ac7721119cd543fc40ffe719e601fa8f20f
MEAN=4bfa49c64a932f700688c2007a01d8ea1fa102ac
OPT2=edb003c6770491abb74766835f4c803b9d4f5a20
REPO=""; WORK_ROOT=""; PORT=/dev/ttyACM0

help() {
  echo 'Usage: bash scripts/run_all.sh --repo /path/to/esp-nn --workspace /path/to/empty/bench-work --port /dev/ttyACM0'
  echo 'Requires: activated ESP-IDF, Python3, git, physical ESP32-S3-EYE.'
}
while (($#)); do
  case "$1" in
    --repo) REPO="$2";shift 2;;
    --workspace) WORK_ROOT="$2";shift 2;;
    --port) PORT="$2";shift 2;;
    -h|--help) help;exit 0;;
    *) echo "Unknown argument: $1" >&2;help;exit 2;;
  esac
done
[[ -n "$REPO" && -n "$WORK_ROOT" ]] || { help;exit 2; }
command -v idf.py >/dev/null || { echo 'Activate ESP-IDF first' >&2;exit 1; }
[[ -n "${IDF_PATH:-}" ]] || { echo 'IDF_PATH missing; source export.sh first' >&2;exit 1; }
REPO="$(realpath "$REPO")"
[[ -e "$REPO/.git" ]] || { echo "Not an ESP-NN Git repository: $REPO" >&2;exit 1; }
[[ ! -e "$WORK_ROOT" ]] || { echo "Workspace already exists; refusing to overwrite: $WORK_ROOT" >&2;exit 1; }
for SHA in "$STOCK" "$MEAN" "$OPT2"; do
  git -C "$REPO" cat-file -e "$SHA^{commit}" || { echo "Missing commit $SHA; fetch the fork" >&2;exit 1; }
done
mkdir -p "$WORK_ROOT"/results
WORK_ROOT="$(realpath "$WORK_ROOT")"
printf 'BEGIN: %s\n' "$(date -Is)" | tee "$WORK_ROOT/results/session.txt"
printf 'IDF_PATH=%s\nPORT=%s\n' "$IDF_PATH" "$PORT" | tee -a "$WORK_ROOT/results/session.txt"
for k in stock exp_mean opt2; do
  case "$k" in stock) SHA="$STOCK";; exp_mean) SHA="$MEAN";; opt2) SHA="$OPT2";; esac
  mkdir -p "$WORK_ROOT/$k"
  git -C "$REPO" worktree add --detach "$WORK_ROOT/$k/esp-nn" "$SHA"
  git -C "$WORK_ROOT/$k/esp-nn" rev-parse HEAD >> "$WORK_ROOT/results/commits.txt"
  python3 "$SCRIPT_DIR/install_extended.py" --repo "$WORK_ROOT/$k/esp-nn" --ref "$SHA" \
    > "$WORK_ROOT/results/$k-install.json"
  APP="$WORK_ROOT/$k/esp-nn/bench_app"
  ( cd "$APP"
    idf.py -D PROJECT_VER=v1.5.0 set-target esp32s3 \
      > "$WORK_ROOT/results/$k-set-target.log" 2>&1
    idf.py -D PROJECT_VER=v1.5.0 build \
      > "$WORK_ROOT/results/$k-build.log" 2>&1
    sha256sum sdkconfig > "$WORK_ROOT/results/$k-sdkconfig.sha256"
  )
  echo "BUILT: $k"
done
python3 "$SCRIPT_DIR/verify_build_integrity.py" --workspace "$WORK_ROOT"
python3 - "$WORK_ROOT" <<'PY'
import hashlib,sys
from pathlib import Path
root=Path(sys.argv[1]); items={}
for k in ('stock','exp_mean','opt2'):
    b=(root/k/'esp-nn/bench_app/sdkconfig').read_bytes()
    items[k]=hashlib.sha256(b).hexdigest()
if len(set(items.values()))!=1:
    raise SystemExit(f'FATAL: sdkconfig differences: {items}')
print('SDKCONFIG_IDENTICAL',items)
PY

# Two full boots per build. Alternate to reduce order/temperature confounds.
sequence=(stock exp_mean opt2 stock opt2 exp_mean)
for index in "${!sequence[@]}"; do
  k="${sequence[$index]}"
  boot=$((index<3?1:2))
  APP="$WORK_ROOT/$k/esp-nn/bench_app"
  echo "FLASHING: $k boot=$boot"
  (cd "$APP" && idf.py -D PROJECT_VER=v1.5.0 -p "$PORT" flash \
    > "$WORK_ROOT/results/$k-flash-$boot.log" 2>&1)
  # Runtime limit is 20 minutes PER FULL 90-case benchmark boot, not builds.
  python3 "$SCRIPT_DIR/capture_monitor.py" --cwd "$APP" --port "$PORT" \
    --output "$WORK_ROOT/results/$k-$boot.log" --timeout 1200 \
    > "$WORK_ROOT/results/$k-capture-$boot.log" 2>&1
  echo "CAPTURED: $k boot=$boot"
done
python3 "$SCRIPT_DIR/compare_extended.py" \
  --stock "$WORK_ROOT/results/stock-1.log" "$WORK_ROOT/results/stock-2.log" \
  --mean "$WORK_ROOT/results/exp_mean-1.log" "$WORK_ROOT/results/exp_mean-2.log" \
  --opt2 "$WORK_ROOT/results/opt2-1.log" "$WORK_ROOT/results/opt2-2.log" \
  --out "$WORK_ROOT/results/analysis"
printf 'COMPLETE: %s\n' "$(date -Is)" | tee -a "$WORK_ROOT/results/session.txt"
echo "RESULTS: $WORK_ROOT/results/analysis/RESULTS.md"
