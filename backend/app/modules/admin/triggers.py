from __future__ import annotations

from typing import Protocol

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.web.errors import AdminTriggerFailed

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"
_DISPATCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class CollectionTrigger(Protocol):
    async def trigger(self, job: str) -> str | None: ...


class WorkflowDispatchTrigger:
    async def trigger(self, job: str) -> str | None:
        if not settings.GITHUB_DISPATCH_TOKEN:
            raise AdminTriggerFailed(
                "수집 트리거가 아직 구성되지 않았습니다 (GITHUB_DISPATCH_TOKEN 미설정)."
            )
        await self._dispatch(job)
        return None

    async def _dispatch(self, job: str) -> None:
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
    return WorkflowDispatchTrigger()
