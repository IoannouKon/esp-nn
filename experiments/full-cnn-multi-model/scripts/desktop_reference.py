#!/usr/bin/env python3
"""Independent desktop-reference outputs for the same frozen samples."""
import hashlib
import json
from pathlib import Path

import numpy as np
import tensorflow as tf

kit = Path(__file__).resolve().parents[1]
result = {}
for path in sorted((kit / "models").glob("*/model.tflite")):
    directory = path.parent
    out = {"model_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    try:
        interpreter = tf.lite.Interpreter(
            model_path=str(path), num_threads=1,
            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        interpreter.allocate_tensors()
        [i] = interpreter.get_input_details()
        [o] = interpreter.get_output_details()
        raw = (directory / "input.bin").read_bytes()
        interpreter.set_tensor(i["index"], np.frombuffer(raw, dtype=np.int8).reshape(i["shape"]))
        interpreter.invoke()
        out["output_hex"] = interpreter.get_tensor(o["index"]).tobytes().hex()
        out["input_sha256"] = hashlib.sha256(raw).hexdigest()
    except (ValueError, RuntimeError) as error:
        out["error"] = str(error)
    result[directory.name] = out
(kit / "results" / "desktop-reference.json").write_text(json.dumps(result, indent=2) + "\n")
