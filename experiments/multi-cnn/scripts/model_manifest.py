#!/usr/bin/env python3
"""Inventory exact graph operators and verify each frozen input on host TFLite."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as fb

root = Path(__file__).resolve().parents[1]
models = root / "models"
ops = {v: k for k, v in vars(fb.BuiltinOperator).items() if k.isupper()}
types = {v: k for k, v in vars(fb.TensorType).items() if k.isupper()}
cifar = json.loads((models / "generated_manifest.json").read_text())
sources = {
    "mnist_fixed": [
        "https://github.com/IoannouKon/esp-nn/tree/edb003c6770491abb74766835f4c803b9d4f5a20",
        "User's frozen trained MNIST model, exact model and input from the benchmark commit.",
    ],
    "person_detection": [
        "https://github.com/espressif/esp-tflite-micro/tree/df8722334a80ceabc609c1e72968f417cd9437f1/examples/person_detection",
        "Espressif's Apache-2.0 example. Exact bundled model and sample image0 with XOR 0x80.",
    ],
    "mobilenet_v2": [
        "https://huggingface.co/litert-community/MobileNet-v2",
        "Static channelwise INT8 TorchVision checkpoint. Model card does not give a separate weights license. "
        "CIFAR-10 test image 0, RGB bilinear 232 then center crop 224, ImageNet channel normalization, "
        "NCHW and model input quantization.",
    ],
    "mobilenet_v3_small": [
        "https://huggingface.co/litert-community/MobileNet-v3-small/commit/77f13855abb1d843015ff3605e5748b960ffe7dd",
        "Historical static channelwise INT8 TorchVision checkpoint. Provider later withdrew this export "
        "due to poor accuracy. No accuracy inference is drawn. Preprocessed the same way as MobileNetV2.",
    ],
    "efficientnet_lite0": [
        "https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/int8/latest/efficientnet_lite0.tflite",
        "Google MediaPipe's ImageNet EfficientNet-Lite0, UINT8 interface with INT8 compute, "
        "CIFAR-10 image 0 resized to 224x224 RGB UINT8 as used by the ImageClassifier input interface.",
    ],
}

def digest(data):
    return sha256(data).hexdigest()

def shape(t):
    return [t.Shape(i) for i in range(t.ShapeLength())]

def tensor(t):
    q = t.Quantization()
    return {"shape": shape(t), "dtype": types[t.Type()],
            "scale": [q.Scale(i) for i in range(q.ScaleLength())] if q else [],
            "zero_point": [q.ZeroPoint(i) for i in range(q.ZeroPointLength())] if q else []}

manifest = {}
for path in sorted(models.glob("*/model.tflite")):
    name = path.parent.name
    raw = path.read_bytes()
    data = (path.parent / "input.bin").read_bytes()
    validation_path = path.parent / "validation.bin"
    validation = validation_path.read_bytes() if validation_path.exists() else b""
    model = fb.Model.GetRootAsModel(raw, 0)
    g = model.Subgraphs(0)
    op_info = []
    for i in range(g.OperatorsLength()):
        op = g.Operators(i)
        code = model.OperatorCodes(op.OpcodeIndex())
        o = ops.get(max(code.BuiltinCode(), code.DeprecatedBuiltinCode()), "UNKNOWN")
        info = {"op": o, "version": code.Version()}
        if op.InputsLength() and op.Inputs(0) >= 0:
            info["input_shape"] = shape(g.Tensors(op.Inputs(0)))
        if o == "MAX_POOL_2D":
            bo = op.BuiltinOptions()
            pool = fb.Pool2DOptions()
            pool.Init(bo.Bytes, bo.Pos)
            info.update(filter=[pool.FilterHeight(), pool.FilterWidth()],
                        stride=[pool.StrideH(), pool.StrideW()], same=pool.Padding() == fb.Padding.SAME)
        if o == "MEAN":
            axis = g.Tensors(op.Inputs(1))
            axis_raw = model.Buffers(axis.Buffer()).DataAsNumpy()
            info["axes"] = np.frombuffer(axis_raw, dtype="<i4").tolist() if isinstance(axis_raw, np.ndarray) else None
            bo = op.BuiltinOptions()
            opt = fb.ReducerOptions()
            opt.Init(bo.Bytes, bo.Pos)
            info["keep_dims"] = bool(opt.KeepDims())
        op_info.append(info)
    src, detail = sources.get(name, ("https://www.cs.toronto.edu/~kriz/cifar.html",
        "Kit custom CNN. TensorFlow 2.15.1, 1 epoch, 12000 samples, seed 1729, Adam, "
        "128 calibration images, full integer TFLite quantization. Fixed test image 0."))
    result = {"source": src, "source_detail": detail, "schema_version": model.Version(),
              "model_bytes": len(raw), "model_sha256": digest(raw), "input_bytes": len(data),
              "input_sha256": digest(data), "input": tensor(g.Tensors(g.Inputs(0))),
              "output": tensor(g.Tensors(g.Outputs(0))), "operators": op_info,
              "operator_counts": dict(Counter(o["op"] for o in op_info)),
              "training_and_architecture": cifar.get(name),
              "validation_input_sha256": [digest(validation[i:i+len(data)])
                                          for i in range(0, len(validation), len(data))]}
    for j, resolver in (("host_tflite", tf.lite.experimental.OpResolverType.BUILTIN),
                        ("host_reference", tf.lite.experimental.OpResolverType.BUILTIN_REF)):
        try:
            t = tf.lite.Interpreter(model_content=raw, num_threads=1, experimental_op_resolver_type=resolver)
            t.allocate_tensors()
            i, = t.get_input_details()
            out, = t.get_output_details()
            outputs = []
            for sample in [data] + [validation[k:k+len(data)] for k in range(0, len(validation), len(data))]:
                t.set_tensor(i["index"], np.frombuffer(sample, dtype=i["dtype"]).reshape(i["shape"]))
                t.invoke()
                outputs.append(t.get_tensor(out["index"]).tobytes().hex())
            result[j] = {"outputs_hex": outputs, "tensorflow_version": tf.__version__}
        except (RuntimeError, ValueError) as error:
            result[j] = {"error": str(error)}
    manifest[name] = result
    print(name, result["input"], result["operator_counts"],
          ["OK" if "error" not in result[k] else "ERROR" for k in ("host_tflite", "host_reference")])
(root / "results/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
