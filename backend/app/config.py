"""Application settings, loaded from backend/.env.

Every required value here must be set in the environment (see .env.example).
A missing value stops startup with a message naming it; settings are never
logged or printed in full (see `safe_field_names`).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", case_sensitive=True)

    # Runtime
    APP_ENV: str
    API_HOST: str
    API_PORT: int
    LOG_LEVEL: str = "info"
    TIMEZONE: str = "UTC"

    # Supabase (server side only)
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    DATABASE_URL: str
    REQUIRE_MFA: bool = True

    # Redis
    REDIS_URL: str

    # Face worker
    FACE_WORKER_URL: str
    FACE_WORKER_TOKEN: str

    # Google service account (Play Integrity decode)
    GOOGLE_APPLICATION_CREDENTIALS: str

    # Play Integrity
    PLAY_INTEGRITY_PACKAGE_NAME: str
    PLAY_INTEGRITY_ENFORCE: bool = False

    # Attendance window defaults
    WINDOW_DEFAULT_OPEN: str
    WINDOW_DEFAULT_CLOSE: str

    # Warden dashboard origins allowed to call the API (comma separated)
    DASHBOARD_ORIGINS: str = "http://localhost:5173"

    # Network gate
    NETWORK_VERIFY_MODE: str = "subnet"
    TRUSTED_PROXY_IPS: str = ""

    # Trust score (provisional, tuned in Phase 13)
    WEIGHT_FACE: float
    WEIGHT_FINGERPRINT: float
    WEIGHT_LIVENESS: float
    WEIGHT_OWN_AP: float
    WEIGHT_AP_AGREEMENT: float
    THRESHOLD_PRESENT: float
    THRESHOLD_REVIEW: float

    # Scorer thresholds (provisional, tuned in Phase 13). Scorers read these; no number lives in scorer code.
    FACE_SIM_LOW: float = 0.45
    FACE_SIM_HIGH: float = 0.50
    ANTISPOOF_MIN: float = 0.90
    HEAD_TURN_MIN_DEG: float = 15.0
    # Sign of the worker's yaw for a left turn. Confirm with real turned-head captures before the walk test.
    HEAD_TURN_LEFT_SIGN: int = -1
    OWN_AP_RSSI_LOW: float = -75.0
    OWN_AP_RSSI_HIGH: float = -55.0
    FP_NEIGHBOUR_LOW: float = 0.3
    FP_NEIGHBOUR_HIGH: float = 0.7
    FP_UNKNOWN_FREE: int = 2
    FP_UNKNOWN_STEP: float = 0.1
    FP_UNKNOWN_CAP: float = 0.5
    SCAN_STALE_MS: int = 30000
    AP_AGREEMENT_FULL_DB: float = 10.0
    AP_AGREEMENT_ZERO_DB: float = 25.0
    FACE_WORKER_TIMEOUT_SECONDS: float = 5.0

    @model_validator(mode="after")
    def _check_business_rules(self) -> Settings:
        total_weight = (
            self.WEIGHT_FACE
            + self.WEIGHT_FINGERPRINT
            + self.WEIGHT_LIVENESS
            + self.WEIGHT_OWN_AP
            + self.WEIGHT_AP_AGREEMENT
        )
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"fusion weights must sum to 1.0, got {total_weight}")

        if self.THRESHOLD_PRESENT <= self.THRESHOLD_REVIEW:
            raise ValueError(
                f"THRESHOLD_PRESENT ({self.THRESHOLD_PRESENT}) must be greater than "
                f"THRESHOLD_REVIEW ({self.THRESHOLD_REVIEW})"
            )

        ranges = [
            ("FACE_SIM_LOW", self.FACE_SIM_LOW, "FACE_SIM_HIGH", self.FACE_SIM_HIGH),
            ("OWN_AP_RSSI_LOW", self.OWN_AP_RSSI_LOW, "OWN_AP_RSSI_HIGH", self.OWN_AP_RSSI_HIGH),
            ("FP_NEIGHBOUR_LOW", self.FP_NEIGHBOUR_LOW, "FP_NEIGHBOUR_HIGH", self.FP_NEIGHBOUR_HIGH),
            ("AP_AGREEMENT_FULL_DB", self.AP_AGREEMENT_FULL_DB, "AP_AGREEMENT_ZERO_DB", self.AP_AGREEMENT_ZERO_DB),
        ]
        if self.HEAD_TURN_LEFT_SIGN not in (-1, 1):
            raise ValueError("HEAD_TURN_LEFT_SIGN must be -1 or 1")

        for low_name, low, high_name, high in ranges:
            if low >= high:
                raise ValueError(f"{low_name} ({low}) must be less than {high_name} ({high})")

        if not self.REDIS_URL.startswith("rediss://"):
            raise ValueError("REDIS_URL must use TLS (rediss://); a plain redis:// URL is refused")

        if self.NETWORK_VERIFY_MODE not in ("subnet", "controller", "radius", "off"):
            raise ValueError("NETWORK_VERIFY_MODE must be one of: subnet, controller, radius, off")

        if self.NETWORK_VERIFY_MODE == "off" and self.APP_ENV in ("pilot", "production"):
            raise ValueError("NETWORK_VERIFY_MODE=off is not allowed when APP_ENV is pilot or production")

        if not self.PLAY_INTEGRITY_ENFORCE and self.APP_ENV in ("pilot", "production"):
            raise ValueError("PLAY_INTEGRITY_ENFORCE=false is not allowed when APP_ENV is pilot or production")

        if not self.REQUIRE_MFA and self.APP_ENV in ("pilot", "production"):
            raise ValueError("REQUIRE_MFA=false is not allowed when APP_ENV is pilot or production")

        return self

    def safe_field_names(self) -> list[str]:
        """Field names only, for startup logs. Never returns values."""
        return sorted(self.model_fields.keys())


def _format_missing(errors: list[dict]) -> str | None:
    missing = [str(err["loc"][0]) for err in errors if err["type"] == "missing"]
    if not missing:
        return None
    names = ", ".join(sorted(missing))
    return f"Missing required settings: {names}. Copy backend/.env.example to backend/.env and fill them in."


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:  # pydantic.ValidationError or our own ValueError
        errors = getattr(exc, "errors", None)
        if callable(errors):
            message = _format_missing(exc.errors())
            if message:
                raise SystemExit(message) from exc
        raise SystemExit(f"Invalid settings: {exc}") from exc
