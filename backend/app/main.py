"""FastAPI app entrypoint.

Mounts the 6 domain modules under /v1 and the admin console under /admin.
"""

from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="PicTrip API")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness probe (outside /v1)."""
    return {"status": "ok", "environment": settings.environment}


# TODO: include module routers
#   from app.modules.users.routes import router as users_router
#   app.include_router(users_router, prefix="/v1")
#   ... taste · spots · images · map · system
#   admin mounts at /admin (HTML) + /admin/api/* (JSON), Basic auth
