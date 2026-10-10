"""Envelope Signature Verification Script (Phase 7 Exit Criteria).

Verifies the hardware ECDSA P-256 SHA-256 signature of a NightRoll attendance payload
using the student's enrolled public key (base64 DER SubjectPublicKeyInfo) and the exact
received payload bytes.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def verify_payload_signature(
    public_key_b64: str,
    payload_bytes: bytes,
    signature_b64: str,
) -> bool:
    """Verify ECDSA P-256 signature over raw payload bytes.

    Args:
        public_key_b64: Base64-encoded DER SubjectPublicKeyInfo.
        payload_bytes: Raw received payload UTF-8 bytes (exact bytes from envelope).
        signature_b64: Base64-encoded ASN.1 DER signature.

    Returns:
        True if signature is mathematically valid for the payload bytes, False otherwise.
    """
    try:
        pub_der = base64.b64decode(public_key_b64)
        public_key = serialization.load_der_public_key(pub_der)
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return False

        sig_der = base64.b64decode(signature_b64)
        public_key.verify(sig_der, payload_bytes, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def run_self_test() -> int:
    """Runs a self-test with an ECDSA P-256 key and a standard Phase 7 payload."""
    print("Running Phase 7 Envelope Signature Verification Self-Test...")

    # 1. Generate an EC P-256 key pair
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    pub_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_b64 = base64.b64encode(pub_der).decode("ascii")

    # 2. Build sample Phase 7 payload
    sample_payload = {
        "v": 1,
        "student_id": "b3c9554f-1234-4567-89ab-cdef01234567",
        "window_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "nonce": "test_nonce_base64url_value_1234567890",
        "client_time": "2026-10-10T22:01:14+05:30",
        "challenge": [
            {"action": "blink", "started_ms": 0, "detected_ms": 1180},
            {"action": "turn_right", "started_ms": 1400, "detected_ms": 2950},
        ],
        "frames": [
            {"index": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "tag": "blink"},
            {"index": 1, "sha256": "ca978112ca1bbdcafac231b39a23dc4da7860814965e7146607a345999014603", "tag": "turn_right"},
            {"index": 2, "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a", "tag": "neutral"},
            {"index": 3, "sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d", "tag": "neutral"},
        ],
        "wifi": {
            "connected": {"bssid": "aa:bb:cc:00:01:05", "rssi": -52, "band": "5GHz"},
            "scan_age_ms": 800,
            "scan": [
                {"bssid": "aa:bb:cc:00:01:05", "rssi": -52, "band": "5GHz"},
                {"bssid": "aa:bb:cc:00:02:05", "rssi": -71, "band": "5GHz"},
            ],
        },
        "environment": {
            "vpn": False,
            "proxy": False,
            "mock_location": False,
            "developer_options": False,
            "on_wifi": True,
        },
        "app_version": "0.1.0",
    }

    # Exactly serialized payload bytes
    payload_str = json.dumps(sample_payload)
    payload_bytes = payload_str.encode("utf-8")

    # 3. Sign the bytes
    signature = private_key.sign(payload_bytes, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(signature).decode("ascii")

    # 4. Verify original payload
    valid = verify_payload_signature(pub_b64, payload_bytes, sig_b64)
    print(f"[-] Verification on genuine payload: {'PASS' if valid else 'FAIL'}")
    if not valid:
        return 1

    # 5. Tamper test: Alter one byte of payload
    tampered_bytes = payload_bytes + b" "
    tampered_valid = verify_payload_signature(pub_b64, tampered_bytes, sig_b64)
    print(f"[-] Tampered payload rejected: {'PASS' if not tampered_valid else 'FAIL'}")
    if tampered_valid:
        return 1

    # 6. Wrong key test
    other_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    other_pub_der = other_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    other_pub_b64 = base64.b64encode(other_pub_der).decode("ascii")
    wrong_key_valid = verify_payload_signature(other_pub_b64, payload_bytes, sig_b64)
    print(f"[-] Wrong public key rejected: {'PASS' if not wrong_key_valid else 'FAIL'}")
    if wrong_key_valid:
        return 1

    print("\nAll signature verification tests passed successfully!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify NightRoll envelope signature")
    parser.add_argument("--test", action="store_true", help="Run self-test with sample payload and generated key")
    parser.add_argument("--public-key", type=str, help="Base64 DER public key or file path containing it")
    parser.add_argument("--payload", type=str, help="Payload UTF-8 string or file path containing it")
    parser.add_argument("--signature", type=str, help="Base64 ASN.1 DER signature or file path containing it")

    args = parser.parse_args()

    if args.test or len(sys.argv) == 1:
        return run_self_test()

    if not (args.public_key and args.payload and args.signature):
        parser.error("Must provide --public-key, --payload, and --signature (or --test)")

    # Read public key
    pk_str = args.public_key
    if Path(pk_str).is_file():
        pk_str = Path(pk_str).read_text(encoding="utf-8").strip()

    # Read payload
    if Path(args.payload).is_file():
        payload_bytes = Path(args.payload).read_bytes()
    else:
        payload_bytes = args.payload.encode("utf-8")

    # Read signature
    sig_str = args.signature
    if Path(sig_str).is_file():
        sig_str = Path(sig_str).read_text(encoding="utf-8").strip()

    valid = verify_payload_signature(pk_str, payload_bytes, sig_str)
    if valid:
        print("SIGNATURE_VALID: Verification succeeded.")
        return 0
    else:
        print("SIGNATURE_INVALID: Verification failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
