"""Claude Haiku client for REC-004 'why this place?' natural-language explanations."""

from __future__ import annotations

from anthropic import AnthropicError, AsyncAnthropic, RateLimitError

from app.config import settings
from app.core.exceptions import LlmApiUnavailable, RateLimited
from app.core.logging import get_logger

logger = get_logger(__name__)


class LlmClient:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def explain_match(
        self,
        *,
        taste_summary: str,
        spot_title: str,
        spot_address: str,
        spot_overview: str,
    ) -> str:
        prompt = (
            f"사용자의 취향: {taste_summary}\n"
            f"이 관광지: {spot_title} ({spot_address})\n"
            f"{spot_overview[:300]}\n\n"
            "위 정보를 기반으로 사용자에게 '왜 이곳을 추천하는지' "
            "자연스러운 한국어 2~3문장으로 답변하세요."
        )
        try:
            msg = await self._client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
        except RateLimitError as exc:
            raise RateLimited() from exc
        except AnthropicError as exc:
            # Auth, connection, timeout, 5xx — surface a domain code instead of
            # leaking a generic INTERNAL_ERROR to the mobile client.
            logger.warning("llm.explain_match.failed", error_type=type(exc).__name__)
            raise LlmApiUnavailable() from exc

        # Guard against an empty/non-text content list rather than IndexError-ing
        # or silently returning "".
        if not msg.content:
            raise LlmApiUnavailable()
        text = getattr(msg.content[0], "text", "")
        if not text:
            raise LlmApiUnavailable()
        return text


llm_client = LlmClient()
