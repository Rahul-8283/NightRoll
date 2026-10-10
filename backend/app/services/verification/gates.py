"""The six hard gates, in the order they run (Phase 8 section 3).

Each gate reads what earlier gates have already proven and returns a GateCheck. Adding a gate means
adding one function here and one line in ORDERED_GATES.
"""

from __future__ import annotations

import base64
import hashlib
import time
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from pydantic import ValidationError

from app.db.queries import students as students_q
from app.db.queries import verification as verification_q
from app.db.queries import windows as windows_q
from app.schemas.verify import SubmissionPayload
from app.services import nonces
from app.services.verification import integrity
from app.services.verification.network import RoomNetwork, get_network_verifier
from app.services.verification.runner import GateCheck, Submission

SUPPORTED_PAYLOAD_VERSION = 1


async def signature_gate(submission: Submission) -> GateCheck:
    """Gate 1: nothing in the payload is believed until its signature checks out.

    The order is fixed: device key, then signature over the raw bytes, then schema, then version, then the
    frame hashes. Only the signed bytes are ever parsed.
    """
    if submission.claimed_student_id is None:
        return GateCheck.fail("DEVICE_NOT_ENROLLED", "no student identified")

    key = await verification_q.active_device_key(submission.pool, submission.claimed_student_id)
    if key is None:
        return GateCheck.fail("DEVICE_NOT_ENROLLED", "no active device for this student")

    try:
        public_key = load_der_public_key(key)
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError("device key is not EC")
        public_key.verify(base64.b64decode(submission.signature), submission.payload_bytes, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError):
        return GateCheck.fail("SIGNATURE_INVALID", "signature does not match the payload")

    try:
        payload = SubmissionPayload.model_validate_json(submission.payload_bytes)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return GateCheck.fail("PAYLOAD_INVALID", f"{where}: {first['msg']}")
    if payload.v != SUPPORTED_PAYLOAD_VERSION:
        return GateCheck.fail("PAYLOAD_INVALID", f"unsupported payload version {payload.v}")
    submission.payload = payload

    if len(submission.frames) != len(payload.frames):
        return GateCheck.fail("SIGNATURE_INVALID", "frame count differs from the signed payload")
    for signed, body in zip(payload.frames, submission.frames, strict=True):
        if hashlib.sha256(body).hexdigest() != signed.sha256:
            return GateCheck.fail("SIGNATURE_INVALID", f"frame {signed.index} is not the one that was signed")
    return GateCheck.ok()


async def environment_gate(submission: Submission) -> GateCheck:
    """Gate 5: the phone's own report. Supporting evidence only; the network gate is the real block."""
    env = submission.payload.environment
    flags = [
        name for name, bad in (("vpn", env.vpn), ("proxy", env.proxy), ("mock_location", env.mock_location)) if bad
    ]
    if not env.on_wifi:
        flags.append("not_on_wifi")
    if flags:
        return GateCheck.fail("ENVIRONMENT_FLAGGED", f"flagged: {', '.join(flags)}")
    return GateCheck.ok()


def _integrity_failure(submission: Submission, detail: str) -> GateCheck:
    if submission.settings.PLAY_INTEGRITY_ENFORCE:
        return GateCheck.fail("INTEGRITY_FAILED", detail)
    return GateCheck.ok(warning=f"INTEGRITY_NOT_ENFORCED: {detail}")


async def integrity_gate(submission: Submission) -> GateCheck:
    """Gate 4: the token is genuine, for this app, and bound to this exact payload.

    An unreachable Google raises IntegrityUnavailable, which becomes a 503. It never passes the gate.
    """
    if submission.integrity_error or not submission.integrity_token:
        return _integrity_failure(submission, f"no token ({submission.integrity_error or 'missing'})")

    verdict = await integrity.decode_token(submission.settings, submission.integrity_token)
    if verdict is None:
        return _integrity_failure(submission, "Google rejected the token")

    detail, warning = integrity.check_verdict(
        verdict,
        expected_package=submission.settings.PLAY_INTEGRITY_PACKAGE_NAME,
        payload_hash=submission.payload_hash,
        now_ms=int(time.time() * 1000),
    )
    if detail:
        return _integrity_failure(submission, detail)
    return GateCheck.ok(warning=warning)


async def window_gate(submission: Submission) -> GateCheck:
    """Gate 2: the payload's window must be the open one, and the server clock must agree.

    The phone's `client_time` is recorded but never used for this decision.
    """
    payload = submission.payload
    window = await windows_q.open_window(submission.pool)
    if window is None or window["id"] != payload.window_id:
        return GateCheck.fail("OUTSIDE_WINDOW", "the signed window is not the open window")

    now = datetime.now(UTC)
    if not (window["opens_at"] <= now < window["closes_at"]):
        return GateCheck.fail("OUTSIDE_WINDOW", "server clock is outside the window")

    student = await students_q.get_active_enrolled(submission.pool, payload.student_id)
    if student is None:
        return GateCheck.fail("DEVICE_NOT_ENROLLED", "student is not active and enrolled")

    submission.window = window
    return GateCheck.ok()


async def nonce_gate(submission: Submission) -> GateCheck:
    """Gate 3: the nonce is fresh, single use, and was issued with this challenge.

    The challenge is compared before the nonce is consumed, so a wrong challenge does not burn it.
    """
    payload = submission.payload
    window_id = submission.window["id"]
    status, value, challenge = await nonces.peek(submission.redis, window_id, payload.student_id)
    if status != "ok" or value != payload.nonce:
        return GateCheck.fail("NONCE_INVALID", f"nonce {status}")
    if challenge is None or challenge != [step.action for step in payload.challenge]:
        return GateCheck.fail("NONCE_INVALID", "challenge does not match the one issued")

    consumed = await nonces.consume(submission.redis, window_id, payload.student_id, payload.nonce)
    if consumed != "ok":
        return GateCheck.fail("NONCE_INVALID", f"nonce {consumed}")
    return GateCheck.ok()


async def network_gate(submission: Submission) -> GateCheck:
    """Gate 6: the request came from the student's own room network, through the room's own router.

    The detail stays in the logs. The student is told only that the request did not come from the room.
    """
    payload = submission.payload
    row = await verification_q.student_room_network(submission.pool, payload.student_id)
    if row is None:
        return GateCheck.fail("NETWORK_MISMATCH", "student has no room")

    room = RoomNetwork(
        room_id=str(row["room_id"]),
        subnet=row["subnet"],
        access_point_bssids=frozenset(row["access_point_bssids"]),
    )
    submission.room = room
    verifier = get_network_verifier(submission.settings.NETWORK_VERIFY_MODE)
    result = verifier.verify(room, submission.client_ip, payload.wifi.connected.bssid)
    if result.warning:
        return GateCheck.ok(warning=result.warning)
    if not result.passed:
        return GateCheck.fail("NETWORK_MISMATCH", result.detail)
    return GateCheck.ok()
