"""admin security — ADMIN_PASSWORD HTTP Basic dependency (A01 §1.3).

Guards every `/admin/*` route. Username is fixed to ``admin``; the password is
compared with :func:`secrets.compare_digest` (timing-safe). When
``ADMIN_PASSWORD`` is unset the whole surface is *locked* (503).

Auth failures raise admin :class:`AppError` subclasses so the response carries
the A01 §3 envelope codes (``ADMIN_LOCKED`` / ``ADMIN_UNAUTHORIZED``).
``AdminUnauthorized`` ships the ``WWW-Authenticate: Basic`` header, which the
envelope handler forwards (``headers=exc.headers``) so browsers still prompt.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.exceptions import AdminLocked, AdminUnauthorized

_ADMIN_USERNAME = "admin"

# auto_error=False so a *missing* Authorization header reaches us as ``None``
# and we can return 503 (locked) before 401 when the console is not configured.
_basic = HTTPBasic(auto_error=False)


def verify_admin(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    # Lazy import keeps the dependency reading the live settings object, which
    # tests monkeypatch via ``app.config.settings.ADMIN_PASSWORD``.
    from app.config import settings

    password = settings.ADMIN_PASSWORD
    if not password:
        raise AdminLocked

    if credentials is None:
        raise AdminUnauthorized

    user_ok = secrets.compare_digest(credentials.username, _ADMIN_USERNAME)
    pass_ok = secrets.compare_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        raise AdminUnauthorized


AdminAuth = Annotated[None, Depends(verify_admin)]
