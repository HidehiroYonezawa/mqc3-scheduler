"""Job priority module."""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property


@dataclass(frozen=True)
class PriorityFactorWeights:
    """Weights of factors for priority calculation."""

    timeout_factor: int
    role_factor: int
    age_factor: int
    fair_share_factor: int


def get_role_max_timeout(role: str) -> timedelta:
    """Get the maximum timeout for the given role.

    Args:
        role (str): The role of the job submitter.

    Returns:
        timedelta: The maximum timeout for the given role.
    """
    role = role.lower()
    if role == "admin":
        return timedelta(minutes=60)
    if role == "developer":
        return timedelta(minutes=10)
    return timedelta(minutes=5)


@dataclass
class BurstScoreInfo:
    """Current burst score and the datetime when this score was last updated."""

    burst_score: float
    last_updated_at: datetime


class BurstScoreManager:
    """Token-based burst score tracking system where scores decay exponentially over time."""

    def __init__(self, burst_score_half_life: timedelta) -> None:
        """Initialize the burst score manager with the given half-life time.

        Args:
            burst_score_half_life (timedelta): Half-life time for burst scores.
        """
        self.burst_score_half_life = burst_score_half_life
        self.token_burst_scores: dict[str, BurstScoreInfo] = {}

    def update_burst_score(self, token: str, current_time: datetime) -> None:
        """Update the burst score for the given token.

        Args:
            token (str): Token for which to update the burst score.
            current_time (datetime): Current time.
        """
        burst_info = self.token_burst_scores.get(token)

        if burst_info is None:
            self.token_burst_scores[token] = BurstScoreInfo(burst_score=1.0, last_updated_at=current_time)
        else:
            elapsed_time = current_time - burst_info.last_updated_at
            decay_rate = 2 ** -(elapsed_time / self.burst_score_half_life)
            new_score = burst_info.burst_score * decay_rate + 1
            self.token_burst_scores[token] = BurstScoreInfo(burst_score=new_score, last_updated_at=current_time)

    def get_burst_score(self, token: str) -> float:
        """Get the burst score of the given token.

        Args:
            token (str): Token.

        Returns:
            float: Burst score of the given token.
        """
        burst_info = self.token_burst_scores.get(token)

        if burst_info is None:
            return 1.0

        return burst_info.burst_score


def calc_role_factor(role: str) -> float:
    """Calculate the role factor.

    Args:
        role (str): Role of the job submitter.

    Returns:
        float: Role factor of the job.
    """
    role = role.lower()
    if role == "admin":
        return 1.0
    if role == "developer":
        return 0.5
    return 0.0


def calc_timeout_factor(timeout: timedelta, role_max_timeout: timedelta) -> float:
    """Calculate the timeout factor.

    Args:
        timeout (timedelta): Timeout of the job.
        role_max_timeout (timedelta): Maximum timeout allowed for the job submitter.

    Returns:
        float: Timeout factor of the job.
    """
    max_timeout_seconds = role_max_timeout.total_seconds()
    timeout_seconds = timeout.total_seconds()

    if max_timeout_seconds <= 0 or timeout_seconds > max_timeout_seconds:
        return 0.0

    return 1 - timeout_seconds / max_timeout_seconds


def calc_age_factor(current_time: datetime, queued_at: datetime, max_age: timedelta) -> float:
    """Calculate the age factor.

    Args:
        current_time (datetime): Current time.
        queued_at (datetime): Queued time of the job.
        max_age (timedelta): Maximum waiting time used to normalize the waiting time of the job.

    Returns:
        float: Age factor of the job.
    """
    waiting_seconds = (current_time - queued_at).total_seconds()
    max_age_seconds = max_age.total_seconds()

    if max_age_seconds <= 0 or waiting_seconds > max_age_seconds:
        return 1.0

    return waiting_seconds / max_age_seconds


def calc_fair_share_factor(burst_score: float, burst_penalty: float) -> float:
    """Calculate the fair share factor from the burst score of the job token.

    Args:
        burst_score (float): Burst score of the job token.
        burst_penalty (float): Burst penalty used to calculate the fair share factor.

    Returns:
        float: Fair share factor of the job.
    """
    if burst_penalty <= 0:
        return 0.0
    if burst_score <= 1:
        return 1.0
    return 2 ** (-((burst_score - 1) / burst_penalty))


