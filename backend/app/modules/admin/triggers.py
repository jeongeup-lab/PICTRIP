"""admin triggers — collection trigger adapter (A01 §5 Phase 2, decision A7).

The collection body is the pipeline CLI ``pictrip-data sync-daily`` (runs on
CT111 via cron; it writes ``sync_runs``). The backend cannot run it directly
(separate Python project), so the trigger remotely kicks a GitHub Actions
workflow that runs the pipeline on the self-hosted runner.

A7 SEAM — the trigger MECHANISM is NOT finalized (GitHub ``workflow_dispatch``
vs a CT111/Tailscale HTTP listener pending team confirmation). It is therefore
isolated behind the :class:`CollectionTrigger` interface (``trigger(job) ->
ref``). Only the concrete adapter changes if the decision flips — routes /
services / frontend / audit stay mechanism-agnostic.

This module implements the RECOMMENDED mechanism (``workflow_dispatch``) as the
sole concrete adapter, CONFIG-GATED: with no ``GITHUB_DISPATCH_TOKEN`` the
factory's adapter raises :class:`AdminTriggerFailed` ("not configured") so the
endpoint degrades to a clean 502 instead of crashing.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.config import settings
from app.core.exceptions import AdminTriggerFailed
from app.core.logging import get_logger

logger = get_logger(__name__)

# GitHub returns 204 No Content (no body, no run id) on a successful dispatch.
_GITHUB_API = "https://api.github.com"
_DISPATCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class CollectionTrigger(Protocol):
    """A7 adapter interface — mechanism-agnostic.

    ``trigger(job)`` kicks the named collection job and returns an optional
    reference id. ``workflow_dispatch`` has no run id (returns 204), so this is
    ``None``; a future listener mechanism could return a real id without
    touching any caller.
    """

    async def trigger(self, job: str) -> str | None: ...


class WorkflowDispatchTrigger:
    """Concrete A7 adapter — GitHub REST ``workflow_dispatch``.

    POST /repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches with
    ``{"ref": ref}``. On missing token, non-2xx, or network error raises
    :class:`AdminTriggerFailed` (→ 502 envelope, A01 §3).
    """

    async def trigger(self, job: str) -> str | None:
        if not settings.GITHUB_DISPATCH_TOKEN:
            raise AdminTriggerFailed(
                "수집 트리거가 아직 구성되지 않았습니다 (GITHUB_DISPATCH_TOKEN 미설정)."
            )
        await self._dispatch(job)
        # workflow_dispatch yields 204 with no run id — admin polls sync_runs.
        return None

    async def _dispatch(self, job: str) -> None:
        """Issue the GitHub dispatch call. Split out so tests mock the network
        boundary (everything above it — gating, return shape — stays real)."""
        url = (
            f"{_GITHUB_API}/repos/{settings.GITHUB_REPO}"
            f"/actions/workflows/{settings.COLLECTION_WORKFLOW}/dispatches"
        )
        headers = {
            "Authorization": f"Bearer {settings.GITHUB_DISPATCH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {"ref": settings.COLLECTION_WORKFLOW_REF}
        try:
            async with httpx.AsyncClient(timeout=_DISPATCH_TIMEOUT) as http:
                resp = await http.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            logger.warning("collection.trigger.network_error", job=job, error=str(exc))
            raise AdminTriggerFailed("수집 트리거 전송에 실패했습니다 (네트워크 오류).") from exc
        if resp.status_code // 100 != 2:
            logger.warning(
                "collection.trigger.http_error",
                job=job,
                status=resp.status_code,
                body=resp.text[:500],
            )
            raise AdminTriggerFailed(f"GitHub workflow_dispatch 실패 (HTTP {resp.status_code}).")


def get_collection_trigger() -> CollectionTrigger:
    """A7 factory — returns the configured adapter.

    Only ``WorkflowDispatchTrigger`` exists for now; the indirection is the seam
    that lets a CT111-listener impl replace it later without touching routes or
    services.
    """
    return WorkflowDispatchTrigger()
