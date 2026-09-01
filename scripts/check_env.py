#!/usr/bin/env python
"""Validate that required environment variables are actually set.

Run before deploying, or locally after pulling changes that touch config:
    python scripts/check_env.py

Compares against backend/.env.example, the canonical list of every variable
the app knows about. Variables in REQUIRED must be set (in the real
environment, or in backend/.env / .env) or this exits non-zero — these are
the ones with insecure or non-functional defaults (secrets, DB connection).
Everything else in .env.example is optional (connector credentials, mainly:
the app boots fine without them, that connector just won't work) and only
produces a warning.

Exits non-zero if any REQUIRED variable is missing.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ENV_EXAMPLE = ROOT / "backend" / ".env.example"

REQUIRED = {"DATABASE_URL", "JWT_SECRET", "CREDENTIALS_ENCRYPTION_KEY"}


def _keys_from_example(path: Path) -> list[str]:
    keys = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.append(line.split("=", 1)[0].strip())
    return keys


def _load_dotenv_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def main() -> int:
    if not BACKEND_ENV_EXAMPLE.exists():
        print(f"No {BACKEND_ENV_EXAMPLE} found — nothing to validate against.")
        return 1

    known_dotenv_keys = _load_dotenv_keys(ROOT / "backend" / ".env") | _load_dotenv_keys(ROOT / ".env")
    declared_keys = _keys_from_example(BACKEND_ENV_EXAMPLE)

    missing_required = []
    missing_optional = []
    for key in declared_keys:
        if key in os.environ or key in known_dotenv_keys:
            continue
        (missing_required if key in REQUIRED else missing_optional).append(key)

    if missing_optional:
        print("Optional variables not set (connector features using them won't work):")
        for key in missing_optional:
            print(f"  - {key}")

    if missing_required:
        print("Missing REQUIRED environment variables:")
        for key in missing_required:
            print(f"  - {key}")
        return 1

    print("All required environment variables are set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
