#!/usr/bin/env python3
"""Create reproducible INT8 TFLite CNN candidates and inputs on the AGENT HOST.
This is a preparation script, not a claim that every graph fits TFLM/ESP32-S3.
"""
import argparse, hashlib, json, random, os
from pathlib import Path
import numpy as np
import tensorflow as tf

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'models'
SEED = 1729


def op_list(data):
    from tensorflow.lite.python import schema_py_generated as fb
    g = fb.Model.GetRootAsModel(data, 0)
    sg = g.Subgraphs(0)
    out = []
    for i in range(sg.OperatorsLength()):
        op = sg.Operators(i)
        code = g.OperatorCodes(op.OpcodeIndex()).BuiltinCode()
        try: name = next((k for k,v in vars(fb.BuiltinOperator).items() if k.isupper() and v==code),str(code))
        except AttributeError:
            name = str(code)
        if not isinstance(name, str): name = str(name)
        d = {'name': name, 'inputs': []}
        for k in range(op.InputsLength()):
            ix = op.Inputs(k)
            if ix >= 0:
                t = sg.Tensors(ix)
                d['inputs'].append(t.ShapeAsNumpy().tolist())
        out.append(d)
    return out


def build(kind, width=32):
    k = tf.keras
    inp = k.Input((width, width, 3), name='pixels')
    x = k.layers.Conv2D(16, 3, strides=2, padding='same', activation='relu')(inp)
    if kind in ('max3','max5','both','depthwise_both'):
        x = k.layers.MaxPooling2D(5 if kind == 'max5' else 3, strides=1, padding='same')(x)
    if kind == 'depthwise_both':
        x = k.layers.DepthwiseConv2D(3, padding='same', activation='relu')(x)
        x = k.layers.Conv2D(32,1,activation='relu')(x)
    else:
        x = k.layers.Conv2D(32, 3, strides=2, padding='same', activation='relu')(x)
    if kind == 'both':
        x = k.layers.MaxPooling2D(5, strides=1, padding='same')(x)
    if kind == 'avg_control':
        x = k.layers.AveragePooling2D(3, strides=1, padding='same')(x)
    if kind in ('mean_only','both','depthwise_both'):
        x = k.layers.GlobalAveragePooling2D(keepdims=True)(x)
    else:
        x = k.layers.Flatten()(x)
    logits = k.layers.Dense(10)(x)
    return k.Model(inp, logits, name=kind)


def make_int8(model, name, x_train, y_train, x_test, y_test, train_samples, epochs):
    model.compile(optimizer='adam', loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), metrics=['accuracy'])
    model.fit(x_train[:train_samples], y_train[:train_samples], batch_size=128, epochs=epochs, verbose=2)
    float_acc = float(model.evaluate(x_test[:1000], y_test[:1000], verbose=0)[1])
    rng = np.random.default_rng(SEED)
    inds = rng.choice(len(x_train), size=min(128,len(x_train)), replace=False)
    def rep():
        for i in inds:
            yield [x_train[i:i+1]]
    # Export fixed batch-one inputs so TFLM can allocate the original graph.
    signature = tf.TensorSpec((1, *model.input_shape[1:]), tf.float32, name='pixels')
    @tf.function(input_signature=[signature])
    def inference(pixels):
        return model(pixels, training=False)
    conv = tf.lite.TFLiteConverter.from_concrete_functions(
        [inference.get_concrete_function()], model)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    data = conv.convert()
    interp = tf.lite.Interpreter(model_content=data, num_threads=1)
    interp.allocate_tensors()
    a, = interp.get_input_details()
    z, = interp.get_output_details()
    assert a['dtype'] == z['dtype'] == np.int8
    scale, zp = a['quantization']
    fixed = np.clip(np.rint(x_test[0:1] / scale) + zp, -128, 127).astype(np.int8)
    interp.set_tensor(a['index'], fixed)
    interp.invoke()
    host_logits = interp.get_tensor(z['index']).flatten().tolist()
    d = OUT / name
    d.mkdir(parents=True,exist_ok=True)
    (d/'model.tflite').write_bytes(data)
    (d/'input.bin').write_bytes(fixed.tobytes())
    meta = {
        'name':name,'origin':'custom CIFAR-10 CNN; trained from scratch',
        'training_epochs':epochs,'train_samples':train_samples,'test_accuracy_1000':float_acc,
        'input_shape':a['shape'].tolist(),'output_shape':z['shape'].tolist(),
        'input_scale':float(scale),'input_zero_point':int(zp),'host_output':host_logits,
        'ops':op_list(data), 'dataset':'CIFAR-10', 'fixed_test_index':0,
        'model_sha256':hashlib.sha256(data).hexdigest(),
        'input_sha256':hashlib.sha256(fixed.tobytes()).hexdigest(),
        'note':'Full-model correctness on the board must be checked across builds. Built-in TFLM MEAN is not ESP-NN MEAN.'}
    (d/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('GENERATED',name,'model_size',len(data),'ops',[o['name'] for o in meta['ops']])
    return meta

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs',type=int,default=1)
    ap.add_argument('--train-samples',type=int,default=12000)
    ap.add_argument('--only', nargs='*', default=['max3','max5','mean_only','both','depthwise_both','avg_control','neutral_control'])
    args = ap.parse_args()
    random.seed(SEED); np.random.seed(SEED); tf.keras.utils.set_random_seed(SEED)
    (raw_x, y_train), (raw_xt, y_test) = tf.keras.datasets.cifar10.load_data()
    x_train=raw_x.astype('float32')/255.0
    x_test=raw_xt.astype('float32')/255.0
    y_train=y_train.reshape(-1);y_test=y_test.reshape(-1)
    result={}
    for name in args.only:
        tf.keras.backend.clear_session()
        result[name]=make_int8(build(name),name,x_train,y_train,x_test,y_test,args.train_samples,args.epochs)
    (OUT/'generated_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
