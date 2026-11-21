# ESP-NN multi-CNN validation kit for ESP32-S3-EYE

The executed study is recorded in [results/CNN_RESULTS.md](results/CNN_RESULTS.md). The setup below describes the incoming kit.

A handoff for Codex with a physical ESP32-S3-EYE. Source checked against ESP-NN v1.5.0 and the user's frozen MNIST experiment.

**NOT a set of prevalidated board models.** This zip includes code, model recipes, host preflight, a generic ESP-IDF/TFLM inference runner, log capture, and analysis. Binary `.tflite` models (except the historical one referenced for exact acquisition) must be generated/acquired by the agent with network and TensorFlow access. No new board measurements have been run from this ZIP.

## Suggested setup

```bash
unzip ESP_NN_MULTI_CNN_AGENT_KIT.zip
cd ESP_NN_MULTI_CNN_AGENT_KIT
python3 -m venv .venv
. .venv/bin/activate
pip install -r scripts/requirements.txt
bash scripts/prepare_mnist.sh /path/to/esp-nn
python3 scripts/generate_models.py --epochs 1 --train-samples 12000
python3 scripts/inspect_models.py
bash scripts/prepare_worktrees.sh /path/to/esp-nn /path/to/worktrees
```

The last step creates four detached worktrees; inspect the combined branch production diff and any extra source files. The generator may require downloading CIFAR-10 and is not constrained by the board's 20-minute inference benchmark limit.

### Set up the TFLM component and run a model

For **each** detached worktree, copy `app/` into `$WORKTREE/experiments/multi-cnn/app` and clone or copy a matching version of `esp-tflite-micro` into `$WORKTREE/experiments/multi-cnn/esp-tflite-micro`. The app's `main/idf_component.yml` points to `../../esp-tflite-micro` relative to the `main` directory; preserve this structure. For an IDF build, ensure that component resolves the **local ESP-NN worktree version**, not an independently downloaded registry copy.

```bash
cp models/mnist_fixed/model.tflite "$WORKTREE/experiments/multi-cnn/app/main/model.tflite"
cp models/mnist_fixed/input.bin "$WORKTREE/experiments/multi-cnn/app/main/input.bin"
cd "$WORKTREE/experiments/multi-cnn/app"
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyACM0 flash
python3 /path/to/kit/scripts/capture_serial.py --port /dev/ttyACM0 --out /path/to/results/mnist_fixed/stock-1.log
```

If CMake fails to find the worktree ESP-NN component, explicitly add ESP-NN in the same `EXTRA_COMPONENT_DIRS` manner used in Espressif's `bench_app`, then verify linked symbols and compiler inputs. Do not quietly fall back to registry ESP-NN v1.5.0 for every build.

A candidate `AllocateTensors` failure or unsupported op is a **SKIP with reason**, not a silent replacement by another CNN. For all successfully run models, compare **full output bytes** and all 30 timings per boot, not only top class or one median.

## What the app actually implements

- `app/main/main.cc` is a generic INT8 single-input/single-output ESP-TFLM runner; supports several common CNN operators. It can fail for extra ops: extend resolver explicitly after auditing the model.
- Uses embedded `model.tflite` and `input.bin` with 16-byte-aligned 2 MiB PSRAM arena (change uniformly only after recording need).
- Records 5 warm-ups, 30 individual Invoke timings and exact output hex per boot; captures tensor arena use.
- Diagnostic route prints: built-in TFLM `MEAN` is reference, **not ESP-NN EXP-MEAN**. Cannot claim an EXP-MEAN CNN speedup from this app without implementing and proving a separate bridge.
- `scripts/compare_cnn.py` combines two boots per build and strictly checks full-output equality. It does not infer mean-kernel dispatch and cannot certify routing.

## Files

- `AGENT_PROMPT.md`: full instructions and research validity gates
- `PASTE_THIS_PROMPT.txt`: short entry prompt
- `docs/MODEL_MATRIX.md`: exact model/bridge limitations
- `scripts/`: model preparation, host preflight, detached worktrees, serial capture, comparison
- `app/`: embedded-model inference application
- `results/`: empty results staging folder

Read `AGENT_PROMPT.md` and `docs/MODEL_MATRIX.md` **before** running. Do not alter existing optimization branches or exaggerate CNN claims.
