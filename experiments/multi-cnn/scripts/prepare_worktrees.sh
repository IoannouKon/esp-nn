#!/usr/bin/env bash
set -euo pipefail
# Creates only DETACHED worktrees. Never checks out or commits on user branches.
REPO="${1:?ESP-NN repository clone path}"; DEST="${2:?new workspace directory}"
mkdir -p "$DEST"
REPO="$(cd "$REPO" && pwd)"; DEST="$(cd "$DEST" && pwd)"
BASE=ace42ac7721119cd543fc40ffe719e601fa8f20f
MEAN=4bfa49c64a932f700688c2007a01d8ea1fa102ac
OPT2=edb003c6770491abb74766835f4c803b9d4f5a20
for item in "stock:$BASE" "mean:$MEAN" "opt2:$OPT2" "combined:$MEAN"; do
   name=${item%%:*}; rev=${item#*:};
   git -C "$REPO" worktree add --detach "$DEST/$name/esp-nn" "$rev"
done
# Overlay only Opt2's production pooling changes into the combined detached worktree.
# A combination is NOT a committed optimized branch. Do not modify source silently.
git -C "$REPO" diff "$BASE" "$OPT2" -- src/pooling/esp_nn_max_pool_s8_esp32s3.c src/pooling/esp_nn_max_pool_s8_esp32s3.S | git -C "$DEST/combined/esp-nn" apply --check
git -C "$REPO" diff "$BASE" "$OPT2" -- src/pooling/esp_nn_max_pool_s8_esp32s3.c src/pooling/esp_nn_max_pool_s8_esp32s3.S | git -C "$DEST/combined/esp-nn" apply
# Some Opt2 revisions add new files in src/pooling; verify the exact diff and copy if required.
printf '%s\n' 'VERIFY COMBINED PRODUCTION DIFF before building: Git diff base..Opt2 may include extra .S files.'
git -C "$DEST/combined/esp-nn" status --short
