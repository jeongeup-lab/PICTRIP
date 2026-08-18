from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import repositories as repo
from app.modules.admin.passwords import verify_password
from app.web.errors import AdminUnauthorized

SESSION_KEY = "admin"


async def authenticate(db: AsyncSession, username: str, password: str) -> bool:
    admin = await repo.get_admin_user(db, username)
    return admin is not None and verify_password(password, admin.password_hash)


def require_admin(request: Request) -> str:
    username = request.session.get(SESSION_KEY)
    if not username:
        raise AdminUnauthorized
    return str(username)


AdminAuth = Annotated[str, Depends(require_admin)]
