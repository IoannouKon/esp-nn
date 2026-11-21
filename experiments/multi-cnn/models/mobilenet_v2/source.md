---
library_name: litert
tags:
  - vision
  - image-classification
datasets:
  - imagenet-1k
model-index:
  - name: MobileNet V2
    results:
      - task:
          type: image-classification
          name: Image Classification
        dataset:
          name: ImageNet-1k
          type: imagenet-1k
          config: default
          split: validation
        metrics:
          - name: Top 1 Accuracy (Full Precision)
            type: accuracy
            value: 0.7183
          - name: Top 5 Accuracy (Full Precision)
            type: accuracy
            value: 0.9031
          - name: Top 1 Accuracy (Dynamic Quantized wi8 afp32)
            type: accuracy
            value: 0.7183
          - name: Top 5 Accuracy (Dynamic Quantized wi8 afp32)
            type: accuracy
            value: 0.9031
---

# MobileNet V2

MobileNet V2 model pre-trained on ImageNet-1k at resolution 224x224. It was introduced in [MobileNetV2: Inverted Residuals and Linear Bottlenecks](https://arxiv.org/abs/1801.04381) by Mark Sandler, Andrew Howard, Menglong Zhu, Andrey Zhmoginov, Liang-Chieh Chen. 


## Model description

The model was converted from a checkpoint from PyTorch Vision. 

The source checkpoint has:    
acc@1 (on ImageNet-1K): 72.154%    
acc@5 (on ImageNet-1K): 90.822%    
num_params: 3,504,872    

The license information of the original model was missing.

## Available model files

| File | Description |
| --- | --- |
| `mobilenet_v2.tflite` | Full precision LiteRT/TFLite model. |
| `mobilenet_v2_dynamic_wi8_afp32.tflite` | Dynamic weight-only INT8 model with FP32 activations. |
| `mobilenet_v2_Google_Tensor_G5_apply_plugin.tflite` | AOT-compiled artifact for the Google Tensor G5 target. |
| `mobilenet_v2_int8_channelwise.tflite` | Static INT8 model with channelwise INT8 weights and asymmetric INT8 activations. |

## Quantization

`mobilenet_v2_int8_channelwise.tflite` was produced with the `STATIC_WI8_AI8` quantization recipe. Weights are signed INT8 and use symmetric channelwise quantization for weight tensors. Activations are signed INT8 with asymmetric quantization parameters.

## Compatibility

| File | CPU | GPU | NPU |
|---|---|---|---|
| `mobilenet_v2.tflite` | Supported | Supported | N/A |
| `mobilenet_v2_int8_channelwise.tflite` | Supported | Not supported | Qualcomm / MediaTek |

## Use

```python
#!/usr/bin/env python3
import argparse, json
import numpy as np
from PIL import Image
from huggingface_hub import hf_hub_download
from ai_edge_litert.compiled_model import CompiledModel

def preprocess(img: Image.Image) -> np.ndarray:
    img = img.convert("RGB")
    w, h = img.size
    s = 232
    if w < h:
        img = img.resize((s, int(h * s / w)), Image.BILINEAR)
    else:
        img = img.resize((int(w * s / h), s), Image.BILINEAR)
    left = int(round((img.size[0] - 224) / 2.0))
    top = int(round((img.size[1] - 224) / 2.0))
    img = img.crop((left, top, left + 224, top + 224))

    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
        [0.229, 0.224, 0.225], dtype=np.float32
    )
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    args = ap.parse_args()

    model_path = hf_hub_download("litert-community/MobileNet-v2", "mobilenet_v2.tflite")
    labels_path = hf_hub_download(
        "huggingface/label-files", "imagenet-1k-id2label.json", repo_type="dataset"
    )
    with open(labels_path, "r", encoding="utf-8") as f:
        id2label = {int(k): v for k, v in json.load(f).items()}

    img = Image.open(args.image)
    x = preprocess(img)

    model = CompiledModel.from_file(model_path)
    inp = model.create_input_buffers(0)
    out = model.create_output_buffers(0)

    inp[0].write(x)
    model.run_by_index(0, inp, out)

    req = model.get_output_buffer_requirements(0, 0)
    y = out[0].read(req["buffer_size"] // np.dtype(np.float32).itemsize, np.float32)

    pred = int(np.argmax(y))
    label = id2label.get(pred, f"class_{pred}")

    print(f"Top-1 class index: {pred}")
    print(f"Top-1 label: {label}")
if __name__ == "__main__":
    main()
```

### BibTeX entry and citation info

```bibtex
@inproceedings{mobilenetv22018,
  title={MobileNetV2: Inverted Residuals and Linear Bottlenecks},
  author={Mark Sandler and Andrew Howard and Menglong Zhu and Andrey Zhmoginov and Liang-Chieh Chen},
  booktitle={CVPR},
  year={2018}
}
```
