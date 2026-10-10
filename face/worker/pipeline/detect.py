"""Face detection, quality evaluation, and head pose estimation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import cv2
import numpy as np

from worker.config import settings
from worker.schemas import FrameIssue, HeadPose

# Canonical 3D facial landmark model points for solvePnP pose estimation
# Order: Left Eye, Right Eye, Nose Tip, Left Mouth Corner, Right Mouth Corner
CANONICAL_3D_FACE = np.array([
    [-30.0, 30.0, -30.0],   # Left eye
    [30.0, 30.0, -30.0],    # Right eye
    [0.0, 0.0, 0.0],        # Nose tip
    [-20.0, -35.0, -25.0],  # Left mouth corner
    [20.0, -35.0, -25.0],   # Right mouth corner
], dtype=np.float64)


@dataclass
class QualityResult:
    """Result of quality and detection evaluation on a single frame."""
    valid: bool
    issues: list[FrameIssue]
    face: Any | None
    head_pose: HeadPose
    img: np.ndarray | None


def decode_image(image_bytes: bytes) -> np.ndarray | None:
    """Decode raw bytes (JPEG/PNG) to an OpenCV BGR numpy array."""
    if not image_bytes or len(image_bytes) < 32:
        return None
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def calculate_blur_score(gray_img: np.ndarray) -> float:
    """Compute variance of the Laplacian as a measure of sharpness."""
    return float(cv2.Laplacian(gray_img, cv2.CV_64F).var())


def calculate_lighting_score(gray_img: np.ndarray) -> float:
    """Compute mean grayscale brightness."""
    return float(np.mean(gray_img))


def estimate_head_pose(face: Any, img_shape: tuple[int, int]) -> HeadPose:
    """Estimate head orientation (pitch, yaw, roll) in degrees."""
    # Check if InsightFace already estimated pose
    if hasattr(face, "pose") and face.pose is not None:
        try:
            p = face.pose
            if len(p) >= 3:
                return HeadPose(pitch=float(p[0]), yaw=float(p[1]), roll=float(p[2]))
        except Exception:
            pass

    # Fallback to solvePnP using 5 standard landmarks (kps)
    if hasattr(face, "kps") and face.kps is not None and len(face.kps) >= 5:
        try:
            h, w = img_shape
            focal_length = w
            center = (w / 2.0, h / 2.0)
            camera_matrix = np.array(
                [[focal_length, 0, center[0]],
                 [0, focal_length, center[1]],
                 [0, 0, 1]], dtype=np.float64
            )
            dist_coeffs = np.zeros((4, 1), dtype=np.float64)
            image_points = np.array(face.kps[:5], dtype=np.float64)

            success, rot_vec, _ = cv2.solvePnP(
                CANONICAL_3D_FACE, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
            )
            if success:
                rmat, _ = cv2.Rodrigues(rot_vec)
                # Compute Euler angles from rotation matrix
                sy = np.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
                singular = sy < 1e-6
                if not singular:
                    pitch = np.arctan2(rmat[2, 1], rmat[2, 2])
                    yaw = np.arctan2(-rmat[2, 0], sy)
                    roll = np.arctan2(rmat[1, 0], rmat[0, 0])
                else:
                    pitch = np.arctan2(-rmat[1, 2], rmat[1, 1])
                    yaw = np.arctan2(-rmat[2, 0], sy)
                    roll = 0.0

                return HeadPose(
                    pitch=float(np.degrees(pitch)),
                    yaw=float(np.degrees(yaw)),
                    roll=float(np.degrees(roll)),
                )
        except Exception:
            pass

    return HeadPose(pitch=0.0, yaw=0.0, roll=0.0)


def evaluate_frame(
    frame_index: int,
    image_bytes: bytes,
    face_app: Any | None,
    require_neutral_pose: bool = True,
) -> QualityResult:
    """Run all quality checks on a single frame.

    Checks:
    1. Decoding (BAD_IMAGE)
    2. Face detection count (NO_FACE, MULTIPLE_FACES)
    3. Face bounding box size (FACE_TOO_SMALL)
    4. Sharpness / blur floor (TOO_BLURRY)
    5. Illumination range (BAD_LIGHTING)
    6. Head turn angle (BAD_POSE)
    """
    issues: list[FrameIssue] = []

    # 1. Decode image
    img = decode_image(image_bytes)
    if img is None:
        issues.append(FrameIssue(frame_index=frame_index, code="BAD_IMAGE", detail="Corrupted or unreadable image"))
        return QualityResult(valid=False, issues=issues, face=None, head_pose=HeadPose(pitch=0, yaw=0, roll=0), img=None)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Blur / sharpness check
    blur_score = calculate_blur_score(gray)
    if blur_score < settings.BLUR_THRESHOLD:
        issues.append(
            FrameIssue(
                frame_index=frame_index,
                code="TOO_BLURRY",
                detail=f"Blur score {blur_score:.1f} is below floor {settings.BLUR_THRESHOLD}",
            )
        )

    # 3. Lighting check
    light_score = calculate_lighting_score(gray)
    if not (settings.LIGHT_MIN <= light_score <= settings.LIGHT_MAX):
        issues.append(
            FrameIssue(
                frame_index=frame_index,
                code="BAD_LIGHTING",
                detail=f"Mean brightness {light_score:.1f} outside range [{settings.LIGHT_MIN}, {settings.LIGHT_MAX}]",
            )
        )

    # 4. Face detection
    if face_app is None:
        # Mock / offline testing mode when model is not initialized
        head_pose = HeadPose(pitch=0.0, yaw=0.0, roll=0.0)
        return QualityResult(
            valid=len(issues) == 0,
            issues=issues,
            face={"bbox": [0, 0, 150, 150], "embedding": np.ones(512) / np.sqrt(512)},
            head_pose=head_pose,
            img=img,
        )

    faces = face_app.get(img)

    if len(faces) == 0:
        issues.append(FrameIssue(frame_index=frame_index, code="NO_FACE", detail="No face detected in frame"))
        return QualityResult(valid=False, issues=issues, face=None, head_pose=HeadPose(pitch=0, yaw=0, roll=0), img=img)

    if len(faces) > 1:
        issues.append(FrameIssue(frame_index=frame_index, code="MULTIPLE_FACES", detail=f"Found {len(faces)} faces"))
        return QualityResult(valid=False, issues=issues, face=None, head_pose=HeadPose(pitch=0, yaw=0, roll=0), img=img)

    face = faces[0]

    # 5. Face size check
    bbox = face.bbox.astype(int)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    short_side = min(w, h)
    if short_side < settings.FACE_MIN_SIZE:
        issues.append(
            FrameIssue(
                frame_index=frame_index,
                code="FACE_TOO_SMALL",
                detail=f"Face short side {short_side}px is below minimum {settings.FACE_MIN_SIZE}px",
            )
        )

    # 6. Pose estimation & pose check
    head_pose = estimate_head_pose(face, (img.shape[0], img.shape[1]))

    if require_neutral_pose:
        if (
            abs(head_pose.yaw) > settings.MAX_POSE_YAW
            or abs(head_pose.pitch) > settings.MAX_POSE_PITCH
            or abs(head_pose.roll) > settings.MAX_POSE_ROLL
        ):
            issues.append(
                FrameIssue(
                    frame_index=frame_index,
                    code="BAD_POSE",
                    detail=f"Head pose (yaw={head_pose.yaw:.1f}°, pitch={head_pose.pitch:.1f}°, roll={head_pose.roll:.1f}°) exceeds limits",
                )
            )

    is_valid = len(issues) == 0
    return QualityResult(valid=is_valid, issues=issues, face=face, head_pose=head_pose, img=img)
