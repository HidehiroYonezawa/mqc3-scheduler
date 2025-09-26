"""Tests for the job priority."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.append(Path(__file__).parents[1].as_posix())

from allpairspy import AllPairs
from job_manager.job_priority import (
    BurstScoreManager,
    JobPriorityFactory,
    PriorityFactorWeights,
    calc_age_factor,
    calc_fair_share_factor,
    calc_role_factor,
    calc_timeout_factor,
    get_role_max_timeout,
)
from utility import get_current_datetime


def test_burst_score_manager_constructor():
    half_life_time = timedelta(minutes=30)
    burst_score_manager = BurstScoreManager(burst_score_half_life=half_life_time)

    assert burst_score_manager.burst_score_half_life == half_life_time
    assert burst_score_manager.token_burst_scores == {}


def test_burst_score_manager_initialization():
    burst_score_manager = BurstScoreManager(burst_score_half_life=timedelta(hours=1))
    token = "test_token"  # noqa: S105

    current_time = get_current_datetime()

    burst_score_manager.update_burst_score(token=token, current_time=current_time)
    burst_score = burst_score_manager.get_burst_score(token=token)

    assert burst_score == 1.0
    assert burst_score_manager.token_burst_scores[token].last_updated_at == current_time


def test_burst_score_update():
    burst_score_manager = BurstScoreManager(burst_score_half_life=timedelta(hours=1))
    token = "test_token"  # noqa: S105

    first_time = get_current_datetime()
    second_time = first_time + timedelta(hours=1)
    third_time = second_time + timedelta(hours=1)

    # First update
    burst_score_manager.update_burst_score(token=token, current_time=first_time)
    burst_score = burst_score_manager.get_burst_score(token=token)
    assert burst_score == 1.0

    # Second update after 1 hour (half-life)
    burst_score_manager.update_burst_score(token=token, current_time=second_time)
    updated_burst_score = burst_score_manager.get_burst_score(token=token)
    assert updated_burst_score == 1.5  # (1 * 0.5) + 1 = 1.5

    # Third update after another 1 hour (half-life)
    burst_score_manager.update_burst_score(token=token, current_time=third_time)
    updated_burst_score = burst_score_manager.get_burst_score(token=token)
    assert updated_burst_score == 1.75  # (1.5 * 0.5) + 1 = 1.75


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 1.0),
        ("Admin", 1.0),
        ("developer", 0.5),
        ("DEVELOPER", 0.5),
        ("guest", 0.0),
        ("Unknown", 0.0),
    ],
)
def test_calc_role_factor(role: str, expected: float):
    assert calc_role_factor(role=role) == expected


@pytest.mark.parametrize(
    ("timeout_seconds", "max_timeout_seconds", "expected"),
    [
        (1, 4, 0.75),
        (0.1, 4, 0.975),
        (255, 256, 1 / 256),
        (1, 0, 0),
        (0, 0, 0),
        (1.001, 1, 0),
        (0.001, 0, 0),
    ],
)
def test_calc_timeout_factor(timeout_seconds: float, max_timeout_seconds: float, expected: float):
    assert (
        calc_timeout_factor(
            timeout=timedelta(seconds=timeout_seconds), role_max_timeout=timedelta(seconds=max_timeout_seconds)
        )
        == expected
    )


@pytest.mark.parametrize(
    ("waiting_seconds", "max_age_seconds", "expected"),
    [
        (1, 1, 1),
        (2, 1, 1),
        (0, 0, 1),
        (0, 1, 0),
        (0.001, 1.024, 1 / 1024),
    ],
)
def test_calc_age_factor(waiting_seconds: float, max_age_seconds: float, expected: float):
    queued_at = get_current_datetime()
    current_time = queued_at + timedelta(seconds=waiting_seconds)
    max_age = timedelta(seconds=max_age_seconds)
    assert calc_age_factor(current_time=current_time, queued_at=queued_at, max_age=max_age) == expected


@pytest.mark.parametrize(
    ("burst_score", "burst_penalty", "expected"),
    [
        (1, 1, 1),
        (2, 1, 0.5),
        (0, 0, 0),
        (1, 0, 0),
        (3, 2, 0.5),
        (1, 2, 1),
    ],
)
def test_calc_fair_share_factor(burst_score: float, burst_penalty: float, expected: float):
    result = calc_fair_share_factor(burst_score=burst_score, burst_penalty=burst_penalty)
    assert result == pytest.approx(expected)


def test_job_priority_constructor():
    token = "test_token"  # noqa: S105
    role = "developer"
    queued_at = get_current_datetime() + timedelta(hours=1)

    factor_weights = PriorityFactorWeights(
        timeout_factor=1000, role_factor=2000, age_factor=3000, fair_share_factor=4000
    )

    job_priority_factory = JobPriorityFactory(
        factor_weights=factor_weights, burst_score_half_life=timedelta(hours=1), burst_penalty=5.0
    )
    priority = job_priority_factory.create(token=token, role=role, queued_at=queued_at, timeout=timedelta(minutes=3))

    assert priority._token == token  # noqa: SLF001
    assert priority._queued_at == queued_at  # noqa: SLF001
    assert priority.factor_weights == factor_weights
    assert (
        priority._base_priority == 1700  # noqa: SLF001
    )  # w_role_factor (2000) * role_factor (0.5) + w_timeout_factor (1000) * timeout_factor (1 - 3 / 10)


@pytest.mark.parametrize(
    argnames=(
        "role",
        "timeout_minutes",
        "w_timeout_factor",
        "w_role_factor",
        "w_age_factor",
        "w_fair_share_factor",
    ),
    argvalues=AllPairs([
        ["admin", "developer", "guest"],
        [0, 1, 15],
        [0, 100, 1000],
        [0, 200, 2000],
        [0, 300, 3000],
        [0, 400, 4000],
    ]),
)
def test_job_priority_calc_priority(
    role: str,
    timeout_minutes: int,
    w_timeout_factor: int,
    w_role_factor: int,
    w_age_factor: int,
    w_fair_share_factor: int,
):
    token = "test_token"  # noqa: S105
    queued_at = get_current_datetime() + timedelta(hours=1)

    factor_weights = PriorityFactorWeights(
        timeout_factor=w_timeout_factor,
        role_factor=w_role_factor,
        age_factor=w_age_factor,
        fair_share_factor=w_fair_share_factor,
    )
    max_age = timedelta(minutes=60)
    current_time = queued_at + timedelta(minutes=15)  # wait 15 minutes
    burst_penalty = 2.0

    job_priority_factory = JobPriorityFactory(
        factor_weights=factor_weights, burst_score_half_life=timedelta(hours=1), burst_penalty=burst_penalty
    )

    priority = job_priority_factory.create(
        token=token, role=role, queued_at=queued_at, timeout=timedelta(minutes=timeout_minutes)
    )

    role_priority = factor_weights.role_factor * calc_role_factor(role=role)
    timeout_priority = factor_weights.timeout_factor * calc_timeout_factor(
        timeout=timedelta(minutes=timeout_minutes), role_max_timeout=get_role_max_timeout(role=role)
    )
    age_priority = factor_weights.age_factor * calc_age_factor(
        queued_at=queued_at, current_time=current_time, max_age=max_age
    )
    fair_share_priority = factor_weights.fair_share_factor * calc_fair_share_factor(
        burst_score=1, burst_penalty=burst_penalty
    )

    assert (
        priority.calc_priority(current_time=current_time, max_age=max_age)
        == role_priority + timeout_priority + age_priority + fair_share_priority
    )
