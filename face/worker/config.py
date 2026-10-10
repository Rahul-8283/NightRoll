"""Configuration settings for the Face Worker service."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or face/.env."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server binding
    FACE_HOST: str = "0.0.0.0"
    FACE_PORT: int = 8100
    FACE_WORKER_TOKEN: str = ""

    # Model settings
    FACE_MODEL_NAME: str = "buffalo_l"
    FACE_MODEL_DIR: str = "./models"
    ANTISPOOF_MODEL_PATH: str = "./models/antispoof.onnx"
    MODEL_VERSION: str = "buffalo_l-1"

    # Supabase (Server-side service credentials)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    FRAMES_BUCKET: str = "frames"
    FRAME_RETENTION_HOURS: int = 24

    # Quality & Detection Floors (provisional, tuned in Phase 13)
    FACE_MIN_SIZE: int = 112  # Minimum box dimension in pixels
    BLUR_THRESHOLD: float = 75.0  # Laplacian variance floor
    LIGHT_MIN: float = 35.0  # Minimum mean grayscale brightness
    LIGHT_MAX: float = 230.0  # Maximum mean grayscale brightness
    MAX_POSE_YAW: float = 30.0  # Head turn limit in degrees
    MAX_POSE_PITCH: float = 25.0  # Head tilt limit in degrees
    MAX_POSE_ROLL: float = 25.0  # Head roll limit in degrees

    # Enrollment consistency check
    ENROLL_MIN_AGREEMENT: float = 0.55  # Minimum pairwise cosine similarity across frames
    ENROLL_MIN_VALID_FRAMES: int = 3  # Minimum frames that must pass quality


settings = Settings()
