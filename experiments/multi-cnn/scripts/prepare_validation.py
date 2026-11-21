#!/usr/bin/env python3
"""Freeze fixed and additional inputs for this model matrix."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import tensorflow as tf

p = argparse.ArgumentParser()
p.add_argument("--cifar-cache", type=Path, required=True)
p.add_argument("--mnist", type=Path, required=True)
args = p.parse_args()
models = Path(__file__).resolve().parents[1] / "models"
from keras.src.datasets import cifar10
from functools import partial
cifar10.get_file = partial(cifar10.get_file, cache_dir=str(args.cifar_cache))
_, (cifar, _) = tf.keras.datasets.cifar10.load_data()
mnist = np.load(args.mnist)["x_test"]
for directory in sorted(models.iterdir()):
    path = directory / "model.tflite"
    if not path.exists() or directory.name == "person_detection":
        continue
    runtime = tf.lite.Interpreter(model_path=str(path), num_threads=1)
    inputs, = runtime.get_input_details()
    scale, zp = inputs["quantization"]
    dtype = inputs["dtype"]
    if dtype not in (np.int8, np.uint8):
        print(directory.name, "unsupported IO", dtype)
        continue
    extras = []
    for index in range(7):
        name = directory.name
        if name == "mnist_fixed":
            pixels = mnist[index, ..., None].astype(np.float32) / 255.0
        elif name in ("mobilenet_v2", "mobilenet_v3_small"):
            image = Image.fromarray(cifar[index]).resize((232, 232), Image.Resampling.BILINEAR)
            pixels = np.asarray(image.crop((4, 4, 228, 228)), dtype=np.float32) / 255.0
            pixels = (pixels - np.array([.485,.456,.406], dtype=np.float32)) / np.array(
                [.229,.224,.225], dtype=np.float32)
            if inputs["shape"][1] == 3:
                pixels = pixels.transpose(2, 0, 1)
        elif name == "efficientnet_lite0":
            # Google MediaPipe ImageClassifier copies resized RGB bytes for UINT8 input.
            pixels = np.asarray(Image.fromarray(cifar[index]).resize((224, 224), Image.Resampling.BILINEAR))
        else:
            pixels = cifar[index].astype(np.float32) / 255.0
        if name != "efficientnet_lite0":
            bound = np.iinfo(dtype)
            pixels = np.clip(np.rint(pixels / scale) + zp, bound.min, bound.max).astype(dtype)
        assert pixels.size == int(np.prod(inputs["shape"]))
        if index == 0:
            if name.startswith("mobilenet") or name == "efficientnet_lite0":
                (directory / "input.bin").write_bytes(pixels.tobytes())
            continue
        extras.append(pixels.tobytes())
    (directory / "validation.bin").write_bytes(b"".join(extras))
