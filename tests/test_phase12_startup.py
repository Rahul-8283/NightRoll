"""Phase 12 startup safety checks. No database needed. Run from the backend folder:
uv run pytest ../tests/test_phase12_startup.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app import startup_checks  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402

GOOD_TOKEN = "t" * 32


def _settings(**overrides) -> dict:
    base = get_settings().model_dump()
    base.update(
        APP_ENV="pilot",
        PLAY_INTEGRITY_ENFORCE=True,
        NETWORK_VERIFY_MODE="subnet",
        REQUIRE_MFA=True,
        TRUSTED_PROXY_IPS="172.28.0.10",
        FACE_WORKER_TOKEN=GOOD_TOKEN,
    )
    base.update(overrides)
    return base


def test_a_safe_pilot_configuration_starts():
    assert Settings(**_settings()).APP_ENV == "pilot"


@pytest.mark.parametrize("env", ["pilot", "production"])
@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"PLAY_INTEGRITY_ENFORCE": False}, "PLAY_INTEGRITY_ENFORCE=false is not allowed"),
        ({"NETWORK_VERIFY_MODE": "off"}, "NETWORK_VERIFY_MODE=off is not allowed"),
        ({"REQUIRE_MFA": False}, "REQUIRE_MFA=false is not allowed"),
        ({"TRUSTED_PROXY_IPS": ""}, "TRUSTED_PROXY_IPS is empty"),
        ({"TRUSTED_PROXY_IPS": "172.28.0.10, 0.0.0.0/0"}, "TRUSTED_PROXY_IPS allows every address"),
        ({"TRUSTED_PROXY_IPS": "*"}, "TRUSTED_PROXY_IPS allows every address"),
        ({"FACE_WORKER_TOKEN": "short"}, "FACE_WORKER_TOKEN must be at least 32 characters"),
    ],
)
def test_pilot_and_production_refuse_each_unsafe_setting(env, override, message):
    with pytest.raises(Exception, match=message):
        Settings(**_settings(APP_ENV=env, **override))


def test_an_unknown_environment_name_is_refused():
    with pytest.raises(Exception, match="APP_ENV must be one of"):
        Settings(**_settings(APP_ENV="staging"))


def test_demo_allows_every_relaxed_setting_and_lists_them():
    demo = Settings(
        **_settings(
            APP_ENV="demo",
            PLAY_INTEGRITY_ENFORCE=False,
            NETWORK_VERIFY_MODE="off",
            REQUIRE_MFA=False,
            TRUSTED_PROXY_IPS="",
            FACE_WORKER_TOKEN="short",
        )
    )
    relaxed = " | ".join(demo.relaxed_settings())
    names = ("PLAY_INTEGRITY_ENFORCE", "NETWORK_VERIFY_MODE", "REQUIRE_MFA", "TRUSTED_PROXY_IPS", "FACE_WORKER_TOKEN")
    for name in names:
        assert name in relaxed


def test_a_safe_configuration_relaxes_nothing():
    assert Settings(**_settings(APP_ENV="demo")).relaxed_settings() == []


def _worker(answer: dict | int, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(answer, int):
            return httpx.Response(answer)
        return httpx.Response(200, json=answer)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        startup_checks.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **{k: v for k, v in kw.items() if k != "transport"}),
    )


@pytest.mark.asyncio
async def test_pilot_refuses_to_start_when_antispoof_is_unavailable(monkeypatch):
    _worker({"ready": True, "antispoof_available": False}, monkeypatch)
    with pytest.raises(SystemExit, match="anti-spoof"):
        await startup_checks.run(Settings(**_settings()))


@pytest.mark.asyncio
async def test_pilot_refuses_to_start_when_the_face_worker_does_not_answer(monkeypatch):
    _worker(503, monkeypatch)
    with pytest.raises(SystemExit, match="did not answer"):
        await startup_checks.run(Settings(**_settings()))


@pytest.mark.asyncio
async def test_pilot_starts_when_antispoof_is_available(monkeypatch):
    _worker({"ready": True, "antispoof_available": True}, monkeypatch)
    await startup_checks.run(Settings(**_settings()))


@pytest.mark.asyncio
async def test_demo_prints_a_banner_naming_what_is_relaxed(monkeypatch, capsys):
    _worker({"ready": True, "antispoof_available": False}, monkeypatch)
    await startup_checks.run(Settings(**_settings(APP_ENV="demo", PLAY_INTEGRITY_ENFORCE=False)))
    out = capsys.readouterr().out
    assert "DEMO MODE" in out
    assert "PLAY_INTEGRITY_ENFORCE" in out
    assert "anti-spoof" in out
