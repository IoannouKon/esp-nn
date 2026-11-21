#!/usr/bin/env bash
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
workspace=$(cd "$1" && pwd)
group=$2
log_dir="$kit/results/logs/suite_$group"
for entry in stock-1 opt2-1 mean-1 combined-1 combined-2 mean-2 opt2-2 stock-2; do
    version=${entry%-*}
    app="$workspace/$version/app"
    if [ -s "$log_dir/$entry.log" ]; then
        if grep -Fq 'CNN_SUITE_DONE' "$log_dir/$entry.log"; then
            continue
        fi
        timestamp=$(date -u +%Y%m%dT%H%M%SZ)
        mv "$log_dir/$entry.log" "$log_dir/$entry-$timestamp.incomplete.log"
        if [ -f "$log_dir/$entry.flash.log" ]; then
            mv "$log_dir/$entry.flash.log" "$log_dir/$entry-$timestamp.incomplete.flash.log"
        fi
    fi
    if [ "${WAIT_FOR_BUILDS:-0}" = 1 ]; then
        until [ -s "$kit/results/build/$group-$version-build/evidence.json" ]; do
            sleep 5
        done
    fi
    /usr/bin/python3 "$kit/scripts/run_suite.py" "$app" build "$log_dir/$entry.log" "${@:3}"
done
