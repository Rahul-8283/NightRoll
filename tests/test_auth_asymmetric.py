"""Supabase projects with asymmetric signing keys issue ES256 tokens. The backend must accept them, and still
accept HS256 for older projects. Pure logic, no database. Run from the backend folder:
    uv run pytest ../tests/test_auth_asymmetric.py -v
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.auth import supabase as auth  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.errors import AppError  # noqa: E402


def _claims() -> dict:
    return {
        "sub": "user-1",
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        "aal": "aal2",
        "app_metadata": {"role": "admin"},
    }


def _stub_jwks(monkeypatch, public_key) -> None:
    client = types.SimpleNamespace(get_signing_key_from_jwt=lambda token: types.SimpleNamespace(key=public_key))
    monkeypatch.setattr(auth, "_jwks_client", lambda settings: client)


def test_es256_token_signed_by_the_project_key_is_accepted(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    _stub_jwks(monkeypatch, private.public_key())
    token = jwt.encode(_claims(), private, algorithm="ES256", headers={"kid": "k1"})
    assert auth.verify_token(token, get_settings())["sub"] == "user-1"


def test_es256_token_signed_by_another_key_is_refused(monkeypatch):
    project = ec.generate_private_key(ec.SECP256R1())
    attacker = ec.generate_private_key(ec.SECP256R1())
    _stub_jwks(monkeypatch, project.public_key())
    token = jwt.encode(_claims(), attacker, algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(AppError) as error:
        auth.verify_token(token, get_settings())
    assert error.value.status_code == 401


def test_hs256_token_still_works_for_older_projects():
    settings = get_settings()
    token = jwt.encode(_claims(), settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    assert auth.verify_token(token, settings)["sub"] == "user-1"


def test_unsigned_and_unknown_algorithms_are_refused():
    token = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(AppError) as error:
        auth.verify_token(token, get_settings())
    assert error.value.status_code == 401
