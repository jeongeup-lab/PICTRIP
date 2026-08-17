from __future__ import annotations

import math

from app.modules.spots.visual_job import (
    AESTHETIC_PROMPTS,
    TYPE_PROMPTS,
    build_anchors,
    score_embedding,
)

_AXES = {
    "interior": [1.0, 0.0, 0.0, 0.0],
    "exterior": [0.0, 1.0, 0.0, 0.0],
    "food": [0.0, 0.0, 1.0, 0.0],
    "view": [0.0, 0.0, 0.0, 1.0],
}


def fake_embed_texts(prompts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for prompt in prompts:
        for key, prompt_list in TYPE_PROMPTS.items():
            if prompt in prompt_list:
                out.append(_AXES[key])
                break
        else:
            for key, (pos, neg) in AESTHETIC_PROMPTS.items():
                if prompt in pos:
                    vec = [x * 0.5 for x in _AXES[key]]
                    vec[(list(_AXES).index(key) + 1) % 4] += 0.5
                    out.append(vec)
                    break
                if prompt in neg:
                    out.append([-x for x in _AXES[key]])
                    break
            else:
                raise AssertionError(f"unknown prompt: {prompt}")
    return out


def test_anchors_are_unit_length() -> None:
    anchors = build_anchors(fake_embed_texts)
    for vec in anchors.type_vectors:
        assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-6)


def test_classifies_by_the_nearest_type_anchor() -> None:
    anchors = build_anchors(fake_embed_texts)

    photo_type, _ = score_embedding([0.9, 0.1, 0.0, 0.0], anchors)
    assert photo_type == "interior"

    photo_type, _ = score_embedding([0.0, 0.0, 0.1, 2.0], anchors)
    assert photo_type == "view"


def test_aesthetic_score_rewards_positive_anchor_direction() -> None:
    anchors = build_anchors(fake_embed_texts)

    _, aligned = score_embedding([1.0, 0.0, 0.0, 0.0], anchors)
    _, opposed = score_embedding([1.0, -3.0, 0.0, 0.0], anchors)

    assert aligned > 0
    assert aligned > opposed


def test_score_handles_unnormalized_input() -> None:
    anchors = build_anchors(fake_embed_texts)

    t1, s1 = score_embedding([2.0, 0.0, 0.0, 0.0], anchors)
    t2, s2 = score_embedding([1.0, 0.0, 0.0, 0.0], anchors)

    assert (t1, round(s1, 9)) == (t2, round(s2, 9))
