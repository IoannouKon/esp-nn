#!/usr/bin/env bash
# Prepare independent 4-firmware benchmark workspaces; NEVER touches optimization branches.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${1:?Usage: prepare_benchmark_workspace.sh /path/to/esp-nn /fresh/workspace}"
DEST="${2:?Usage: prepare_benchmark_workspace.sh /path/to/esp-nn /fresh/workspace}"
[[ ! -e "$DEST" ]] || { echo "REFUSE existing workspace: $DEST" >&2;exit 3; }
mkdir -p "$DEST"
REPO="$(cd "$REPO" && pwd)"; DEST="$(cd "$DEST" && pwd)"
BASE=ace42ac7721119cd543fc40ffe719e601fa8f20f
MEAN=4bfa49c64a932f700688c2007a01d8ea1fa102ac
OPT2=edb003c6770491abb74766835f4c803b9d4f5a20
TFLM=df8722334a80ceabc609c1e72968f417cd9437f1
for key in "stock:$BASE" "opt2:$OPT2" "mean:$MEAN" "combined:$MEAN"; do
  name=${key%%:*};sha=${key#*:}
  git -C "$REPO" cat-file -e "$sha^{commit}" || { echo "Missing $sha in $REPO. Fetch fork refs.";exit 2; }
  mkdir -p "$DEST/$name"
  git -C "$REPO" worktree add --detach "$DEST/$name/esp-nn" "$sha"
  cp -a "$KIT/app" "$DEST/$name/app"
  git clone -q https://github.com/espressif/esp-tflite-micro.git "$DEST/$name/esp-tflite-micro"
  git -C "$DEST/$name/esp-tflite-micro" checkout -q --detach "$TFLM"
  python3 - "$DEST/$name/esp-tflite-micro/idf_component.yml" <<'PYPATCH'
import sys
from pathlib import Path
f=Path(sys.argv[1]);s=f.read_text();pattern='    version: ">=1.4.2"'
assert pattern in s, 'Unexpected pinned TFLM manifest layout; inspect manually'
f.write_text(s.replace(pattern,pattern+'\n    override_path: "../esp-nn"'))
PYPATCH
  # Ensure all firmware variants use exactly the same ESP-TFLM source.
  echo "$name source $(git -C "$DEST/$name/esp-nn" rev-parse HEAD) TFLM $(git -C "$DEST/$name/esp-tflite-micro" rev-parse HEAD)"
done
# Combine ONLY two production pooling files; no benchmark app/result files.
git -C "$REPO" diff "$BASE" "$OPT2" -- src/pooling/esp_nn_max_pool_s8_esp32s3.c src/pooling/esp_nn_max_pool_s8_esp32s3.S | git -C "$DEST/combined/esp-nn" apply --check
git -C "$REPO" diff "$BASE" "$OPT2" -- src/pooling/esp_nn_max_pool_s8_esp32s3.c src/pooling/esp_nn_max_pool_s8_esp32s3.S | git -C "$DEST/combined/esp-nn" apply
printf '\nCOMBINED DIFF (review):\n'
git -C "$DEST/combined/esp-nn" diff --stat
printf '\nREADY: %s\n' "$DEST"
