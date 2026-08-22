"""notify.py 포맷터 회귀 — 표준 라이브러리만 쓴다(러너에 pytest 가 없다).

`python3 test_notify.py` 로 돌리고, pr-check 의 discord-action 잡이 이걸 친다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import notify


def _job(name: str, conclusion: str | None, start: str = "T00:00:00Z", end: str = "T00:00:09Z"):
    return {
        "name": name,
        "conclusion": conclusion,
        "started_at": f"2026-08-23{start}",
        "completed_at": f"2026-08-23{end}",
        "html_url": f"https://example.test/{name}",
    }


def test_timeout_is_not_green() -> None:
    """잡 타임아웃은 failure 가 아니라 cancelled 로 찍힌다 — 2026-08-18 월간 ETL."""
    assert notify.overall([_job("overseas-etl", "cancelled")]) == notify.FAILED
    assert notify.overall([_job("x", "timed_out")]) == notify.FAILED


def test_intentional_skip_is_not_a_failure() -> None:
    assert notify.overall([_job("embed", "skipped")]) == notify.OK
    assert notify.overall([_job("a", "success"), _job("b", "skipped")]) == notify.OK


def test_failure_wins_over_success() -> None:
    assert notify.overall([_job("a", "success"), _job("b", "failure")]) == notify.FAILED


def test_reusable_workflow_name_is_collapsed() -> None:
    collected = notify.collect_jobs([_job("warm / warm", "success")], "heartbeat")
    assert collected[0]["name"] == "warm"


def test_self_job_is_excluded() -> None:
    jobs = [_job("heartbeat", None), _job("embed", "success")]
    assert [j["name"] for j in notify.collect_jobs(jobs, "heartbeat")] == ["embed"]


def test_every_row_is_the_same_width() -> None:
    jobs = notify.collect_jobs(
        [
            _job("sync-kto", "success"),
            _job("a-very-long-job-name-here", "cancelled"),
            _job("embed", "skipped"),
        ],
        "heartbeat",
    )
    widths = {len(line) for line in notify.render_table(jobs).splitlines()}
    assert widths == {35}, widths


def test_skipped_shows_a_dash_not_zero() -> None:
    table = notify.render_table(notify.collect_jobs([_job("embed", "skipped")], "heartbeat"))
    assert table.splitlines()[-1].endswith("      -")


def test_duration_formats_past_an_hour() -> None:
    assert notify.duration("2026-01-01T00:00:00Z", "2026-01-01T02:01:07Z") == "121m07s"
    assert notify.duration(None, None) == "-"


def test_failed_links_cover_cancelled() -> None:
    jobs = [_job("a", "success"), _job("b", "cancelled"), _job("c", "failure")]
    assert len(notify.failed_links(jobs)) == 2


def test_payload_shape() -> None:
    jobs = notify.collect_jobs([_job("embed", "failure")], "heartbeat")
    payload = notify.build_payload(
        "pipeline-daily", jobs, "2026-08-23T20:07:00Z", "run 1 . dev abc", recovered=False
    )
    embed = payload["embeds"][0]
    assert embed["title"] == "pipeline-daily  FAILED"
    assert embed["color"] == notify.COLOR_FAILED
    assert "2026-08-24 05:07 KST" in embed["description"]
    assert embed["description"].count("```") == 2


def test_recovered_only_when_green() -> None:
    green = notify.collect_jobs([_job("embed", "success")], "heartbeat")
    payload = notify.build_payload("d", green, "2026-08-23T20:07:00Z", "f", recovered=True)
    assert payload["embeds"][0]["title"] == "d  RECOVERED"
    red = notify.collect_jobs([_job("embed", "failure")], "heartbeat")
    payload = notify.build_payload("d", red, "2026-08-23T20:07:00Z", "f", recovered=True)
    assert payload["embeds"][0]["title"] == "d  FAILED"


def test_network_error_never_escapes() -> None:
    """알림 인프라 장애로 DAG 가 가짜 실패하면 안 된다 — Codex 리뷰 #329.

    127.0.0.1:9 는 즉시 connection refused 라 밖으로 나가지 않는다.
    """
    assert notify.fetch_or_none("http://127.0.0.1:9/nope", "t") is None


def test_previous_run_lookup_failure_is_not_a_recovery() -> None:
    """조회에 실패했는데 복구로 읽으면 가짜 RECOVERED 가 나간다."""
    original = notify.fetch_or_none
    notify.fetch_or_none = lambda *_args, **_kwargs: None
    try:
        assert notify.previous_run_failed("o/r", "w.yml", 1, "t") is False
    finally:
        notify.fetch_or_none = original


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"  ok  {test.__name__}")
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
