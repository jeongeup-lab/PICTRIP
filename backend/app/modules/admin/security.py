"""admin security — DB-backed HTTP Basic auth (A01 §1.3).

Guards every ``/admin/*`` route. Credentials are checked against the
``admin_users`` table (username + bcrypt ``password_hash``) rather than an env
var, so the console can be provisioned/rotated through the shared CT110 DB with
no CT112 ``.env``/shell access (decision 2026-06-27).

A missing/blank Authorization header or a bad username/password raises
:class:`AdminUnauthorized` (401 + ``WWW-Authenticate: Basic`` so a browser
prompts). The endpoint is CF-exposed, so the challenge header matters.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.db import DbSession
from app.core.exceptions import AdminUnauthorized
from app.core.passwords import verify_password
from app.modules.admin import repositories as repo

# auto_error=False so a *missing* Authorization header reaches us as ``None``
# (we turn it into a 401 + Basic challenge ourselves).
_basic = HTTPBasic(auto_error=False)


async def verify_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
    db: DbSession,
) -> None:
    if credentials is None:
        raise AdminUnauthorized
    admin = await repo.get_admin_user(db, credentials.username)
    # verify_password is constant-time on the stored hash; an unknown username
    # (admin is None) and a wrong password both fall through to the same 401 so
    # the response does not reveal which one was wrong.
    if admin is None or not verify_password(credentials.password, admin.password_hash):
        raise AdminUnauthorized


AdminAuth = Annotated[None, Depends(verify_admin)]
