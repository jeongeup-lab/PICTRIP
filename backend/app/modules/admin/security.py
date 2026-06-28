"""admin security — login-page + signed-cookie session (replaces HTTP Basic).

Credentials are checked against the ``admin_users`` table (username + bcrypt
``password_hash``). A successful ``POST /admin/login`` writes the username into
the signed session cookie; :func:`require_admin` then gates protected routes by
reading ``request.session``. Unauthenticated API calls raise
:class:`AdminUnauthorized` (401, no Basic challenge); HTML pages redirect to the
login page in ``routes.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AdminUnauthorized
from app.core.passwords import verify_password
from app.modules.admin import repositories as repo

SESSION_KEY = "admin"


async def authenticate(db: AsyncSession, username: str, password: str) -> bool:
    """True iff (username, password) matches an admin_users row.

    ``verify_password`` is constant-time on the stored hash; an unknown username
    and a wrong password both return False without revealing which.
    """
    admin = await repo.get_admin_user(db, username)
    return admin is not None and verify_password(password, admin.password_hash)


def require_admin(request: Request) -> str:
    """Gate for /admin/api/* — return the logged-in username or raise 401."""
    username = request.session.get(SESSION_KEY)
    if not username:
        raise AdminUnauthorized
    return str(username)


AdminAuth = Annotated[str, Depends(require_admin)]
