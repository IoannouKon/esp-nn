#!/usr/bin/env python3
"""Resolve batch-one FlatBuffer shape placeholders for the supplied Dense lowering."""
from hashlib import sha256
import json
from pathlib import Path
import struct

import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as fb

root = Path(__file__).resolve().parents[1]

def runtime(content):
    t = tf.lite.Interpreter(model_content=content, num_threads=1,
                            experimental_preserve_all_tensors=True,
                            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
    t.allocate_tensors()
    return t

def invoke(t, raw):
    i, = t.get_input_details()
    o, = t.get_output_details()
    t.set_tensor(i["index"], np.frombuffer(raw, dtype=i["dtype"]).reshape(i["shape"]))
    t.invoke()
    return t.get_tensor(o["index"]).tobytes()

records = {}
for name in ("mean_only", "both", "depthwise_both"):
    d = root / "models" / name
    m = d / "model.tflite"
    dynamic = d / "model-keras-dynamic.tflite"
    if not dynamic.exists():
        dynamic.write_bytes(m.read_bytes())
    original = dynamic.read_bytes()
    fixed = bytearray(original)
    data = (d / "input.bin").read_bytes()
    alt = (d / "validation.bin").read_bytes()
    images = [data] + [alt[i:i+len(data)] for i in range(0, len(alt), len(data))]
    interpreter = runtime(original)
    baseline = [invoke(interpreter, sample) for sample in images]
    graph = fb.Model.GetRootAsModel(original, 0).Subgraphs(0)
    detail = []
    for tensor in interpreter.get_tensor_details():
        if tensor["index"] >= graph.TensorsLength():
            continue
        table = graph.Tensors(tensor["index"])
        before = [table.Shape(i) for i in range(table.ShapeLength())]
        actual = tensor["shape"].tolist()
        if before == actual:
            continue
        assert len(before) == len(actual) == table.ShapeSignatureLength()
        assert all(a > 0 and (a == b or table.ShapeSignature(j) == -1)
                   for j, (b, a) in enumerate(zip(before, actual)))
        offset = table._tab.Vector(table._tab.Offset(4))
        assert struct.unpack_from("<" + "i" * len(before), original, offset) == tuple(before)
        struct.pack_into("<" + "i" * len(actual), fixed, offset, *actual)
        detail.append({"tensor": tensor["index"], "original_shape": before, "static_shape": actual,
                       "shape_vector_offset": offset})
    assert detail
    finalized = bytes(fixed)
    final_interpreter = runtime(finalized)
    assert [invoke(final_interpreter, sample) for sample in images] == baseline
    # Every node, weight, quantization parameter, signature and input is untouched.
    spans = {i for item in detail for i in range(item["shape_vector_offset"],
             item["shape_vector_offset"] + 4 * len(item["static_shape"]))}
    assert all(i in spans for i, (a, b) in enumerate(zip(original, finalized)) if a != b)
    m.write_bytes(finalized)
    records[name] = {"original_sha256": sha256(original).hexdigest(),
                     "final_sha256": sha256(finalized).hexdigest(),
                     "reference_inputs_exact": len(images), "changes": detail}
    print(name, records[name])
(root / "results" / "static_tensor_shapes.json").write_text(json.dumps(records, indent=2) + "\n")
