"""admin — read-only ops console (A01). Served at /admin, outside /v1."""

from app.modules.admin.routes import router

__all__ = ["router"]
