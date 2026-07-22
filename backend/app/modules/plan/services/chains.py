from __future__ import annotations

import re

_BRANCH_SUFFIX = re.compile(r"\S*점$")
_INDEPENDENT_SUFFIX = re.compile(r"(본점|반점)$")


def is_chain_branch(title: str | None) -> bool:
    name = (title or "").strip()
    if len(name) < 3:
        return False
    if _INDEPENDENT_SUFFIX.search(name):
        return False
    return bool(_BRANCH_SUFFIX.search(name))
