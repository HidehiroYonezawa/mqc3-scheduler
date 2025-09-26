"""Job queue module."""

import sys
from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
from itertools import islice

from pb.mqc3_cloud.program.v1 import quantum_program_pb2
from utility import get_current_datetime

from .job_priority import JobPriority, JobPriorityFactory, PriorityFactorWeights


@dataclass
class JobQueueEntry:
    """Job queue entry class."""

    token: str
    program: quantum_program_pb2.QuantumProgram
    priority: JobPriority

    @cached_property
    def bytes(self) -> int:
        """Return the size of the job queue entry object in bytes.

        Returns:
            int: The size of the job queue entry object in bytes.
        """
        return sys.getsizeof(self) + sys.getsizeof(self.token) + self.program.ByteSize() + sys.getsizeof(self.priority)

    def calc_priority(self, current_time: datetime, max_age: timedelta) -> float:
        """Calculate the priority of the job.

        Args:
            current_time (datetime): Current time.
            max_age (timedelta): Maximum waiting time used to calculate the age factor.

        Returns:
            float: The priority of the job.
        """
        return self.priority.calc_priority(current_time=current_time, max_age=max_age)


class JobQueue:
    """Job queue class."""

    def __init__(
        self,
        capacity_bytes: int,
        max_jobs_to_consider: int = 10,
        max_waiting_time_per_job: timedelta = timedelta(minutes=30),
        max_concurrent_jobs_per_token: dict[str, int] | None = None,
    ) -> None:
        """Initialize the job queue.

        Args:
            capacity_bytes (int): The maximum number of bytes that the job queue can store.
            max_jobs_to_consider (int): The maximum number of jobs to consider when calculating the priority.
            max_waiting_time_per_job (timedelta): The maximum waiting time per job.
            max_concurrent_jobs_per_token (dict[str, int] | None):
                Mapping from role to the maximum number of concurrent jobs per token.

                Limits the number of jobs a single token can have concurrently for each role.
                If this is ``None`` or the role is not present in the mapping, no limit is applied.
        """
        self.capacity_bytes: int = capacity_bytes
        self.max_jobs_to_consider: int = max_jobs_to_consider
        self.max_waiting_time_per_job: timedelta = max_waiting_time_per_job
        self.max_concurrent_jobs_per_token: dict[str, int] = max_concurrent_jobs_per_token or {}

        self.current_bytes: int = 0
        self.jobs: OrderedDict[str, JobQueueEntry] = OrderedDict()
        self.token_job_counts: dict[str, int] = defaultdict(int)

        self.job_priority_factory = JobPriorityFactory(
            factor_weights=PriorityFactorWeights(
                timeout_factor=1000, role_factor=0, age_factor=2000, fair_share_factor=1000
            ),
            burst_score_half_life=timedelta(minutes=1),
            burst_penalty=2,
        )

    def try_push(  # noqa: PLR0913
        self,
        *,
        job_id: str,
        program: quantum_program_pb2.QuantumProgram,
        token: str,
        role: str,
        queued_at: datetime,
        timeout: timedelta,
    ) -> bool:
        """Push a job onto the job queue.

        Args:
            job_id (str): The job ID.
            program (quantum_program_pb2.QuantumProgram): The program of the job.
            token (str): Token of the job submitter.
            role (str): The role of the job submitter.
            queued_at (datetime): The time when the job was queued.
            timeout (timedelta): Timeout of the job.

        Raises:
            ValueError: If the job ID already exists in the queue.

        Returns:
            bool: True if the job was successfully pushed onto the queue, False otherwise.
        """
        if job_id in self.jobs:
            msg = f"Failed to push job {job_id}: Job ID already exists."
            raise ValueError(msg)

        if (
            role in self.max_concurrent_jobs_per_token
            and self.token_job_counts[token] >= self.max_concurrent_jobs_per_token[role]
        ):
            return False

        job_priority = self.job_priority_factory.create(token=token, role=role, queued_at=queued_at, timeout=timeout)
        job = JobQueueEntry(token=token, program=program, priority=job_priority)

        if self.current_bytes + job.bytes > self.capacity_bytes:
            return False

        job_priority.burst_score_manager.update_burst_score(token=token, current_time=queued_at)

        self.current_bytes += job.bytes
        self.jobs[job_id] = job
        self.token_job_counts[token] += 1
        return True

    def try_pop(self) -> tuple[str, quantum_program_pb2.QuantumProgram] | None:
        """Pop a job of the highest priority from the queue and return it.

        Returns:
            tuple[str, quantum_program_pb2.QuantumProgram] | None:
            Job ID and the program of the highest priority job or None if the queue is empty.
        """
        if not self.jobs:
            return None

        num_jobs_to_consider = min(self.max_jobs_to_consider, len(self.jobs))
        candidate_job_ids = list(islice(self.jobs.keys(), num_jobs_to_consider))

        current_time = get_current_datetime()

        earliest_exceeding_job_id = None

        for job_id in candidate_job_ids:
            waiting_time = self.jobs[job_id].priority.get_waiting_time(current_time=current_time)
            if waiting_time > self.max_waiting_time_per_job and earliest_exceeding_job_id is None:
                earliest_exceeding_job_id = job_id

        if earliest_exceeding_job_id is not None:
            job_id = earliest_exceeding_job_id
        else:
            # Find the highest priority job
            job_id = max(
                candidate_job_ids,
                key=lambda job_id: self.jobs[job_id].calc_priority(
                    current_time=current_time, max_age=self.max_waiting_time_per_job
                ),
            )

        job = self.jobs.pop(job_id)
        self.current_bytes -= job.bytes
        self.token_job_counts[job.token] -= 1
        if self.token_job_counts[job.token] == 0:
            del self.token_job_counts[job.token]
        return job_id, job.program

    def try_remove(self, job_id: str) -> bool:
        """Remove a job from the queue.

        Args:
            job_id (str): The job ID.

        Returns:
            bool: True if the job was successfully removed, False if it did not exist in the queue.
        """
        if job_id not in self.jobs:
            return False

        job = self.jobs.pop(job_id)
        self.current_bytes -= job.bytes
        self.token_job_counts[job.token] -= 1
        if self.token_job_counts[job.token] == 0:
            del self.token_job_counts[job.token]
        return True


