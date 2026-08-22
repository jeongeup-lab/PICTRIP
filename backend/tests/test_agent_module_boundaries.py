from __future__ import annotations

import ast
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1] / "app" / "modules" / "agent" / "services"
PACKAGE = "app.modules.agent.services"


def _cross_file_private_imports() -> list[str]:
    found: list[str] = []
    for path in sorted(SERVICES.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith(f"{PACKAGE}."):
                continue
            source = node.module.rsplit(".", 1)[-1]
            if source == path.stem:
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    found.append(f"{path.stem} <- {source}.{alias.name}")
    return found


def test_agent_services_do_not_reach_into_each_others_privates() -> None:
    """`_` 는 "이 파일 밖에서 쓰지 마라"는 유일한 표식이다.

    2026-08-19 이전에는 이 값이 36이었다. 파일만 갈라 놓고 서로의 프라이빗을
    끌어다 쓰면 파일 경계는 grep 편의일 뿐 모듈 경계가 아니다. 공유해야 하는
    것은 이름을 공개로 올려 cards/phrasing/answer 중 한 곳에 둔다.
    """
    leaks = _cross_file_private_imports()
    assert leaks == [], "공개 이름으로 올리거나 같은 파일로 옮길 것:\n  " + "\n  ".join(leaks)


def test_no_service_module_is_named_like_an_http_router() -> None:
    """모든 모듈에서 routes.py 는 HTTP 라우터다 — services 안에 두면 읽는 이가 헷갈린다."""
    names = {path.stem for path in SERVICES.glob("*.py")}
    assert "routes" not in names
