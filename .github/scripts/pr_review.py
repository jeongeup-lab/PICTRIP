#!/usr/bin/env python3
"""자체 호스팅 PR 리뷰 — codexproxy(CT112)로 diff를 리뷰하고 P1/P2/P3 인라인 코멘트를 단다.

Codex GitHub 커넥터를 대체하는 stdlib-only 스크립트. GITHUB_TOKEN으로 diff를 받아
codexproxy /v1/chat/completions에 넘기고, diff 범위 안 findings만 인라인 리뷰로,
범위 밖은 요약 본문에 모아 게시한다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

GH_API = "https://api.github.com"
MAX_DIFF_CHARS = 200_000
SEVERITY_ORDER = {"P1": 0, "P2": 1, "P3": 2}
SEV_EMOJI = {"P1": "🔴", "P2": "🟡", "P3": "🔵"}
ALERT_BY_TOP = {"P1": "CAUTION", "P2": "WARNING", "P3": "NOTE"}


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        sys.exit(f"[pr_review] 필수 환경변수 누락: {name}")
    return val


def gh_request(method: str, url: str, token: str, accept: str, body: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "pictrip-pr-review")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_diff(repo: str, pr: str, token: str) -> str:
    url = f"{GH_API}/repos/{repo}/pulls/{pr}"
    return gh_request("GET", url, token, "application/vnd.github.diff").decode("utf-8", "replace")


def post_review(repo: str, pr: str, token: str, payload: dict) -> tuple[int, str]:
    url = f"{GH_API}/repos/{repo}/pulls/{pr}/reviews"
    body = json.dumps(payload).encode("utf-8")
    try:
        gh_request("POST", url, token, "application/vnd.github+json", body)
        return 200, "ok"
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def parse_diff(diff: str) -> dict[str, dict[str, set[int]]]:
    """path -> {'RIGHT': {새 파일 줄번호}, 'LEFT': {옛 파일 줄번호}} — 코멘트 가능 라인 집합."""
    files: dict[str, dict[str, set[int]]] = {}
    path: str | None = None
    new_ln = old_ln = 0
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            path, in_hunk = None, False
        elif line.startswith("+++ "):
            p = line[4:]
            path = None if p == "/dev/null" else p[2:] if p.startswith("b/") else p
            if path:
                files.setdefault(path, {"RIGHT": set(), "LEFT": set()})
        elif line.startswith("--- "):
            continue
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                old_ln, new_ln, in_hunk = int(m.group(1)), int(m.group(2)), True
        elif in_hunk and path:
            tag = line[:1]
            if tag == "+":
                files[path]["RIGHT"].add(new_ln)
                new_ln += 1
            elif tag == "-":
                files[path]["LEFT"].add(old_ln)
                old_ln += 1
            elif tag == " ":
                files[path]["RIGHT"].add(new_ln)
                files[path]["LEFT"].add(old_ln)
                new_ln += 1
                old_ln += 1
    return files


def extract_guidelines(text: str) -> str:
    """AGENTS.md에서 '## Review guidelines' 섹션만 추출, 없으면 전문."""
    out: list[str] = []
    grabbing = False
    for line in text.splitlines():
        if re.match(r"^##\s+Review guidelines", line, re.I):
            grabbing = True
            out.append(line)
            continue
        if grabbing and re.match(r"^##\s+\S", line):
            break
        if grabbing:
            out.append(line)
    return "\n".join(out).strip() or text.strip()


def build_messages(guidelines: str, diff: str) -> list[dict]:
    system = f"""너는 PicTrip 모노레포의 시니어 코드 리뷰어다. 아래 프로젝트 리뷰 가이드라인에 따라
주어진 PR diff를 리뷰한다.

{guidelines}

# 심각도(severity)
- P1: 반드시 고쳐야 함 — 정확성 버그, 명백한 로직 오류, 보안 문제, 모듈 경계/모노레포 불변식
  위반, KTO 컴플라이언스 위반, 커밋된 시크릿.
- P2: 고치는 게 좋음 — 잠재적 버그, 누락된 엣지 케이스, 규약(JSend 봉투/AppError/네이밍) 위반.
- P3: 사소한 개선 — 가독성, 중복 제거 등. 확신이 낮거나 스타일 취향 수준이면 아예 생략하라.

# 규칙
- 실제 문제만 지적한다. 사소한 스타일 잔소리는 건너뛴다. 문제가 없으면 findings를 빈 배열로 둔다.
- 각 finding은 diff에 실제로 나타난 코드 줄을 가리켜야 한다. line은 그 파일의 새 파일(RIGHT) 기준
  줄 번호다. 삭제된 줄을 가리킬 때만 side를 "LEFT"로 하고 line은 옛 파일 기준 줄 번호로 한다.
- 코멘트는 한국어로, 간결하고 구체적으로. 무엇이 왜 문제인지 + 가능하면 고칠 방향.

