"""CPU ONNX inference for the U2-Net salient-object segmentation model.

Input/output normalization follows the published U2-Net/rembg pipeline.
The model file is installed separately and verified before deployment.
"""
from functools import lru_cache
import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

MODEL_PATH = Path(os.environ.get("WENSHI_MODEL_PATH", "/opt/wenshi/models/u2net.onnx"))
MODEL_NAME = MODEL_PATH.stem


@lru_cache(maxsize=1)
def session():
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(str(MODEL_PATH), options, providers=["CPUExecutionProvider"])


def warmup():
    model = session()
    data = np.zeros((1, 3, 320, 320), dtype=np.float32)
    model.run([model.get_outputs()[0].name], {model.get_inputs()[0].name: data})


def foreground_mask(image):
    rgb = np.asarray(image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS), dtype=np.float32)
    # Uniform images have no meaningful foreground; min/max normalization of
    # a nearly constant prediction would otherwise amplify noise into a mask.
    if np.max(np.std(rgb, axis=(0, 1))) < 1:
        raise ValueError("没有找到清晰主体，请选择纹样与背景有明显区别的照片。")
    rgb = rgb / max(float(rgb.max()), 1e-6)
    rgb = (rgb - np.array([.485, .456, .406], dtype=np.float32)) / np.array([.229, .224, .225], dtype=np.float32)
    tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32)
    model = session()
    prediction = model.run([model.get_outputs()[0].name], {model.get_inputs()[0].name: tensor})[0][0, 0]
    if not np.isfinite(prediction).all() or float(prediction.max()-prediction.min()) < .05:
        raise ValueError("AI 没有识别出清晰主体，请裁剪到纹样区域后重试。")
    normalized = (prediction-prediction.min()) / (prediction.max()-prediction.min())
    coverage = np.mean(normalized > .5)
    if coverage < .002 or coverage > .98:
        raise ValueError("AI 未分离出有效纹样，请更换照片或先裁剪主体。")
    mask = Image.fromarray(np.rint(np.clip(normalized, 0, 1)*255).astype(np.uint8))
    return mask.resize(image.size, Image.Resampling.LANCZOS)
