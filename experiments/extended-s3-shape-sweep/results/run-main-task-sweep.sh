#!/usr/bin/env bash
# Invoke after rebuilding all three worktrees with main-task-wrapper.patch.
set -euo pipefail
root="$(realpath "$1")"
kit="$(realpath "$2")"
port="${3:-/dev/ttyACM0}"
out="$root/results"
sequence=(stock exp_mean opt2 stock opt2 exp_mean)
for index in "${!sequence[@]}"; do
  build="${sequence[$index]}"
  boot=$((index < 3 ? 1 : 2))
  app="$root/$build/esp-nn/bench_app"
  base="$out/$build-$boot.log"
  [[ ! -e "$base" ]] || { echo "Log already exists: $base" >&2; exit 1; }
  echo "FLASHING: $build boot=$boot"
  (cd "$app" && idf.py -D PROJECT_VER=v1.5.0 -p "$port" flash > "$out/$build-flash-$boot.log" 2>&1)
  /usr/bin/time -o "$out/$build-$boot.elapsed" -f '%e' python3 "$kit/scripts/capture_monitor.py" \
    --cwd "$app" --port "$port" --output "$base" --timeout 1200 \
    > "$out/$build-capture-$boot.log" 2>&1
  grep -aE 'EXTBENCH_(HEAP|STACK)|^BENCH_DONE' "$base" | tr -d '\r'
  grep -aq '^BENCH_DONE cases=90 failures=0 skipped=0' "$base"
done
python3 "$kit/scripts/compare_extended.py" \
  --stock "$out/stock-1.log" "$out/stock-2.log" \
  --mean "$out/exp_mean-1.log" "$out/exp_mean-2.log" \
  --opt2 "$out/opt2-1.log" "$out/opt2-2.log" \
  --out "$out/analysis"
