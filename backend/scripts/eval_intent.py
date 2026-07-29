from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.modules.agent.schemas import QueryIntent
from app.modules.agent.services import intent as intent_service

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "tests" / "data" / "intent_golden.jsonl"

BOOL_FIELDS = ("festivalOnly", "indoorOnly", "nearMe", "outOfScope")
ENUM_FIELDS = ("crowdPreference",)
SET_FIELDS = ("categoryKeywords", "regionHints", "moodHints")
PLACE_FIELD = "namedPlaces"
ROUTING_FIELDS = ("outOfScope", "festivalOnly", "indoorOnly", "nearMe")
REGION_SUFFIXES = ("특별자치도", "광역시", "특별시", "도", "시", "군", "구")


@dataclass(slots=True)
class Case:
    id: str
    question: str
    expect: dict[str, Any]


@dataclass(slots=True)
class FieldScore:
    total: float = 0.0
    scored: int = 0

    def add(self, value: float) -> None:
        self.total += value
        self.scored += 1

    @property
    def ratio(self) -> float:
        return self.total / self.scored if self.scored else 1.0


@dataclass(slots=True)
class Outcome:
    case: Case
    latency_ms: float
    intent: QueryIntent | None = None
    error: str | None = None
    misses: dict[str, tuple[Any, Any]] = field(default_factory=dict)


def load_cases(path: Path, limit: int | None) -> list[Case]:
    cases: list[Case] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw = json.loads(stripped)
        cases.append(Case(id=raw["id"], question=raw["q"], expect=raw["expect"]))
    return cases[:limit] if limit else cases


def normalize_region(token: str) -> str:
    cleaned = token.strip()
    for suffix in REGION_SUFFIXES:
        if len(cleaned) - len(suffix) >= 2 and cleaned.endswith(suffix):
            return cleaned[: -len(suffix)]
    return cleaned


def region_tokens(values: list[str]) -> set[str]:
    return {normalize_region(part) for value in values for part in value.split() if part.strip()}


def plain_tokens(values: list[str]) -> set[str]:
    return {value.strip() for value in values if value.strip()}


def f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    hits = len(expected & actual)
    if hits == 0:
        return 0.0
    precision = hits / len(actual)
    recall = hits / len(expected)
    return 2 * precision * recall / (precision + recall)


def place_names(intent: QueryIntent) -> set[str]:
    return {(place.nameKo or place.name).strip() for place in intent.namedPlaces}


def score_case(
    case: Case, intent: QueryIntent
) -> tuple[dict[str, float], dict[str, tuple[Any, Any]]]:
    scores: dict[str, float] = {}
    misses: dict[str, tuple[Any, Any]] = {}

    for name in (*BOOL_FIELDS, *ENUM_FIELDS):
        if name not in case.expect:
            continue
        actual = getattr(intent, name)
        expected = case.expect[name]
        scores[name] = 1.0 if actual == expected else 0.0
        if actual != expected:
            misses[name] = (expected, actual)

    for name in SET_FIELDS:
        if name not in case.expect:
            continue
        actual_values = list(getattr(intent, name))
        expected_values = list(case.expect[name])
        if name == "regionHints":
            value = f1(region_tokens(expected_values), region_tokens(actual_values))
        else:
            value = f1(plain_tokens(expected_values), plain_tokens(actual_values))
        scores[name] = value
        if value < 1.0:
            misses[name] = (expected_values, actual_values)

    if PLACE_FIELD in case.expect:
        expected_places = plain_tokens(list(case.expect[PLACE_FIELD]))
        actual_places = place_names(intent)
        value = f1(expected_places, actual_places)
        scores[PLACE_FIELD] = value
        if value < 1.0:
            misses[PLACE_FIELD] = (sorted(expected_places), sorted(actual_places))

    return scores, misses


async def run_case(case: Case, semaphore: asyncio.Semaphore, spacing: float) -> Outcome:
    async with semaphore:
        started = time.perf_counter()
        try:
            intent = await intent_service.extract_intent(case.question)
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            await asyncio.sleep(spacing)
            return Outcome(case=case, latency_ms=elapsed, error=f"{type(exc).__name__}: {exc}")
        elapsed = (time.perf_counter() - started) * 1000
        await asyncio.sleep(spacing)
        _, misses = score_case(case, intent)
        return Outcome(case=case, latency_ms=elapsed, intent=intent, misses=misses)


async def evaluate(cases: list[Case], concurrency: int, rpm: float) -> list[Outcome]:
    semaphore = asyncio.Semaphore(concurrency)
    spacing = (60.0 / rpm) * concurrency if rpm > 0 else 0.0
    return list(await asyncio.gather(*(run_case(case, semaphore, spacing) for case in cases)))


def report(outcomes: list[Outcome], model: str) -> int:
    per_field: dict[str, FieldScore] = {}
    routing = FieldScore()
    exact = 0
    errors = [outcome for outcome in outcomes if outcome.error is not None]
    latencies = [outcome.latency_ms for outcome in outcomes if outcome.error is None]

    for outcome in outcomes:
        if outcome.intent is None:
            continue
        scores, misses = score_case(outcome.case, outcome.intent)
        for name, value in scores.items():
            per_field.setdefault(name, FieldScore()).add(value)
            if name in ROUTING_FIELDS:
                routing.add(value)
        if not misses:
            exact += 1

    scored = len(outcomes) - len(errors)
    print(f"\nmodel: {model}")
    print(f"cases: {len(outcomes)}   scored: {scored}   errors: {len(errors)}")
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        print(f"latency: p50 {statistics.median(ordered):.0f}ms   p95 {p95:.0f}ms")
    print(f"exact-match cases: {exact}/{scored}" if scored else "exact-match cases: 0/0")
    print(f"routing fields (outOfScope/festival/indoor/near): {routing.ratio:.3f}\n")

    print(f"{'field':<20}{'score':>8}{'n':>6}")
    print("-" * 34)
    for name in sorted(per_field):
        score = per_field[name]
        print(f"{name:<20}{score.ratio:>8.3f}{score.scored:>6}")

    failures = [o for o in outcomes if o.misses or o.error]
    if failures:
        print(f"\n{len(failures)} case(s) with a miss:\n")
        for outcome in failures:
            print(f"  [{outcome.case.id}] {outcome.case.question}")
            if outcome.error:
                print(f"      error: {outcome.error}")
            for name, (expected, actual) in outcome.misses.items():
                print(f"      {name}: expected {expected!r} got {actual!r}")

    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Score intent extraction against the golden set.")
    parser.add_argument("--model", help="override GEMINI_MODEL for this run")
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--rpm", type=float, default=10.0, help="0 disables pacing")
    parser.add_argument("--json", type=Path, default=None, help="write raw outcomes here")
    args = parser.parse_args()

    if args.model:
        settings.GEMINI_MODEL = args.model
    if not settings.GEMINI_API_KEY:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2

    cases = load_cases(args.golden, args.limit)
    if not cases:
        print(f"no cases in {args.golden}", file=sys.stderr)
        return 2

    outcomes = asyncio.run(evaluate(cases, args.concurrency, args.rpm))

    if args.json:
        args.json.write_text(
            json.dumps(
                [
                    {
                        "id": outcome.case.id,
                        "q": outcome.case.question,
                        "expect": outcome.case.expect,
                        "actual": outcome.intent.model_dump() if outcome.intent else None,
                        "error": outcome.error,
                        "latencyMs": round(outcome.latency_ms),
                    }
                    for outcome in outcomes
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return report(outcomes, settings.GEMINI_MODEL)


if __name__ == "__main__":
    raise SystemExit(main())