class JobQueueContainer:
    """Container for multiple job queues."""

    def __init__(  # noqa: PLR0913
        self,
        backends: Iterable[str],
        capacity_bytes: int,
        max_jobs_to_consider: int = 10,
        max_waiting_time_per_job: timedelta = timedelta(minutes=30),
        max_concurrent_jobs_per_token: dict[str, int] | None = None,
        *,
        unify_backends: bool = False,
    ) -> None:
        """Initialize a JobQueueContainer.

        Args:
            backends (Iterable[str]): A list of backend names.
            capacity_bytes (int): The maximum number of bytes that the job queue can store.
            max_jobs_to_consider (int): The maximum number of jobs to consider when calculating the priority.
            max_waiting_time_per_job (timedelta): The maximum waiting time per job.
            max_concurrent_jobs_per_token (dict[str, int] | None):
                Mapping from role to the maximum number of concurrent jobs per token.

                Limits the number of jobs a single token can have concurrently for each role.
                If this is ``None`` or the role is not present in the mapping, no limit is applied.
            unify_backends (bool): Whether to treat backends as a single group or handle them individually.
                - If True, all backends are treated as a single virtual backend named `all`.
                - If False, each backend is treated separately.
        """
        self.unify_backends = unify_backends

        if unify_backends:
            self.queues = {
                "all": JobQueue(
                    capacity_bytes=capacity_bytes,
                    max_jobs_to_consider=max_jobs_to_consider,
                    max_waiting_time_per_job=max_waiting_time_per_job,
                    max_concurrent_jobs_per_token=max_concurrent_jobs_per_token,
                )
            }
        else:
            self.queues = {
                backend: JobQueue(
                    capacity_bytes=capacity_bytes,
                    max_jobs_to_consider=max_jobs_to_consider,
                    max_waiting_time_per_job=max_waiting_time_per_job,
                    max_concurrent_jobs_per_token=max_concurrent_jobs_per_token,
                )
                for backend in backends
            }

    def __getitem__(self, key: str) -> JobQueue:
        """Get a queue by key.

        If unify_backends is True, the key is ignored and the `all` queue is returned.

        Args:
            key (str): The key to get the queue for.

        Returns:
            JobQueue: The queue for the given key.
        """
        return self.queues["all"] if self.unify_backends else self.queues[key]

    def __contains__(self, key: str) -> bool:
        """Check if a queue exists for the given key.

        If unify_backends is True, this always returns True.

        Args:
            key (str): The key to check for.

        Returns:
            bool: True if the queue exists, False otherwise.
        """
        return True if self.unify_backends else key in self.queues
