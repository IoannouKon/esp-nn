#!/usr/bin/env python3
"""Check actual top-1 predictions of the frozen CIFAR classifiers."""
import argparse
from functools import partial
import json
from pathlib import Path

from keras.src.datasets import cifar10
import numpy as np
import tensorflow as tf

p = argparse.ArgumentParser()
p.add_argument("--cifar-cache", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
cifar10.get_file = partial(cifar10.get_file, cache_dir=str(a.cifar_cache))
_, (images, labels) = cifar10.load_data()
images = images[:1000].astype(np.float32) / 255
labels = labels[:len(images)].reshape(-1)
generated = json.loads((root / "models/generated_manifest.json").read_text())
result = {}
for model in generated:
    path = root / "models" / model / "model.tflite"
    t = tf.lite.Interpreter(model_path=str(path), num_threads=1)
    t.allocate_tensors()
    i, = t.get_input_details()
    o, = t.get_output_details()
    scale, zp = i["quantization"]
    exact = 0
    for img, truth in zip(images, labels):
        sample = np.clip(np.rint(img / scale) + zp, -128, 127).astype(np.int8)
        t.set_tensor(i["index"], sample.reshape(i["shape"]))
        t.invoke()
        exact += int(np.argmax(t.get_tensor(o["index"]).reshape(-1)) == truth)
    result[model] = {"int8_correct": exact, "examples": len(images), "top1": exact / len(images)}
    print(model, result[model])
(root / "results/cifar_int8_accuracy.json").write_text(json.dumps(result, indent=2) + "\n")
