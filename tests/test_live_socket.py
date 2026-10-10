"""The live feed accepts the same ES256 tokens as the REST API and sends a snapshot first.
Run from the backend folder:
    uv run pytest ../tests/test_live_socket.py -v
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from starlette.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.auth import supabase as auth  # noqa: E402
from app.main import app  # noqa: E402


def _token(private, role="admin", aal="aal2") -> str:
    claims = {
        "sub": "ws-user",
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        "aal": aal,
        "app_metadata": {"role": role},
    }
    return jwt.encode(claims, private, algorithm="ES256", headers={"kid": "k1"})


def _use_key(monkeypatch, public_key) -> None:
    client = types.SimpleNamespace(get_signing_key_from_jwt=lambda token: types.SimpleNamespace(key=public_key))
    monkeypatch.setattr(auth, "_jwks_client", lambda settings: client)


def test_es256_admin_gets_a_snapshot_first(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    _use_key(monkeypatch, private.public_key())
    with TestClient(app) as client, client.websocket_connect("/v1/ws/rooms") as socket:
        socket.send_json({"type": "auth", "token": _token(private)})
        message = socket.receive_json()
    assert message["type"] == "snapshot"
    assert set(message) >= {"window", "totals", "rooms", "recent"}


def test_socket_without_the_authenticator_step_is_refused(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    _use_key(monkeypatch, private.public_key())
    with TestClient(app) as client, client.websocket_connect("/v1/ws/rooms") as socket:
        socket.send_json({"type": "auth", "token": _token(private, aal="aal1")})
        try:
            socket.receive_json()
            closed = None
        except Exception as error:  # the server closes with 4403
            closed = error
    assert closed is not None
