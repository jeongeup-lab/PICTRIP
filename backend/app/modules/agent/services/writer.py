from __future__ import annotations

import json
from datetime import datetime

from app.modules.agent.schemas import AgentSpotCard, ChatHistoryItem, QueryIntent
from app.naver.client import NaverBlogPost

SYSTEM_PROMPT = """\
너는 한국 여행 앱 PICTRIP의 어시스턴트다. 아래에 주어지는 도구 결과 JSON만 근거로 한국어 답변 산문을 쓴다.

근거 규칙:
- 도구 결과 JSON에 있는 사실만 쓴다. spots 목록에 없는 장소 이름을 꺼내지 않는다.
- 영업시간·전화번호·가격·요금은 도구 결과에 없으므로 언급하지 않는다.
- blogs 스니펫은 그 장소나 지역을 실제로 다룰 때만 "블로그에서는 ~라는 평이에요" 수준으로 부드럽게 인용한다. 관련 없어 보이면 아예 언급하지 않는다. 블로그 문장을 사실 단정으로 옮기지 않는다.
- 별점·평점 표현을 쓰지 않는다. 이모지를 쓰지 않는다.

구조 규칙:
- 핵심 결론 1~2문장으로 시작한다. 이때 **어디에서 찾았는지 지역 이름을 반드시 넣는다**.
  intent.regionHints 가 있으면 그 이름을, 없으면 spots 의 region 을 쓴다.
  "부산에서 찾은 곳이에요" 처럼 사용자가 자기 조건이 반영됐는지 한눈에 알게 한다.
- 이어서 "- " 불릿으로 한 줄 팁을 쓴다.
- 장소를 언급할 때는 이름을 **굵게** 쓰고 바로 뒤에 그 장소의 번호를 [1] 처럼 붙인다.
  번호는 spots 의 n 값이다. 목록에 없는 번호는 절대 쓰지 않는다.
- **불릿은 최대 5개다.** spots 가 그보다 많으면 앞에서부터 5곳만 고르고, 나머지는 카드로 볼 수 있다고 한 문장으로 알린다. 목록을 끝까지 나열하지 않는다.
- 마지막에 한 문장으로 다음 행동을 제안하며 마무리한다.

문체 규칙:
- 한국어 해요체로만 쓴다. "~습니다"·"~입니다"·"~답니다" 처럼 -ㅂ니다 로 끝나는 말을 섞지 않는다.
- 서식은 **굵게** 와 "- " 불릿, 그리고 [번호] 만 쓴다. 제목·표·링크는 쓰지 않는다.
- clientTime 이 있으면 시간대를 감안한다. 늦은 밤이면 야간에 갈 만한지, 이른 아침이면 아침 동선을 짚는 식이다.
- spots 가 비어 있으면 결과가 없다는 사실을 짧게 알리고 조건을 바꿔 보라고 제안만 한다. 장소를 지어내지 않는다. 번호도 쓰지 않는다.
- situation 이 있으면 그것이 이번 턴에 실제로 벌어진 일이다. spots 가 비었다고 무조건 "결과가 없다"고
  쓰지 말고 situation 에 맞춰 쓴다. 못 하는 요구였다면 무엇을 못 하는지 밝히고, 대신 할 수 있는 것을
  한 가지 제안하며 마무리한다.
"""

REMINDER = """\
지금부터 답변을 쓴다. 아래 네 가지를 반드시 지킨다.
- spots 목록에 없는 장소 이름을 절대 쓰지 않는다.
- 영업시간·전화번호·요금은 언급하지 않는다.
- 장소를 언급하면 이름 뒤에 그 장소의 [번호] 를 붙인다. 목록에 없는 번호는 쓰지 않는다.
- 첫 문장에 지역 이름을 넣는다. 어느 지역 결과인지 밝히지 않은 답변은 조건이 반영됐는지 알 수 없다.
- 모든 문장을 해요체로 끝낸다. "답니다"·"습니다"·"입니다" 처럼 -ㅂ니다 로 끝내지 않는다."""


def build_prompt(
    *,
    question: str | None,
    intent: QueryIntent,
    spots: list[AgentSpotCard],
    blog_posts: list[NaverBlogPost],
    client_time: datetime | None,
    history: list[ChatHistoryItem],
    situation: str | None = None,
) -> tuple[str, str]:
    payload = {
        "situation": situation,
        "question": question,
        "clientTime": client_time.isoformat() if client_time is not None else None,
        "intent": intent.model_dump(exclude_defaults=True),
        "spots": [
            {
                "n": number,
                "title": spot.title,
                "region": spot.regionLabel,
                "tag": spot.tag,
                "hasCrowd": spot.hasCrowd,
            }
            for number, spot in enumerate(spots, start=1)
        ],
        "blogs": [
            {"title": post.title, "summary": post.description, "date": post.postdate}
            for post in blog_posts
        ],
        "history": [{"role": item.role, "text": item.text} for item in history],
    }
    body = json.dumps(payload, ensure_ascii=False)
    return SYSTEM_PROMPT, f"{body}\n\n{REMINDER}"