class JobPriority:
    """Job priority class."""

    factor_weights: PriorityFactorWeights = PriorityFactorWeights(
        timeout_factor=1000, role_factor=0, age_factor=2000, fair_share_factor=1000
    )
    burst_score_manager: BurstScoreManager = BurstScoreManager(burst_score_half_life=timedelta(minutes=1))
    burst_penalty: float = 2

    @classmethod
    def configure(
        cls, factor_weights: PriorityFactorWeights, burst_score_manager: BurstScoreManager, burst_penalty: float
    ) -> None:
        """Configure the job priority class.

        Args:
            factor_weights (PriorityFactorWeights): Weights of the priority factors.
            burst_score_manager (BurstScoreManager): Burst score manager.
            burst_penalty (float): Burst penalty used to calculate the fair share factor.
        """
        cls.factor_weights = factor_weights
        cls.burst_score_manager = burst_score_manager
        cls.burst_penalty = burst_penalty

    def __init__(self, token: str, role: str, queued_at: datetime, timeout: timedelta) -> None:
        """Initialize the job priority.

        Args:
            token (str): Token of the job submitter.
            role (str): The role of the job submitter.
            queued_at (datetime): The time when the job was queued.
            timeout (timedelta): Timeout of the job.
        """
        self._token = token
        self._queued_at = queued_at
        self._base_priority = self._calc_base_priority(
            role=role,
            timeout=timeout,
        )

    def _calc_base_priority(self, role: str, timeout: timedelta) -> float:
        """Calculate the base priority determined when the job is enqueued.

        Args:
            role (str): Role of job submitter.
            timeout (timedelta): Timeout of the job.

        Returns:
            float: Base priority of the job.
        """
        role_max_timeout = get_role_max_timeout(role=role)
        w_role_factor = self.factor_weights.role_factor
        w_timeout_factor = self.factor_weights.timeout_factor
        return w_role_factor * calc_role_factor(role=role) + w_timeout_factor * calc_timeout_factor(
            timeout=timeout, role_max_timeout=role_max_timeout
        )

    def calc_priority(self, current_time: datetime, max_age: timedelta) -> float:
        """Calculate the job priority as the weighted sum of multiple factors.

        Args:
            current_time (datetime): Current time.
            max_age (timedelta): Maximum waiting time used to calculate the age factor.

        Returns:
            float: Priority of the job.
        """
        burst_score = self.burst_score_manager.get_burst_score(token=self._token)
        w_age_factor = self.factor_weights.age_factor
        w_fair_share_factor = self.factor_weights.fair_share_factor
        return (
            self._base_priority
            + w_age_factor * calc_age_factor(current_time=current_time, queued_at=self._queued_at, max_age=max_age)
            + w_fair_share_factor * calc_fair_share_factor(burst_score=burst_score, burst_penalty=self.burst_penalty)
        )

    def get_waiting_time(self, current_time: datetime) -> timedelta:
        """Return the waiting time of the job.

        Args:
            current_time (datetime): Current time.

        Returns:
            timedelta: The waiting time of the job.
        """
        return current_time - self._queued_at

    @cached_property
    def bytes(self) -> int:
        """Return the size of the job priority object in bytes (excludes referenced objects).

        Returns:
           int: The size of the job priority object in bytes.
        """
        return (
            sys.getsizeof(self)
            + sys.getsizeof(self._token)
            + sys.getsizeof(self._queued_at)
            + sys.getsizeof(self._base_priority)
        )


class JobPriorityFactory:
    """Job priority factory class."""

    def __init__(
        self, factor_weights: PriorityFactorWeights, burst_score_half_life: timedelta, burst_penalty: float
    ) -> None:
        """Initialize the job priority factory.

        Args:
            factor_weights (PriorityFactorWeights): Weights of the priority factors.
            burst_score_half_life (timedelta): Half-life time for burst scores.
            burst_penalty (float): Burst penalty used to calculate the fair share factor.
        """
        JobPriority.configure(
            factor_weights=factor_weights,
            burst_score_manager=BurstScoreManager(burst_score_half_life=burst_score_half_life),
            burst_penalty=burst_penalty,
        )

    def create(self, token: str, role: str, queued_at: datetime, timeout: timedelta) -> JobPriority:
        """Create a job priority object.

        Args:
            token (str): Token of the job submitter.
            role (str): The role of the job submitter.
            queued_at (datetime): The time when the job was queued.
            timeout (timedelta): Timeout of the job.

        Returns:
            JobPriority: The job priority object.
        """
        return JobPriority(token=token, role=role, queued_at=queued_at, timeout=timeout)
