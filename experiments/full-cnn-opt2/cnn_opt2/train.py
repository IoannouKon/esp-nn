"""Train, calibrate, and freeze the MNIST classifier and fixed test input."""
import hashlib
import json
import os
from pathlib import Path

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as schema

ROOT = Path(__file__).resolve().parent
SEED = 1729
BATCH = 128
EPOCHS = 4

tf.config.threading.set_intra_op_parallelism_threads(3)
tf.config.threading.set_inter_op_parallelism_threads(1)
tf.keras.utils.set_random_seed(SEED)
tf.config.experimental.enable_op_determinism()

(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
x_train = x_train[..., None].astype(np.float32) / 255
x_test = x_test[..., None].astype(np.float32) / 255

model = tf.keras.Sequential([
    tf.keras.layers.Input((28, 28, 1)),
    tf.keras.layers.Conv2D(16, 3, strides=2, padding="same", activation="relu"),
    tf.keras.layers.MaxPooling2D(3, strides=1, padding="same"),
    tf.keras.layers.Conv2D(32, 3, strides=2, padding="same", activation="relu"),
    tf.keras.layers.MaxPooling2D(5, strides=1, padding="same"),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(10),
])
model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)
model.summary()
model.fit(x_train, y_train, epochs=EPOCHS, batch_size=BATCH, verbose=2)
_, float_accuracy = model.evaluate(x_test, y_test, verbose=0)

def representative_dataset():
    for index in np.random.default_rng(SEED).choice(len(x_train), 256, replace=False):
        yield [x_train[index:index + 1]]

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8
model_bytes = converter.convert()

graph = schema.Model.GetRootAsModel(model_bytes, 0)
subgraph = graph.Subgraphs(0)
pool_specs = []
for i in range(subgraph.OperatorsLength()):
    op = subgraph.Operators(i)
    if graph.OperatorCodes(op.OpcodeIndex()).BuiltinCode() != schema.BuiltinOperator.MAX_POOL_2D:
        continue
    options = op.BuiltinOptions()
    pool = schema.Pool2DOptions()
    pool.Init(options.Bytes, options.Pos)
    tensor = subgraph.Tensors(op.Inputs(0))
    output = subgraph.Tensors(op.Outputs(0))
    shape = tensor.ShapeAsNumpy().tolist()
    assert tensor.Type() == output.Type() == schema.TensorType.INT8
    assert shape == output.ShapeAsNumpy().tolist()
    assert pool.Padding() == schema.Padding.SAME
    assert pool.StrideH() == pool.StrideW() == 1
    assert pool.FilterHeight() == pool.FilterWidth() in (3, 5)
    assert shape[-1] % 16 == 0
    pool_specs.append({"shape": shape, "filter": pool.FilterWidth(), "stride": 1, "padding": "SAME"})
assert len(pool_specs) == 2

interpreter = tf.lite.Interpreter(model_content=model_bytes, num_threads=1)
interpreter.allocate_tensors()
input_info, = interpreter.get_input_details()
output_info, = interpreter.get_output_details()
assert input_info["dtype"] == output_info["dtype"] == np.int8
assert input_info["shape"].tolist() == [1, 28, 28, 1]
assert output_info["shape"].tolist() == [1, 10]
scale, zero_point = input_info["quantization"]
test_inputs = np.clip(np.rint(x_test / scale) + zero_point, -128, 127).astype(np.int8)
correct = 0
first_output = None
for index, label in enumerate(y_test):
    interpreter.set_tensor(input_info["index"], test_inputs[index:index + 1])
    interpreter.invoke()
    output = interpreter.get_tensor(output_info["index"])[0]
    correct += int(output.argmax() == label)
    if index == 0:
        first_output = output.tolist()

fixed_input = test_inputs[0].tobytes()
(ROOT / "main/model.tflite").write_bytes(model_bytes)
(ROOT / "main/input.bin").write_bytes(fixed_input)
metadata = {
    "tensorflow": tf.__version__, "seed": SEED, "epochs": EPOCHS, "batch_size": BATCH,
    "train_samples": len(x_train), "test_samples": len(x_test),
    "float_test_accuracy": float(float_accuracy), "int8_test_accuracy": correct / len(x_test),
    "int8_test_correct": correct, "max_pool_layers": pool_specs,
    "fixed_test_index": 0, "fixed_label": int(y_test[0]), "host_output": first_output,
    "input_quantization": input_info["quantization"],
    "output_quantization": output_info["quantization"],
    "model_sha256": hashlib.sha256(model_bytes).hexdigest(),
    "input_sha256": hashlib.sha256(fixed_input).hexdigest(),
}
report = json.dumps(metadata, indent=2) + "\n"
(ROOT / "training_result.json").write_text(report)
print(report)
