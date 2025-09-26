"""Tests for the job queue."""

import sys
from pathlib import Path

import pytest

sys.path.append(Path(__file__).parents[1].as_posix())

from datetime import timedelta

from common import construct_sample_program
from job_manager.job_priority import JobPriority
from job_manager.job_queue import JobQueue, JobQueueContainer, JobQueueEntry
from utility import get_current_datetime


def test_job() -> None:
    program = construct_sample_program()

    token = "token"  # noqa: S105
    job = JobQueueEntry(
        token=token,
        program=program,
        priority=JobPriority(
            token=token,
            role="developer",
            queued_at=get_current_datetime(),
            timeout=timedelta(seconds=1),
        ),
    )
    assert job.bytes == sys.getsizeof(job) + sys.getsizeof(token) + program.ByteSize() + sys.getsizeof(job.priority)


def test_job_queue_constructor() -> None:
    max_bytes = 1000
    max_jobs_to_consider = 100
    max_waiting_time_per_job = timedelta(minutes=1)
    max_concurrent_jobs_per_token = {"admin": 3, "developer": 2, "guest": 1}

    job_queue = JobQueue(
        capacity_bytes=max_bytes,
        max_jobs_to_consider=max_jobs_to_consider,
        max_waiting_time_per_job=max_waiting_time_per_job,
        max_concurrent_jobs_per_token=max_concurrent_jobs_per_token,
    )
    assert job_queue.capacity_bytes == max_bytes
    assert job_queue.max_jobs_to_consider == max_jobs_to_consider
    assert job_queue.max_waiting_time_per_job == max_waiting_time_per_job
    assert job_queue.max_concurrent_jobs_per_token == max_concurrent_jobs_per_token

    assert job_queue.current_bytes == 0
    assert job_queue.jobs == {}
    assert job_queue.token_job_counts == {}


def test_job_queue_push_success() -> None:
    job_queue = JobQueue(capacity_bytes=1_000_000_000, max_concurrent_jobs_per_token=None)
    current_time = get_current_datetime()
    token = "token"  # noqa: S105
    for i in range(100):
        assert job_queue.try_push(
            job_id=f"job1{i}",
            program=construct_sample_program(),
            token=token,
            role="developer",
            queued_at=current_time,
            timeout=timedelta(seconds=1),
        )
        assert job_queue.token_job_counts[token] == i + 1
        assert len(job_queue.jobs) == i + 1


def test_job_queue_push_fails_on_capacity_limit() -> None:
    job_queue = JobQueue(capacity_bytes=10)
    current_time = get_current_datetime()
    token = "token"  # noqa: S105
    assert not job_queue.try_push(
        job_id="job1",
        program=construct_sample_program(),
        token=token,
        role="developer",
        queued_at=current_time,
        timeout=timedelta(seconds=1),
    )


def test_job_queue_push_fails_on_duplicate_job_id() -> None:
    job_queue = JobQueue(capacity_bytes=2000)
    current_time = get_current_datetime()
    token = "token"  # noqa: S105
    assert job_queue.try_push(
        job_id="job1",
        program=construct_sample_program(),
        token=token,
        role="developer",
        queued_at=current_time,
        timeout=timedelta(seconds=1),
    )
    assert job_queue.capacity_bytes == 2000
    assert (
        job_queue.current_bytes
        == JobQueueEntry(
            token=token,
            program=construct_sample_program(),
            priority=JobPriority(
                token=token,
                role="developer",
                queued_at=get_current_datetime(),
                timeout=timedelta(seconds=1),
            ),
        ).bytes
    )
    assert job_queue.jobs.keys() == {"job1"}

    with pytest.raises(ValueError, match=r"Failed to push job job1: Job ID already exists."):
        job_queue.try_push(
            job_id="job1",
            program=construct_sample_program(),
            token=token,
            role="developer",
            queued_at=current_time,
            timeout=timedelta(seconds=1),
        )


def test_job_queue_push_fails_on_token_limit() -> None:
    job_queue = JobQueue(capacity_bytes=2000, max_concurrent_jobs_per_token={"developer": 1})
    current_time = get_current_datetime()
    token = "token"  # noqa: S105
    assert job_queue.try_push(
        job_id="job1",
        program=construct_sample_program(),
        token=token,
        role="developer",
        queued_at=current_time,
        timeout=timedelta(seconds=1),
    )
    assert not job_queue.try_push(
        job_id="job2",
        program=construct_sample_program(),
        token=token,
        role="developer",
        queued_at=current_time,
        timeout=timedelta(seconds=1),
    )