# 출력(엄격한 JSON, 코드펜스 없이 이 객체 하나만 출력)
{{
  "summary": "PR 전반에 대한 1~3문장 한국어 요약",
  "findings": [
    {{"path": "backend/app/...", "line": 120, "side": "RIGHT",
      "severity": "P2", "title": "짧은 제목", "comment": "한국어 상세 설명"}}
  ]
}}"""
    user = f"다음은 리뷰할 PR의 unified diff다:\n\n```diff\n{diff}\n```"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_codexproxy(url: str, model: str, effort: str, messages: list[dict]) -> str:
    payload = {"model": model, "messages": messages, "reasoning": {"effort": effort}, "stream": False}
    req = urllib.request.Request(
        f"{url}/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def parse_findings(content: str) -> dict:
    """모델 응답에서 JSON 객체 추출(코드펜스/잡음 허용)."""
    text = re.sub(r"^```(?:json)?\s*", "", content.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def main() -> None:
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    pr = env("PR_NUMBER")
    proxy_url = env("CODEXPROXY_URL", "http://127.0.0.1:8787")
    model = env("REVIEW_MODEL", "gpt-5.5")
    effort = env("REVIEW_EFFORT", "high")
    guidelines_file = env("GUIDELINES_FILE", "AGENTS.md")

    diff = fetch_diff(repo, pr, token)
    if not diff.strip():
        print("[pr_review] diff 없음 — 종료")
        return
    truncated = len(diff) > MAX_DIFF_CHARS
    diff_for_prompt = diff[:MAX_DIFF_CHARS] + ("\n\n… (diff 길이 초과로 잘림)" if truncated else "")

    commentable = parse_diff(diff)
    try:
        with open(guidelines_file, encoding="utf-8") as f:
            guidelines = extract_guidelines(f.read())
    except OSError:
        guidelines = "(가이드라인 파일을 찾지 못함 — 일반 코드 리뷰 원칙 적용)"

    messages = build_messages(guidelines, diff_for_prompt)
    print(f"[pr_review] codexproxy 호출: model={model} effort={effort} diff={len(diff)}자")
    content = call_codexproxy(proxy_url, model, effort, messages)

    try:
        result = parse_findings(content)
    except json.JSONDecodeError:
        print("[pr_review] 모델 JSON 파싱 실패, 원문 요약으로 게시")
        post_review(repo, pr, token, {"event": "COMMENT",
                    "body": "🤖 자동 리뷰: 응답 파싱 실패\n\n" + content[:60000]})
        return

    summary = (result.get("summary") or "").strip()
    findings = result.get("findings") or []
    findings.sort(key=lambda f: SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 9))

    inline: list[dict] = []
    unplaced_cards: list[str] = []
    counts = {"P1": 0, "P2": 0, "P3": 0}
    for f in findings:
        sev = str(f.get("severity", "")).upper()
        sev = sev if sev in SEVERITY_ORDER else "P3"
        path = f.get("path", "")
        side = str(f.get("side", "RIGHT")).upper()
        side = side if side in ("LEFT", "RIGHT") else "RIGHT"
        title = (f.get("title") or "").strip()
        comment = (f.get("comment") or "").strip()
        try:
            line = int(f.get("line"))
        except (TypeError, ValueError):
            line = -1
        counts[sev] += 1
        dot = SEV_EMOJI[sev]
        loc = f"`{path}`" + (f":{line}" if line > 0 else "")
        if path in commentable and line in commentable[path].get(side, set()):
            label = f"{dot} **{sev}** · {title}" if title else f"{dot} **{sev}**"
            inline.append({"path": path, "line": line, "side": side, "body": f"{label}\n\n{comment}"})
        else:
            heading = f"{dot} {sev} · {title}" if title else f"{dot} {sev} · {loc}"
            unplaced_cards.append(
                f"<details>\n<summary>{heading}</summary>\n\n{loc} — {comment}\n\n</details>"
            )

    top = next((s for s in ("P1", "P2", "P3") if counts[s]), None)
    kind = ALERT_BY_TOP.get(top, "TIP")
    alert_lines: list[str] = []
    if summary:
        alert_lines.extend(summary.splitlines())
    if findings:
        if alert_lines:
            alert_lines.append("")
        alert_lines.append(f"**P1 {counts['P1']} · P2 {counts['P2']} · P3 {counts['P3']}**")
    else:
        alert_lines.append("지적 사항 없음.")
    if truncated:
        alert_lines += ["", "_diff가 커서 일부만 리뷰했습니다._"]

    parts = [f"> [!{kind}]"]
    parts += [f"> {ln}" if ln else ">" for ln in alert_lines]
    body_md = "## Automated Code Review\n\n" + "\n".join(parts)
    if unplaced_cards:
        body_md += "\n\n### diff 범위 밖 지적 (인라인 불가)\n\n" + "\n\n".join(unplaced_cards)

    code, msg = post_review(repo, pr, token, {"event": "COMMENT", "body": body_md, "comments": inline})
    if code == 200:
        print(f"[pr_review] 리뷰 게시 완료 — 인라인 {len(inline)}건, 요약수록 {len(unplaced_cards)}건")
        return

    print(f"[pr_review] 인라인 리뷰 실패({code}): {msg[:300]}")
    fallback = body_md + "\n\n### 인라인 게시 실패로 본문에 수록\n\n" + "\n\n".join(
        f"<details>\n<summary>{c['body'].splitlines()[0]}</summary>\n\n"
        f"`{c['path']}`:{c['line']}\n\n{c['body']}\n\n</details>"
        for c in inline
    )
    code2, msg2 = post_review(repo, pr, token, {"event": "COMMENT", "body": fallback})
    print(f"[pr_review] 폴백 요약 게시: {code2} {msg2[:200]}")


if __name__ == "__main__":
    main()
