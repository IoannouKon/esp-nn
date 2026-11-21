#!/usr/bin/env python3
"""Train only the two follow-up models, audit their FlatBuffers and freeze extra inputs."""
import argparse
import hashlib
import json
import random
import sys
from functools import partial
from pathlib import Path

import numpy as np
import tensorflow as tf
from keras.src.datasets import cifar10
from tensorflow.lite.python import schema_py_generated as fb

EXTENSION = Path(__file__).resolve().parents[1]
ORIGINAL = EXTENSION.parent
sys.path.insert(0, str(ORIGINAL / "scripts"))
import generate_models as training
from inspect_models import inspect as inspect_model

NEW_MODELS = {"cifar_mean_wide": (14, 14, 128), "cifar_mean_large": (28, 28, 32)}
MODELS = ("mean_only", "both", "depthwise_both", *NEW_MODELS)
ORIGINAL_MEAN_SHAPES = {"mean_only": (8, 8, 32), "both": (8, 8, 32), "depthwise_both": (16, 16, 32)}
EXTRA_SEED = 231121


def build(name, channels):
    layers = tf.keras.layers
    pixels = tf.keras.Input((32, 32, 3), name="pixels")
    x = layers.Conv2D(16, 3, padding="valid", activation="relu")(pixels)
    x = layers.Conv2D(channels, 3, strides=2 if channels == 128 else 1,
                      padding="valid", activation="relu")(x)
    x = layers.GlobalAveragePooling2D(keepdims=True)(x)
    return tf.keras.Model(pixels, layers.Dense(10)(x), name=name)


def audit(path, expected):
    raw = (path / "model.tflite").read_bytes()
    model = fb.Model.GetRootAsModel(raw, 0)
    assert model.SubgraphsLength() == 1
    subgraph = model.Subgraphs(0)
    means = []
    for index in range(subgraph.OperatorsLength()):
        node = subgraph.Operators(index)
        opcode = model.OperatorCodes(node.OpcodeIndex())
        code = max(opcode.BuiltinCode(), opcode.DeprecatedBuiltinCode())
        if code != fb.BuiltinOperator.MEAN:
            continue
        source, axes = [subgraph.Tensors(node.Inputs(i)) for i in range(2)]
        target = subgraph.Tensors(node.Outputs(0))
        shape = source.ShapeAsNumpy().tolist()
        assert shape == [1, *expected], (path, shape)
        assert target.ShapeAsNumpy().tolist() == [1, 1, 1, expected[-1]]
        assert source.Type() == target.Type() == fb.TensorType.INT8
        assert axes.Type() == fb.TensorType.INT32 and axes.ShapeAsNumpy().tolist() == [2]
        values = np.frombuffer(model.Buffers(axes.Buffer()).DataAsNumpy(), dtype="<i4").tolist()
        assert sorted(values) == [1, 2]
        opts = node.BuiltinOptions()
        reduce = fb.ReducerOptions()
        reduce.Init(opts.Bytes, opts.Pos)
        assert reduce.KeepDims()
        scales = [float(t.Quantization().Scale(0)) for t in (source, target)]
        zeros = [int(t.Quantization().ZeroPoint(0)) for t in (source, target)]
        assert all(t.Quantization().ScaleLength() == t.Quantization().ZeroPointLength() == 1
                   for t in (source, target))
        means.append({"input_shape": shape, "axes": values, "keep_dims": True,
                      "input_scale": scales[0], "output_scale": scales[1],
                      "input_zero_point": zeros[0], "output_zero_point": zeros[1]})
    assert len(means) == 1
    assert not any(subgraph.Tensors(i).Type() == fb.TensorType.FLOAT32
                   for i in range(subgraph.TensorsLength()))
    return means[0]


