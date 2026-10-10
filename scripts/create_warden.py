"""Create or update a warden or admin account in Supabase Auth.

Phase 1, task 6.2. Sets app_metadata.role, which only the service role key can
write, so this must run server-side.

Usage (from the backend folder, so its venv has httpx):

    uv run python ../scripts/create_warden.py --email warden@example.com --role warden
    uv run python ../scripts/create_warden.py --email admin@example.com --role admin

The password is never passed on the command line. It is read from the
NIGHTROLL_WARDEN_PASSWORD environment variable, or prompted for interactively,
so it never appears in shell history or process listings.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def find_user(base: str, headers: dict[str, str], email: str) -> dict | None:
    resp = httpx.get(f"{base}/auth/v1/admin/users", headers=headers, params={"per_page": 1000}, timeout=15)
    resp.raise_for_status()
    for user in resp.json().get("users", []):
        if user.get("email", "").lower() == email.lower():
            return user
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=["warden", "admin"])
    args = parser.parse_args()

    env = parse_env(ROOT / "backend" / ".env")
    base = env["SUPABASE_URL"].rstrip("/")
    service_key = env["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    password = os.environ.get("NIGHTROLL_WARDEN_PASSWORD")
    existing = find_user(base, headers, args.email)

    if existing:
        body = {"app_metadata": {"role": args.role}}
        if password:
            body["password"] = password
        resp = httpx.put(
            f"{base}/auth/v1/admin/users/{existing['id']}", headers=headers, json=body, timeout=15
        )
        action = "updated"
    else:
        if not password:
            password = getpass.getpass(f"Password for {args.email}: ")
        resp = httpx.post(
            f"{base}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": args.email,
                "password": password,
                "email_confirm": True,
                "app_metadata": {"role": args.role},
            },
            timeout=15,
        )
        action = "created"

    if resp.status_code >= 300:
        print(f"Request failed: HTTP {resp.status_code}", file=sys.stderr)
        return 1

    print(f"{action}: {args.email} with role={args.role}")
    print("Password not printed. Set it with NIGHTROLL_WARDEN_PASSWORD or type it when prompted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