def test_job_queue_pop() -> None:
    program = construct_sample_program()

    job_queue = JobQueue(capacity_bytes=1000, max_concurrent_jobs_per_token=None)
    assert job_queue.try_push(
        job_id="job1",
        program=program,
        token="token",  # noqa: S106
        role="developer",
        queued_at=get_current_datetime(),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job2",
        program=program,
        token="token",  # noqa: S106
        role="developer",
        queued_at=get_current_datetime(),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_pop() == ("job1", program)
    assert job_queue.jobs.keys() == {"job2"}
    assert job_queue.token_job_counts == {"token": 1}

    assert job_queue.try_pop() == ("job2", program)
    assert job_queue.capacity_bytes == 1000
    assert job_queue.current_bytes == 0
    assert job_queue.jobs == {}
    assert job_queue.token_job_counts == {}

    assert job_queue.try_pop() is None


def test_job_queue_remove() -> None:
    program = construct_sample_program()

    job_queue = JobQueue(capacity_bytes=1000, max_concurrent_jobs_per_token=None)
    assert job_queue.try_push(
        job_id="job1",
        program=program,
        token="token",  # noqa: S106
        role="developer",
        queued_at=get_current_datetime(),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job2",
        program=program,
        token="token",  # noqa: S106
        role="developer",
        queued_at=get_current_datetime(),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_remove(job_id="job2")
    assert job_queue.jobs.keys() == {"job1"}
    assert job_queue.token_job_counts == {"token": 1}

    assert job_queue.try_remove(job_id="job1")
    assert job_queue.capacity_bytes == 1000
    assert job_queue.current_bytes == 0
    assert job_queue.jobs == {}
    assert job_queue.token_job_counts == {}

    assert not job_queue.try_remove(job_id="job1")
    assert not job_queue.try_remove(job_id="invalid job id")


def test_job_queue_priority() -> None:
    job_queue = JobQueue(capacity_bytes=1000, max_jobs_to_consider=3)

    program = construct_sample_program()
    current_time = get_current_datetime()

    assert job_queue.try_push(
        job_id="job1",
        program=program,
        token="token1",  # noqa: S106
        role="guest",
        queued_at=current_time,
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job2",
        program=program,
        token="token2",  # noqa: S106
        role="admin",
        queued_at=current_time,
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job3",
        program=program,
        token="token3",  # noqa: S106
        role="developer",
        queued_at=current_time,
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job4",
        program=program,
        token="token4",  # noqa: S106
        role="developer",
        queued_at=current_time - timedelta(minutes=30),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job5",
        program=program,
        token="token5",  # noqa: S106
        role="developer",
        queued_at=current_time - timedelta(hours=1),
        timeout=timedelta(milliseconds=900),
    )

    assert job_queue.try_pop() == ("job2", program)  # 2 < 1 < 3
    assert job_queue.try_pop() == ("job4", program)  # 4 < 3 < 1
    assert job_queue.try_pop() == ("job5", program)  # 5 < 3 < 1
    assert job_queue.try_pop() == ("job3", program)  # 3 < 1
    assert job_queue.try_pop() == ("job1", program)  # 1


def test_job_queue_priority_exceed_max_waiting_time() -> None:
    job_queue = JobQueue(capacity_bytes=1000, max_jobs_to_consider=3, max_waiting_time_per_job=timedelta(minutes=30))

    program = construct_sample_program()
    current_time = get_current_datetime()

    assert job_queue.try_push(
        job_id="job1",
        program=program,
        token="token1",  # noqa: S106
        role="admin",
        queued_at=current_time - timedelta(minutes=20),
        timeout=timedelta(milliseconds=1),
    )
    assert job_queue.try_push(
        job_id="job2",
        program=program,
        token="token2",  # noqa: S106
        role="developer",
        queued_at=current_time - timedelta(minutes=40),
        timeout=timedelta(milliseconds=900),
    )
    assert job_queue.try_push(
        job_id="job3",
        program=program,
        token="token3",  # noqa: S106
        role="developer",
        queued_at=current_time - timedelta(minutes=40),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job4",
        program=program,
        token="token4",  # noqa: S106
        role="guest",
        queued_at=current_time - timedelta(minutes=35),
        timeout=timedelta(milliseconds=1000),
    )
    assert job_queue.try_push(
        job_id="job5",
        program=program,
        token="token5",  # noqa: S106
        role="admin",
        queued_at=current_time - timedelta(hours=1),
        timeout=timedelta(milliseconds=1000),
    )

    assert job_queue.try_pop() == ("job2", program)  # 2 < 3 < 1
    assert job_queue.try_pop() == ("job3", program)  # 3 < 4 < 1
    assert job_queue.try_pop() == ("job4", program)  # 4 < 5 < 1
    assert job_queue.try_pop() == ("job5", program)  # 5 < 1
    assert job_queue.try_pop() == ("job1", program)  # 1


def test_job_queue_container_not_unify() -> None:
    backends = ["backend1", "backend2"]
    job_queues = JobQueueContainer(backends, capacity_bytes=1_000_000_000)

    job_queues["backend1"]
    job_queues["backend2"]

    with pytest.raises(KeyError):
        job_queues["invalid"]

    assert "backend1" in job_queues
    assert "backend2" in job_queues
    assert "invalid" not in job_queues


def test_job_queue_container_unify() -> None:
    backends = ["backend1", "backend2"]
    job_queues = JobQueueContainer(
        backends,
        capacity_bytes=1_000_000_000,
        unify_backends=True,
    )

    job_queues["backend1"]
    job_queues["backend2"]
    job_queues["backend3"]

    assert "backend1" in job_queues
    assert "backend2" in job_queues
    assert "backend3" in job_queues
