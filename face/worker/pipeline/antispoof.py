"""Anti-spoofing / liveness detection using ONNX Runtime."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger(__name__)


class AntiSpoofClassifier:
    """Classifies face crops as genuine (1.0) or presentation attack / screen / photo (0.0)."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.session: ort.InferenceSession | None = None
        self.input_name: str = ""
        self.output_name: str = ""
        self.input_shape: tuple[int, ...] = (1, 3, 80, 80)
        self.scale_ratio: float = 2.7
        self.is_available: bool = False

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str | Path) -> bool:
        """Load the ONNX model session."""
        path = Path(model_path)
        if not path.exists():
            logger.warning(f"Anti-spoof model file not found at {path}")
            self.is_available = False
            return False

        if ort is None:
            logger.warning("onnxruntime is not installed; anti-spoofing disabled")
            self.is_available = False
            return False

        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
            inputs = self.session.get_inputs()
            outputs = self.session.get_outputs()

            self.input_name = inputs[0].name
            self.output_name = outputs[0].name
            self.input_shape = tuple(inputs[0].shape) if inputs[0].shape else (1, 3, 80, 80)
            self.is_available = True
            logger.info(f"Loaded anti-spoof model from {path} (input: {self.input_name}, shape: {self.input_shape})")
            return True
        except Exception as e:
            logger.error(f"Failed to load anti-spoof model from {path}: {e}")
            self.session = None
            self.is_available = False
            return False

    def _crop_box(
        self, src_w: int, src_h: int, x: float, y: float, box_w: float, box_h: float
    ) -> tuple[int, int, int, int]:
        """Scale the face box by `scale_ratio`, then slide it back inside the frame.

        Ported from Silent-Face-Anti-Spoofing (`CropImage._get_new_box`). The box is shifted, not cut,
        at the image border, so the crop keeps the proportions the model was trained on.
        """
        scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, self.scale_ratio)
        new_w, new_h = box_w * scale, box_h * scale
        cx, cy = x + box_w / 2.0, y + box_h / 2.0
        left, top = cx - new_w / 2.0, cy - new_h / 2.0
        right, bottom = cx + new_w / 2.0, cy + new_h / 2.0
        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > src_w - 1:
            left -= right - src_w + 1
            right = src_w - 1
        if bottom > src_h - 1:
            top -= bottom - src_h + 1
            bottom = src_h - 1
        return int(left), int(top), int(right), int(bottom)

    def preprocess_crop(self, img: np.ndarray, bbox: list[int] | np.ndarray) -> np.ndarray:
        """Crop a BGR frame the way MiniFASNet was trained.

        The model expects BGR channel order and raw 0..255 float values (no scaling to 0..1).
        """
        h_img, w_img = img.shape[:2]
        x1, y1, x2, y2 = (float(v) for v in bbox[:4])
        box_w, box_h = x2 - x1, y2 - y1
        if box_w <= 1 or box_h <= 1:
            cropped = img
        else:
            left, top, right, bottom = self._crop_box(w_img, h_img, x1, y1, box_w, box_h)
            cropped = img[top : bottom + 1, left : right + 1]
            if cropped.size == 0:
                cropped = img

        target_h, target_w = 80, 80
        if len(self.input_shape) >= 4 and isinstance(self.input_shape[2], int) and isinstance(self.input_shape[3], int):
            target_h, target_w = self.input_shape[2], self.input_shape[3]

        resized = cv2.resize(cropped, (target_w, target_h)).astype(np.float32)
        chw = np.transpose(resized, (2, 0, 1))
        return np.expand_dims(chw, axis=0)

    def score(self, img: np.ndarray, bbox: list[int] | np.ndarray) -> float:
        """Probability that the face is a live person, from 0.0 (attack) to 1.0 (real)."""
        if not self.is_available or self.session is None:
            # If the model is unavailable, return 0.0 so liveness fails safely
            return 0.0

        try:
            tensor = self.preprocess_crop(img, bbox)
            raw = self.session.run([self.output_name], {self.input_name: tensor})[0]  # shape: (1, num_classes)

            exp_scores = np.exp(raw - np.max(raw))
            probs = exp_scores / np.sum(exp_scores)

            # MiniFASNetV2 has 3 classes: 0 = print attack, 1 = real face, 2 = screen replay.
            if probs.shape[-1] >= 2:
                real_score = float(probs[0, 1])
            else:
                real_score = float(probs[0, 0])

            return float(np.clip(real_score, 0.0, 1.0))
        except Exception as e:
            logger.error(f"Anti-spoof inference error: {e}")
            return 0.0


def calculate_median_antispoof(scores: list[float]) -> float:
    """Compute median anti-spoof score across evaluated frames."""
    if not scores:
        return 0.0
    return float(np.median(scores))
