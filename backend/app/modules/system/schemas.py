"""SYS DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class VersionMeta(BaseModel):
    apiVersion: str
    environment: str
    ktoApiStatus: str = "unknown"
