"""Set / rotate an admin-console password (admin_users table).

The admin console authenticates against the ``admin_users`` DB table, not an env
var. Use this to replace the weak seeded default (``admin``/``admin``) with a
strong password, or to add another admin login. Connects with the same
``DATABASE_URL`` / ``POSTGRES_*`` settings as the app (``app.config``).

Usage (from ``backend/``):

    # interactive (password not echoed, never on the command line / shell history):
    uv run python -m scripts.set_admin_password --username admin

    # non-interactive (e.g. from a secret store) — avoid in shared shells:
    ADMIN_NEW_PASSWORD='...' uv run python -m scripts.set_admin_password --username admin

Upserts: creates the user if absent, else updates the hash + bumps updated_at.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import text

from app.core.db import engine
from app.core.passwords import hash_password


async def _upsert(username: str, password: str) -> None:
    password_hash = hash_password(password)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO admin_users (username, password_hash) "
                "VALUES (:u, :h) "
                "ON CONFLICT (username) "
                "DO UPDATE SET password_hash = EXCLUDED.password_hash, updated_at = now()"
            ),
            {"u": username, "h": password_hash},
        )
    await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Set/rotate an admin-console password.")
    parser.add_argument("--username", default="admin", help="admin username (default: admin)")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_NEW_PASSWORD")
    if not password:
        password = getpass.getpass(f"New password for admin '{args.username}': ")
        confirm = getpass.getpass("Confirm: ")
        if password != confirm:
            print("passwords do not match", file=sys.stderr)
            return 1
    if not password.strip():
        print("password must not be blank", file=sys.stderr)
        return 1

    asyncio.run(_upsert(args.username, password))
    print(f"admin '{args.username}' password updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
