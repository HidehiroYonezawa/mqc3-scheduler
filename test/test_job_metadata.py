"""Tests for the job metadata."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from allpairspy import AllPairs

sys.path.append(Path(__file__).parents[1].as_posix())


from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from job_manager.job_metadata import JobMetadata, JobStatus, StateSavePolicy
from pb.mqc3_cloud.scheduler.v1 import job_pb2
from utility import convert_timestamp_to_datetime, get_current_datetime


def test_job_metadata_constructor() -> None:
    job_id = "job1"
    role = "guest"
    settings = job_pb2.JobExecutionSettings(
        backend="BACKEND_ACTUAL",
        n_shots=1024,
        timeout=Duration(seconds=10),
        role=role,
    )
    management_options = job_pb2.JobManagementOptions(
        save_job=True,
    )
    sdk_version = "0.0.1"
    token = "token1"  # noqa: S105
    state_save_policy = StateSavePolicy.ALL
    resource_squeezing_level = 10.0

    construction_start_time = get_current_datetime()
    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=settings.timeout.seconds,
        sdk_version=sdk_version,
        token=token,
        role=role,
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=management_options.save_job,
        state_save_policy=state_save_policy,
        resource_squeezing_level=resource_squeezing_level,
    )
    construction_end_time = get_current_datetime()

    assert job_metadata.job_id == job_id
    assert job_metadata.max_elapsed_s == settings.timeout.seconds
    assert job_metadata.sdk_version == sdk_version

    assert job_metadata.token == token
    assert job_metadata.role == role
    assert job_metadata.requested_backend == settings.backend
    assert job_metadata.n_shots == settings.n_shots
    assert job_metadata.save_job == management_options.save_job

    assert job_metadata.state_save_policy == state_save_policy
    assert job_metadata.resource_squeezing_level == resource_squeezing_level

    assert job_metadata.status == JobStatus.UNSPECIFIED
    assert not job_metadata.status_code
    assert not job_metadata.status_message

    assert job_metadata.actual_backend_name is None
    assert job_metadata.raw_size_bytes is None
    assert job_metadata.encoded_size_bytes is None

    assert job_metadata.physical_lab_version is None
    assert job_metadata.scheduler_version is None

    assert job_metadata.submitted_at is not None
    assert construction_start_time < convert_timestamp_to_datetime(job_metadata.submitted_at) < construction_end_time
    assert job_metadata.compile_started_at is None
    assert job_metadata.compile_finished_at is None
    assert job_metadata.queued_at is None
    assert job_metadata.dequeued_at is None
    assert job_metadata.execution_started_at is None
    assert job_metadata.execution_finished_at is None
    assert job_metadata.finished_at is None
    assert job_metadata.job_expiry is not None


@pytest.mark.parametrize(
    argnames=(
        "job_id",
        "token",
        "role",
        "backend",
        "n_shots",
        "save_job",
        "state_save_policy",
        "resource_squeezing_level",
        "status",
    ),
    argvalues=AllPairs([
        ["", "job", "0"],
        ["", "token", "1"],
        ["", "role", "2"],
        [
            "BACKEND_UNSPECIFIED",
            "BACKEND_SIMULATOR",
            "BACKEND_ACTUAL",
        ],
        [0, 1000],
        [False, True],
        [StateSavePolicy.ALL, StateSavePolicy.FIRST_ONLY, StateSavePolicy.NONE],
        [0.5, 10.0],
        [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED],
    ]),
)
def test_job_metadata_to_dynamodb_item(
    *,
    job_id: str,
    token: str,
    role: str,
    backend: str,
    n_shots: int,
    save_job: bool,
    state_save_policy: StateSavePolicy,
    resource_squeezing_level: float,
    status: JobStatus,
) -> None:
    settings = job_pb2.JobExecutionSettings(backend=backend, n_shots=n_shots, timeout=Duration(seconds=1), role=role)
    management_options = job_pb2.JobManagementOptions(
        save_job=save_job,
    )
    sdk_version = "0.0.2"

    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=settings.timeout.seconds,
        sdk_version=sdk_version,
        token=token,
        role=role,
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=management_options.save_job,
        state_save_policy=state_save_policy,
        resource_squeezing_level=resource_squeezing_level,
        status=status,
    )

    assert job_metadata.submitted_at is not None
    submitted_at = convert_timestamp_to_datetime(job_metadata.submitted_at)
    assert job_metadata.job_expiry is not None
    job_expiry = convert_timestamp_to_datetime(job_metadata.job_expiry)

    d = job_metadata.to_dynamodb_item()

    assert d["job_id"] == {"S": job_id}
    assert d["max_elapsed_s"] == {"N": str(settings.timeout.seconds)}
    assert d["sdk_version"] == {"S": sdk_version}

    assert d["token"] == {"S": token}
    assert d["role"] == {"S": role}
    assert d["requested_backend"] == {"S": str(settings.backend)}
    assert d["n_shots"] == {"N": str(settings.n_shots)}
    assert d["save_job"] == {"BOOL": management_options.save_job}

    assert d["state_save_policy"] == {"S": state_save_policy.name}
    assert d["resource_squeezing_level"] == {"N": str(Decimal(resource_squeezing_level))}

    assert d["status"] == {"S": status.name}
    assert d["status_code"] == {"S": ""}
    assert d["status_message"] == {"S": ""}

    assert d["submitted_at"] == {"S": submitted_at.isoformat()}
    assert d["job_expiry"] == {"S": job_expiry.isoformat()}

    for key in [
        "actual_backend_name",
        "raw_size_bytes",
        "encoded_size_bytes",
        "physical_lab_version",
        "scheduler_version",
        "compile_started_at",
        "compile_finished_at",
        "queued_at",
        "dequeued_at",
        "execution_started_at",
        "execution_finished_at",
        "finished_at",
    ]:
        assert d[key] == {"NULL": True}


@pytest.mark.parametrize(
    argnames=(
        "job_id",
        "token",
        "role",
        "backend",
        "n_shots",
        "save_job",
        "state_save_policy",
        "resource_squeezing_level",
        "status",
    ),
    argvalues=AllPairs([
        ["", "job", "0"],
        ["", "token", "1"],
        ["", "role", "2"],
        [
            "BACKEND_UNSPECIFIED",
            "BACKEND_SIMULATOR",
            "BACKEND_ACTUAL",
        ],
        [0, 1000],
        [False, True],
        [StateSavePolicy.ALL, StateSavePolicy.FIRST_ONLY, StateSavePolicy.NONE],
        [0.5, 10.0],
        [JobStatus.UNSPECIFIED, JobStatus.FAILED, JobStatus.CANCELLED],
    ]),
)
def test_job_metadata_from_dynamodb_item(
    *,
    job_id: str,
    token: str,
    role: str,
    backend: str,
    n_shots: int,
    save_job: bool,
    state_save_policy: StateSavePolicy,
    resource_squeezing_level: float,
    status: JobStatus,
) -> None:
    settings = job_pb2.JobExecutionSettings(backend=backend, n_shots=n_shots, timeout=Duration(seconds=1), role=role)
    management_options = job_pb2.JobManagementOptions(
        save_job=save_job,
    )
    sdk_version = "0.0.2"

    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=settings.timeout.seconds,
        sdk_version=sdk_version,
        token=token,
        role=role,
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=management_options.save_job,
        state_save_policy=state_save_policy,
        resource_squeezing_level=resource_squeezing_level,
        status=status,
    )

    d = job_metadata.to_dynamodb_item()
    job_metadata_from_dynamodb = JobMetadata.from_dynamodb_item(d)

    assert job_metadata_from_dynamodb == job_metadata


def test_get_proto_execution_version() -> None:
    metadata = JobMetadata(
        job_id="job_id",
        max_elapsed_s=1,
        sdk_version="0.0.2",
        token="token",  # noqa: S106
        role="role",
        requested_backend="backend",
        n_shots=1,
        save_job=True,
    )
    metadata.physical_lab_version = "0.0.2"
    metadata.scheduler_version = "0.0.2"
    expected = job_pb2.JobExecutionVersion(
        physical_lab_version="0.0.2",
        scheduler_version="0.0.2",
    )
    assert metadata.get_proto_execution_version() == expected


def test_get_proto_job_timestamps() -> None:
    metadata = JobMetadata(
        job_id="job_id",
        max_elapsed_s=1,
        sdk_version="0.0.2",
        token="token",  # noqa: S106
        role="role",
        requested_backend="backend",
        n_shots=1,
        save_job=True,
    )
    metadata.submitted_at = Timestamp(seconds=1)
    metadata.queued_at = Timestamp(seconds=2)
    metadata.dequeued_at = Timestamp(seconds=3)
    metadata.compile_started_at = Timestamp(seconds=4)
    metadata.compile_finished_at = Timestamp(seconds=5)
    metadata.execution_started_at = Timestamp(seconds=6)
    metadata.execution_finished_at = Timestamp(seconds=7)
    metadata.finished_at = Timestamp(seconds=8)

    expected = job_pb2.JobTimestamps(
        submitted_at=metadata.submitted_at,
        queued_at=metadata.queued_at,
        dequeued_at=metadata.dequeued_at,
        compile_started_at=metadata.compile_started_at,
        compile_finished_at=metadata.compile_finished_at,
        execution_started_at=metadata.execution_started_at,
        execution_finished_at=metadata.execution_finished_at,
        finished_at=metadata.finished_at,
    )
    assert metadata.get_proto_job_timestamps() == expected
