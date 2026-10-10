"""The six hard gates, in the order they run (Phase 8 section 3).

Each gate reads what earlier gates have already proven and returns a GateCheck. Adding a gate means
adding one function here and one line in ORDERED_GATES.
"""

from __future__ import annotations

import base64
import hashlib
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from pydantic import ValidationError

from app.db.queries import verification as verification_q
from app.schemas.verify import SubmissionPayload
from app.services.verification import integrity
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
