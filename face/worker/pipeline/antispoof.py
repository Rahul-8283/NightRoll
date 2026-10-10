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

    def preprocess_crop(self, img: np.ndarray, bbox: list[int] | np.ndarray) -> np.ndarray:
        """Crop and prepare face image according to MiniFASNet specifications."""
        h_img, w_img = img.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]

        w_box = x2 - x1
        h_box = y2 - y1

        # Center point
        cx = x1 + w_box / 2.0
        cy = y1 + h_box / 2.0

        # Scale bbox by model ratio
        max_side = max(w_box, h_box)
        crop_size = max_side * self.scale_ratio

        nx1 = max(0, int(cx - crop_size / 2.0))
        ny1 = max(0, int(cy - crop_size / 2.0))
        nx2 = min(w_img, int(cx + crop_size / 2.0))
        ny2 = min(h_img, int(cy + crop_size / 2.0))

        cropped = img[ny1:ny2, nx1:nx2]
        if cropped.size == 0:
            cropped = img

        target_h, target_w = 80, 80
        if len(self.input_shape) >= 4 and isinstance(self.input_shape[2], int) and isinstance(self.input_shape[3], int):
            target_h, target_w = self.input_shape[2], self.input_shape[3]

        resized = cv2.resize(cropped, (target_w, target_h))
        # Convert BGR to RGB and normalize to [0, 1] or standard tensor format
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
        # Transpose HWC to CHW
        chw = np.transpose(rgb, (2, 0, 1))
        # Add batch dimension NCHW
        tensor = np.expand_dims(chw, axis=0)
        return tensor

    def score(self, img: np.ndarray, bbox: list[int] | np.ndarray) -> float:
        """Predict real-face probability for a face bounding box.

        Returns float between 0.0 (spoof) and 1.0 (real).
        """
        if not self.is_available or self.session is None:
            # If model is unavailable, return 0.0 so liveness fails safely
            return 0.0

        try:
            tensor = self.preprocess_crop(img, bbox)
            outputs = self.session.run([self.output_name], {self.input_name: tensor})
            raw = outputs[0]  # shape: (1, num_classes)

            # Softmax
            exp_scores = np.exp(raw - np.max(raw))
            probs = exp_scores / np.sum(exp_scores)

            # MiniFASNet usually outputs: class 0 is spoof/background, class 1 is real face
            # Or 3 classes: [fake_type1, fake_type2, real]
            if probs.shape[-1] == 2:
                real_score = float(probs[0, 1])
            elif probs.shape[-1] >= 3:
                # If 3 classes, last class is typically real
                real_score = float(probs[0, -1])
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
