"""AppError hierarchy. The subclass sets both `code` and `http_status`.

Mobile branches on `err.code`, never `err.message`.
"""

from __future__ import annotations


class AppError(Exception):
    code: str = "INTERNAL"
    http_status: int = 500

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


# --- admin console (A01 §3) ---
class AdminUnauthorized(AppError):
    code = "ADMIN_UNAUTHORIZED"
    http_status = 401


class AdminHistoryNotFound(AppError):
    code = "ADMIN_HISTORY_NOT_FOUND"
    http_status = 404


class AdminTriggerFailed(AppError):  # Phase 2
    code = "ADMIN_TRIGGER_FAILED"
    http_status = 502
