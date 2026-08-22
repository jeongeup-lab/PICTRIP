"""DAG 실행 결과를 Discord 웹훅에 표로 보낸다.

jq·gh 를 안 쓰는 이유는 실측이다 — 2026-08-22 기준 CT111·CT112 러너 어디에도
없다(`pct exec 111 -- command -v jq gh`). python3 는 양쪽 다 /usr/bin/python3 로
있다. curl 도 있지만 표 정렬·JSON 조립·API 두 번 호출을 셸로 하면 jq 가 필요해진다.

잡 목록을 워크플로에서 넘겨받지 않고 Actions API 로 자기 run 을 되읽는 이유:
needs.<job>.result 로는 소요 시간을 알 수 없고, 잡이 늘 때마다 heartbeat 의
표현식을 같이 고쳐야 한다.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
KST = timezone(timedelta(hours=9), "KST")

COLOR_OK = 3066993
COLOR_FAILED = 15158332
COLOR_RECOVERED = 16098851

OK = "ok"
FAILED = "FAILED"

BAD = ("failure", "cancelled", "timed_out", "action_required")
"""잡 타임아웃은 failure 가 아니라 cancelled 로 찍힌다 — 2026-08-18 월간 ETL 이
timeout-minutes: 120 에 걸렸을 때가 그랬다. failure 만 보면 그게 초록으로 나간다."""

_NAME_WIDTH = 15
_RESULT_WIDTH = 9
_TIME_WIDTH = 7


def _get(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pictrip-dag-notifier",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


NETWORK_ERRORS = (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError)


def fetch_or_none(url: str, token: str) -> dict | None:
    """알림 인프라 장애가 DAG 를 실패시키면 안 된다.

    상류 잡이 전부 성공해도 Actions API 가 5xx 를 한 번 뱉으면 heartbeat 잡이
    죽고 워크플로가 실패로 남는다. 그 가짜 실패는 다음 실행에서 잘못된
    RECOVERED 알림으로 한 번 더 번진다.
    """
    try:
        return _get(url, token)
    except NETWORK_ERRORS:
        return None


def duration(started: str | None, completed: str | None) -> str:
    if not started or not completed:
        return "-"
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    seconds = int(
        (datetime.strptime(completed, fmt) - datetime.strptime(started, fmt)).total_seconds()
    )
    if seconds < 0:
        return "-"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def result_of(job: dict) -> str:
    conclusion = job.get("conclusion")
    if conclusion == "success":
        return OK
    if conclusion == "failure":
        return FAILED
    return conclusion or "running"


def is_bad(job: dict) -> bool:
    return job.get("conclusion") in BAD


def short_name(name: str) -> str:
    """재사용 워크플로 잡은 'warm / warm' 처럼 이름이 겹쳐 온다."""
    left, sep, right = name.partition(" / ")
    return left if sep and left == right else name


def collect_jobs(run_jobs: list[dict], self_job: str) -> list[dict]:
    """heartbeat 자신은 호출 시점에 아직 in_progress 라 표에서 뺀다."""
    return [
        {**j, "name": short_name(j.get("name", "?"))}
        for j in run_jobs
        if j.get("name") != self_job
    ]


def render_table(jobs: list[dict]) -> str:
    rows = [
        f"{'JOB':<{_NAME_WIDTH}}  {'RESULT':<{_RESULT_WIDTH}}  {'TIME':>{_TIME_WIDTH}}",
        f"{'-' * _NAME_WIDTH}  {'-' * _RESULT_WIDTH}  {'-' * _TIME_WIDTH}",
    ]
    for job in jobs:
        name = job.get("name", "?")
        if len(name) > _NAME_WIDTH:
            name = name[: _NAME_WIDTH - 1] + "."
        elapsed = "-" if job.get("conclusion") == "skipped" else duration(
            job.get("started_at"), job.get("completed_at")
        )
        rows.append(
            f"{name:<{_NAME_WIDTH}}  {result_of(job):<{_RESULT_WIDTH}}  {elapsed:>{_TIME_WIDTH}}"
        )
    return "\n".join(rows)


def failed_links(jobs: list[dict]) -> list[str]:
    return [f"[{j.get('name')}]({j.get('html_url')})" for j in jobs if is_bad(j)]


def overall(jobs: list[dict]) -> str:
    return FAILED if any(is_bad(j) for j in jobs) else OK


def build_payload(dag: str, jobs: list[dict], started_at: str, footer: str, recovered: bool) -> dict:
    status = overall(jobs)
    if status == FAILED:
        title, color = f"{dag}  {FAILED}", COLOR_FAILED
    elif recovered:
        title, color = f"{dag}  RECOVERED", COLOR_RECOVERED
    else:
        title, color = f"{dag}  {OK}", COLOR_OK

    when = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    lines = [
        when.astimezone(KST).strftime("%Y-%m-%d %H:%M KST"),
        "",
        "```",
        render_table(jobs),
        "```",
    ]
    links = failed_links(jobs)
    if links:
        lines.append("failed: " + "  ".join(links))
    return {
        "embeds": [
            {"title": title, "description": "\n".join(lines), "color": color, "footer": {"text": footer}}
        ]
    }


def previous_run_failed(repo: str, workflow: str, run_id: int, token: str) -> bool:
    """직전 완료 실행이 실패였는지 — 복구 알림을 한 번만 보내려고 본다."""
    data = fetch_or_none(
        f"{API}/repos/{repo}/actions/workflows/{workflow}/runs"
        "?status=completed&per_page=5&exclude_pull_requests=true",
        token,
    )
    if data is None:
        return False
    for run in data.get("workflow_runs", []):
        if run.get("id") != run_id:
            return run.get("conclusion") in BAD
    return False


def post(url: str, payload: dict) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "pictrip-dag-notifier"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main() -> int:
    webhook = os.environ.get("DISCORD_URL", "").strip()
    if not webhook:
        print("::notice::DISCORD_WEBHOOK_URL 미설정 — Discord 알림 생략")
        return 0

    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = int(os.environ["GITHUB_RUN_ID"])
    token = os.environ["GITHUB_TOKEN"]
    dag = os.environ["DAG"]
    always = os.environ.get("ALWAYS", "false").lower() == "true"
    self_job = os.environ.get("SELF_JOB", "heartbeat")

    run = fetch_or_none(f"{API}/repos/{repo}/actions/runs/{run_id}", token)
    payload_jobs = fetch_or_none(f"{API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token)
    if run is None or payload_jobs is None:
        print("::warning::Actions API 조회 실패 — Discord 알림 생략")
        return 0

    jobs = collect_jobs(payload_jobs.get("jobs", []), self_job)
    if not jobs:
        print("::warning::잡 목록이 비었다 — Discord 알림 생략")
        return 0

    status = overall(jobs)
    recovered = status == OK and previous_run_failed(
        repo, os.environ["WORKFLOW_FILE"], run_id, token
    )
    if status == OK and not always and not recovered:
        print("::notice::성공 + always=false + 복구 아님 — Discord 알림 생략")
        return 0

    footer = f"run {run_id} . {run.get('head_branch')} {(run.get('head_sha') or '')[:7]}"
    payload = build_payload(dag, jobs, run["run_started_at"], footer, recovered)

    if os.environ.get("DRY_RUN", "").lower() == "true":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        post(webhook, payload)
    except NETWORK_ERRORS as exc:
        print(f"::warning::Discord 전송 실패: {exc}")
        return 0
    print(f"discord sent: {dag} {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
