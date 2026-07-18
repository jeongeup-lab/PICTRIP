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