def freeze_extra_cases(name, model_dir, test_images):
    raw = (model_dir / "model.tflite").read_bytes()
    interpreter = tf.lite.Interpreter(model_content=raw, num_threads=1,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
    interpreter.allocate_tensors()
    [input_details] = interpreter.get_input_details()
    [output_details] = interpreter.get_output_details()
    assert input_details["dtype"] == output_details["dtype"] == np.int8
    shape = input_details["shape"]
    scale, zero = input_details["quantization"]
    rng = np.random.default_rng(EXTRA_SEED)
    constants = sorted({-128, 0, int(zero), 127})
    cases = [(f"constant_{value}", np.full(shape, value, dtype=np.int8))
             for value in constants]
    checker = np.indices(shape).sum(axis=0) % 2
    cases.append(("checkerboard", np.where(checker, -128, 127).astype(np.int8)))
    for index in range(3):
        cases.append((f"random_{index}", rng.integers(-128, 128, shape, dtype=np.int8)))
    for index in range(1, 6):
        sample = np.clip(np.rint(test_images[index:index + 1] / scale) + zero, -128, 127)
        cases.append((f"cifar10_test_{index}", sample.astype(np.int8)))

    packed = bytearray()
    metadata = []
    for label, case in cases:
        raw_case = case.tobytes()
        assert raw_case != (model_dir / "input.bin").read_bytes()
        assert raw_case not in [entry[1].tobytes() for entry in cases if entry[0] != label]
        interpreter.set_tensor(input_details["index"], case)
        interpreter.invoke()
        metadata.append({"label": label, "sha256": hashlib.sha256(raw_case).hexdigest(),
                         "desktop_reference_output_hex": interpreter.get_tensor(output_details["index"]).tobytes().hex()})
        packed.extend(raw_case)
    target = EXTENSION / "models" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "correctness_inputs.bin").write_bytes(packed)
    (target / "correctness_inputs.json").write_text(json.dumps(
        {"seed": EXTRA_SEED, "input_size": int(np.prod(shape)), "cases": metadata}, indent=2) + "\n")


def int8_accuracy(model_dir, test_images, labels):
    interpreter = tf.lite.Interpreter(model_path=str(model_dir / "model.tflite"), num_threads=1)
    interpreter.allocate_tensors()
    [inp] = interpreter.get_input_details()
    [out] = interpreter.get_output_details()
    scale, zero = inp["quantization"]
    examples = np.clip(np.rint(test_images[:1000] / scale) + zero, -128, 127).astype(np.int8)
    correct = 0
    for index, example in enumerate(examples):
        interpreter.set_tensor(inp["index"], example[np.newaxis])
        interpreter.invoke()
        prediction = np.argmax(interpreter.get_tensor(out["index"]).reshape(-1))
        correct += int(prediction == labels[index])
    return {"test_indices": [0, len(examples) - 1], "correct": correct, "total": len(examples)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cifar-cache", type=Path, help="Keras cache root containing datasets/")
    parser.add_argument("--reuse-trained", action="store_true", help="Audit the existing frozen weights and generate extra inputs")
    args = parser.parse_args()
    if args.cifar_cache:
        cifar10.get_file = partial(cifar10.get_file, cache_dir=args.cifar_cache)
    random.seed(training.SEED)
    np.random.seed(training.SEED)
    tf.keras.utils.set_random_seed(training.SEED)
    tf.config.experimental.enable_op_determinism()
    (raw_train, y_train), (raw_test, y_test) = tf.keras.datasets.cifar10.load_data()
    train, test = (a.astype(np.float32) / 255.0 for a in (raw_train, raw_test))
    training.OUT = EXTENSION / "models"
    for name, shape in NEW_MODELS.items():
        if args.reuse_trained:
            continue
        # Retain the same seed even when one model is reproduced independently.
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(training.SEED)
        training.make_int8(build(name, shape[-1]), name, train, y_train.reshape(-1), test,
                           y_test.reshape(-1), train_samples=20000, epochs=2)
        inspect_model(training.OUT / name)

    manifest = {}
    for name in MODELS:
        if name in NEW_MODELS:
            model_dir, shape = training.OUT / name, NEW_MODELS[name]
        else:
            model_dir, shape = ORIGINAL / "models" / name, ORIGINAL_MEAN_SHAPES[name]
        manifest[name] = audit(model_dir, shape)
        freeze_extra_cases(name, model_dir, test)
        print("MEAN_GRAPH", name, manifest[name])
    (training.OUT / "mean_graphs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    accuracy = {name: int8_accuracy(training.OUT / name, test, y_test.reshape(-1)) for name in NEW_MODELS}
    (training.OUT / "int8_accuracy.json").write_text(json.dumps(accuracy, indent=2) + "\n")


if __name__ == "__main__":
    main()
