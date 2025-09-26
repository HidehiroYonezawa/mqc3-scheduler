"""Tests for the job manager."""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.append(Path(__file__).parents[1].as_posix())

import boto3
from __version__ import __version__
from botocore.exceptions import ClientError
from common import SAMPLE_AWS_CREDENTIALS, construct_sample_program, construct_sample_settings, create_dynamodb_table
from get_token_info import TokenInfo
from google.protobuf import timestamp_pb2
from job_manager import dynamodb_helper
from job_manager.job_manager import JobManager
from job_manager.job_metadata import JOB_EXPIRY_DAYS, JobStatus
from job_manager.job_queue import JobQueue
from job_manager.job_repository import JobRepository
from message_manager.message_manager import StatusMessage
from moto import mock_aws
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.program.v1 import quantum_program_pb2
from pb.mqc3_cloud.scheduler.v1 import execution_pb2, job_pb2, submission_pb2
from pytest_mock import MockerFixture
from utility import AWSCredentials, convert_timestamp_to_datetime, get_current_datetime, get_current_timestamp


@mock_aws
def test_job_manager_constructor(request: pytest.FixtureRequest) -> None:
    job_repository = JobRepository(
        bucket_name=request.node.name,
        aws_credentials=AWSCredentials(
            endpoint_url=None,
            access_key_id=None,
            secret_access_key=None,
            region_name=None,
        ),
    )
    max_bytes = 1000
    backends = {"qpu", "emulator", "simulator"}
    dynamodb_max_attempts = 123

    dynamodb_table_name = request.node.name
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=max_bytes,
        max_concurrent_jobs_per_token=None,
        job_repository=job_repository,
        supported_backends=backends,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        dynamodb_max_attempts=dynamodb_max_attempts,
    )

    assert job_manager.job_repository == job_repository
    assert job_manager.table_name == dynamodb_table_name
    assert job_manager.dynamodb_client.meta.config.retries["total_max_attempts"] == dynamodb_max_attempts
    assert job_manager.dynamodb_client.meta.config.retries["mode"] == "standard"

    for backend in backends:
        assert job_manager.job_queue[backend].capacity_bytes == max_bytes
        assert job_manager.job_queue[backend].max_concurrent_jobs_per_token == {}
        assert job_manager.job_queue[backend].jobs == {}
        assert job_manager.job_queue[backend].current_bytes == 0


def construct_sample_job_manager(
    *,
    request: pytest.FixtureRequest,
    backends: set,
    queue_capacity_bytes: int = 1000,
    max_concurrent_jobs_per_token: dict[str, int] | None = None,
    region_name: str | None = None,
    create_table: bool = True,
) -> JobManager:
    job_repository = JobRepository(
        bucket_name=request.node.name,
        aws_credentials=AWSCredentials(
            endpoint_url=None,
            access_key_id=None,
            secret_access_key=None,
            region_name=region_name,
        ),
    )
    dynamodb_table_name = request.node.name
    if create_table:
        create_dynamodb_table(dynamodb_table_name)
    return JobManager(
        queue_capacity_bytes=queue_capacity_bytes,
        max_concurrent_jobs_per_token=max_concurrent_jobs_per_token,
        job_repository=job_repository,
        supported_backends=backends,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
    )


def construct_sample_job_request(
    *,
    token: str = "token1",  # noqa: S107
    save_job: bool = False,
    sdk_version: str = "0.0.2",
) -> submission_pb2.SubmitJobRequest:
    settings = construct_sample_settings()
    management_options = job_pb2.JobManagementOptions(save_job=save_job)
    program = construct_sample_program()
    job = job_pb2.Job(program=program, settings=settings)
    return submission_pb2.SubmitJobRequest(
        token=token,
        job=job,
        options=management_options,
        sdk_version=sdk_version,
    )


@mock_aws
def test_job_manager_restore_job_queue(request: pytest.FixtureRequest) -> None:
    # Create a bucket to save job inputs
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    s3_client.create_bucket(Bucket=request.node.name)

    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})

    # Add a job request to "qpu"
    qpu_job_request = construct_sample_job_request()
    qpu_job_request.job.settings.backend = "qpu"
    qpu_job_metadata = job_manager.add_job_request(
        job_request=qpu_job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    assert qpu_job_metadata.status == JobStatus.QUEUED

    # Add a job request to "emulator"
    emulator_job_request = construct_sample_job_request()
    emulator_job_metadata = job_manager.add_job_request(
        job_request=emulator_job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    assert emulator_job_metadata.status == JobStatus.QUEUED

    # Reconstruct a job manager
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"}, create_table=False)
    assert job_manager.get_job_metadata(job_id=qpu_job_metadata.job_id) == qpu_job_metadata
    assert job_manager.get_job_metadata(job_id=emulator_job_metadata.job_id) == emulator_job_metadata
    assert job_manager.job_queue["qpu"].try_pop() == (qpu_job_metadata.job_id, construct_sample_program())
    assert job_manager.job_queue["qpu"].try_pop() is None
    assert job_manager.job_queue["emulator"].try_pop() == (emulator_job_metadata.job_id, construct_sample_program())
    assert job_manager.job_queue["emulator"].try_pop() is None


@mock_aws
def test_job_manager_fail_running_job(request: pytest.FixtureRequest) -> None:
    # Create a bucket to save job inputs
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    s3_client.create_bucket(Bucket=request.node.name)

    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})

    # Add a job request to "emulator"
    emulator_job_request = construct_sample_job_request()
    emulator_job_metadata = job_manager.add_job_request(
        job_request=emulator_job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    # Update the status to `RUNNING`
    dynamodb_helper.update_item(
        dynamodb_client=job_manager.dynamodb_client,
        table_name=job_manager.table_name,
        job_id=emulator_job_metadata.job_id,
        update_values={"status": JobStatus.RUNNING},
    )

    # Reconstruct a job manager
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"}, create_table=False)
    assert job_manager.get_job_metadata(job_id=emulator_job_metadata.job_id).status == JobStatus.FAILED
    assert job_manager.job_queue["emulator"].try_pop() is None


@mock_aws
def test_job_manager_add_job_request(request: pytest.FixtureRequest) -> None:
    backends = {"qpu", "emulator"}
    job_manager = construct_sample_job_manager(request=request, backends=backends)
    program = construct_sample_program()
    settings = construct_sample_settings()
    management_options = job_pb2.JobManagementOptions(save_job=False)
    token = "token1"  # noqa: S105
    token_info = TokenInfo(name="user1", role="guest", expires_at=None)

    job_request = construct_sample_job_request(token=token, save_job=False)

    start_time = get_current_datetime()
    job1_metadata = job_manager.add_job_request(job_request=job_request, token_info=token_info)
    end_time = get_current_datetime()
    job1_id = job1_metadata.job_id

    job_metadata = job_manager.get_job_metadata(job_id=job1_id)
    assert job_metadata.job_id == job1_id
    assert job_metadata.max_elapsed_s == settings.timeout.seconds
    assert job_metadata.sdk_version == job_request.sdk_version
    assert job_metadata.token == token
    assert job_metadata.role == token_info.role
    assert job_metadata.requested_backend == settings.backend
    assert job_metadata.n_shots == settings.n_shots
    assert job_metadata.save_job == management_options.save_job
    assert job_metadata.status == JobStatus.QUEUED
    assert job_metadata.queued_at is not None
    assert start_time < convert_timestamp_to_datetime(job_metadata.queued_at) < end_time
    assert job_metadata.scheduler_version == __version__

    assert job_manager.job_queue["qpu"].try_pop() is None
    assert job_manager.job_queue["emulator"].try_pop() == (job1_id, program)

    job2_id = job_manager.add_job_request(job_request=job_request, token_info=token_info)
    assert job1_id != job2_id


@mock_aws
def test_job_manager_add_job_request_fails_on_full_queue(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"}, queue_capacity_bytes=0)
    job_request = construct_sample_job_request()
    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    assert initial_metadata.status == JobStatus.FAILED
    assert initial_metadata.status_code == "RESOURCE_EXHAUSTED"
    assert (
        initial_metadata.status_message
        == "The job was not accepted due to current resource limits. Please try again later."
    )


@mock_aws
def test_job_manager_add_job_request_fails_on_invalid_backend(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    invalid_backend = "invalid backend"
    error_code = "INVALID_ARGUMENT"
    error_message = f"Invalid request parameters: {invalid_backend} is not a supported backend."
    job_request.job.settings.backend = invalid_backend
    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    assert initial_metadata.status == JobStatus.FAILED
    assert initial_metadata.status_code == error_code
    assert initial_metadata.status_message == error_message

    db_metadata = job_manager.get_job_metadata(initial_metadata.job_id)
    assert db_metadata.status == JobStatus.FAILED
    assert db_metadata.status_code == error_code
    assert db_metadata.status_message == error_message


@mock_aws
def test_job_manager_add_job_request_fails_on_upload_input(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request(save_job=True)

    mocker.patch.object(
        JobRepository,
        "upload_job_input",
        side_effect=ClientError(error_response={"Error": {"Code": "404"}}, operation_name="upload_job_input"),
    )
    # Failed to upload the job input to S3
    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )

    error_message = "An internal error occurred. Please try again later."
    error_code = "INTERNAL"
    assert initial_metadata.status == JobStatus.FAILED
    assert initial_metadata.status_code == error_code
    assert initial_metadata.status_message == error_message

    db_metadata = job_manager.get_job_metadata(initial_metadata.job_id)
    assert db_metadata.status == JobStatus.FAILED
    assert db_metadata.status_code == error_code
    assert db_metadata.status_message == error_message


@mock_aws
def test_job_manager_add_job_request_fails_on_push_queue(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request(save_job=True)
    token_info = TokenInfo(name="user1", role="guest", expires_at=None)

    metadata1 = job_manager.add_job_request(job_request=job_request, token_info=token_info)

    error_message = "An unexpected error occurred."
    mocker.patch.object(
        JobQueue,
        "try_push",
        side_effect=ValueError(error_message),
    )

    # Failed to push a job with the same job ID
    metadata2 = job_manager.add_job_request(job_request=job_request, token_info=token_info)
    assert metadata2.status == JobStatus.FAILED
    assert metadata2.status_code == "INTERNAL"
    assert metadata2.status_message == error_message

    # Do not update the job status in DB
    db_metadata = job_manager.get_job_metadata(metadata1.job_id)
    assert db_metadata.status == JobStatus.QUEUED


@mock_aws
def test_job_manager_add_job_request_fails_on_update_db(request: pytest.FixtureRequest, mocker: MockerFixture) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request(save_job=True)

    mocker.patch.object(
        dynamodb_helper,
        "put_item",
        side_effect=ClientError(error_response={"Error": {"Code": "404"}}, operation_name="put_item"),
    )
    # Failed to upload the initial metadata to DB
    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    assert initial_metadata.status == JobStatus.FAILED
    assert initial_metadata.status_code == "INTERNAL"
    assert initial_metadata.status_message == "An internal error occurred. Please try again later."
    assert job_manager.job_queue["emulator"].try_pop() is None

    with pytest.raises(
        ValueError, match=f"The item with job ID {initial_metadata.job_id} does not exist in the database."
    ):
        job_manager.get_job_metadata(initial_metadata.job_id)


@mock_aws
def test_job_manager_cancel_job(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    job_id = initial_metadata.job_id
    assert job_manager.cancel_job(job_id=job_id) == (True, StatusMessage())
    db_metadata = job_manager.get_job_metadata(job_id)
    assert db_metadata.status == JobStatus.CANCELLED
    assert not db_metadata.status_code
    assert not db_metadata.status_message

    assert job_manager.cancel_job(job_id=job_id) == (
        False,
        StatusMessage(code="FAILED_PRECONDITION", message="The job can no longer be cancelled."),
    )

    invalid_job_id = "invalid_job_id"
    assert job_manager.cancel_job(job_id=invalid_job_id) == (
        False,
        StatusMessage(code="NOT_FOUND", message=f"Job not found (ID: {invalid_job_id})."),
    )


@mock_aws
def test_job_manager_cancel_job_fails_on_running_job(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    # Pop the job from the queue and start running it
    job_manager.fetch_next_job_to_execute(request=execution_pb2.AssignNextJobRequest(backend="emulator"))

    job_id = initial_metadata.job_id
    assert job_manager.cancel_job(job_id=job_id) == (
        False,
        StatusMessage(code="FAILED_PRECONDITION", message="The job can no longer be cancelled."),
    )

    db_metadata = job_manager.get_job_metadata(job_id=job_id)
    assert db_metadata.status == JobStatus.RUNNING
    assert not db_metadata.status_code
    assert not db_metadata.status_message


@mock_aws
def test_job_manager_cancel_job_fails_on_update_status(request: pytest.FixtureRequest, mocker: MockerFixture) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="update_item")
    error_message = StatusMessage(code="INTERNAL", message="An internal error occurred. Please try again later.")
    mocker.patch.object(
        dynamodb_helper,
        "update_item",
        side_effect=error,
    )
    assert job_manager.cancel_job(job_id=initial_metadata.job_id) == (
        False,
        error_message,
    )

    db_metadata = job_manager.get_job_metadata(initial_metadata.job_id)
    assert db_metadata.status == JobStatus.QUEUED


@mock_aws
def test_job_manager_get_job_metadata(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()
    settings = construct_sample_settings()
    management_options = job_pb2.JobManagementOptions(save_job=False)
    token_info = TokenInfo(name="user1", role="guest", expires_at=None)

    initial_metadata = job_manager.add_job_request(job_request=job_request, token_info=token_info)
    job_id = initial_metadata.job_id

    job_metadata = job_manager.get_job_metadata(job_id=job_id)
    assert job_metadata.job_id == job_id
    assert job_metadata.max_elapsed_s == settings.timeout.seconds
    assert job_metadata.sdk_version == job_request.sdk_version
    assert job_metadata.token == job_request.token
    assert job_metadata.role == token_info.role
    assert job_metadata.requested_backend == settings.backend
    assert job_metadata.n_shots == settings.n_shots
    assert job_metadata.save_job == management_options.save_job
    assert job_metadata.status == JobStatus.QUEUED

    invalid_job_id = "invalid_job_id"
    with pytest.raises(ValueError, match=f"The item with job ID {invalid_job_id} does not exist in the database."):
        job_manager.get_job_metadata(job_id=invalid_job_id)


@mock_aws
def test_job_manager_fetch_next_job(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()
    program = construct_sample_program()
    settings = construct_sample_settings()

    # Test that no job is returned when the queue is empty.
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    assert not next_job.job_id

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role=settings.role, expires_at=None)
    )
    job_id = initial_metadata.job_id

    # Test that the job is returned when the queue is not empty.
    start_time = get_current_datetime()
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    end_time = get_current_datetime()

    assert next_job.job_id == job_id
    assert next_job.job == job_pb2.Job(program=program, settings=settings)
    assert next_job.upload_target.upload_url
    assert next_job.upload_target.expires_at != timestamp_pb2.Timestamp()

    # Test that the job metadata is updated.
    job_metadata = job_manager.get_job_metadata(job_id=job_id)
    assert job_metadata.status == JobStatus.RUNNING
    assert job_metadata.dequeued_at is not None
    assert start_time < convert_timestamp_to_datetime(job_metadata.dequeued_at) < end_time


@mock_aws
def test_job_manager_fetch_next_job_fails_on_unsupported_backend(request: pytest.FixtureRequest) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )

    unsupported_backend = "unsupported"
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend=unsupported_backend))
    assert not next_job.job_id
    assert next_job.error.code == "INVALID_ARGUMENT"
    assert (
        next_job.error.description == f"Invalid request parameters: {unsupported_backend} is not a supported backend."
    )


@mock_aws
def test_job_manager_fetch_next_job_fails_on_get_metadata(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )

    # Save the original `get_job_metadata` method to restore it later
    original_get_job_metadata = job_manager.get_job_metadata

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="get_job_metadata")
    mocker.patch.object(
        JobManager,
        "get_job_metadata",
        side_effect=error,
    )
    # Failed to get the job metadata from DB
    error_code = "INTERNAL"
    error_message = "An internal error occurred. Please try again later."
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    assert next_job.error.code == error_code
    assert next_job.error.description == error_message

    # Restore the original `get_job_metadata` method to retrieve the job metadata
    job_manager.get_job_metadata = original_get_job_metadata
    db_metadata = job_manager.get_job_metadata(initial_metadata.job_id)
    assert db_metadata.status == JobStatus.FAILED
    assert db_metadata.status_code == error_code
    assert db_metadata.status_message == error_message


@mock_aws
def test_job_manager_fetch_next_job_fails_on_generate_upload_url(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()
    token_info = TokenInfo(name="user1", role="guest", expires_at=None)

    metadata1 = job_manager.add_job_request(job_request=job_request, token_info=token_info)

    upload_error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="generate_upload_url")
    mocker.patch.object(
        JobRepository,
        "generate_upload_url",
        side_effect=upload_error,
    )
    # Failed to generate upload URL
    error_code = "INTERNAL"
    error_message = "An internal error occurred. Please try again later."
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    assert next_job.error.code == error_code
    assert next_job.error.description == error_message

    db_metadata1 = job_manager.get_job_metadata(metadata1.job_id)
    assert db_metadata1.status == JobStatus.FAILED
    assert db_metadata1.status_code == error_code
    assert db_metadata1.status_message == error_message

    metadata2 = job_manager.add_job_request(job_request=job_request, token_info=token_info)
    db_error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="update_item")
    mocker.patch.object(
        dynamodb_helper,
        "update_item",
        side_effect=db_error,
    )
    # Failed to generate upload URL and update the job status on DB
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    assert next_job.error.code == error_code
    assert next_job.error.description == error_message

    db_metadata2 = job_manager.get_job_metadata(metadata2.job_id)
    assert db_metadata2.status == JobStatus.QUEUED
    assert not db_metadata2.status_code
    assert not db_metadata2.status_message


@mock_aws
def test_job_manager_fetch_next_job_fails_on_update_status(
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    job_manager = construct_sample_job_manager(request=request, backends={"qpu", "emulator"})
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="update_item")
    error_message = "An internal error occurred. Please try again later."
    mocker.patch.object(
        dynamodb_helper,
        "update_item",
        side_effect=error,
    )
    # Failed to update the job status on DB
    next_job = job_manager.fetch_next_job_to_execute(execution_pb2.AssignNextJobRequest(backend="emulator"))
    assert next_job.error.code == "INTERNAL"
    assert next_job.error.description == error_message

    db_metadata = job_manager.get_job_metadata(initial_metadata.job_id)
    assert db_metadata.status == JobStatus.QUEUED
    assert not db_metadata.status_code
    assert not db_metadata.status_message


@mock_aws
@pytest.mark.parametrize(
    ("execution_status", "execution_status_message", "expected_job_status", "upload_result"),
    [
        (execution_pb2.EXECUTION_STATUS_SUCCESS, "", JobStatus.COMPLETED, True),
        (execution_pb2.EXECUTION_STATUS_FAILURE, "Failed", JobStatus.FAILED, False),
        (execution_pb2.EXECUTION_STATUS_TIMEOUT, "Timeout", JobStatus.TIMEOUT, False),
        (execution_pb2.EXECUTION_STATUS_UNSPECIFIED, "Unspecified", JobStatus.UNSPECIFIED, False),
    ],
)
def test_job_manager_finalize_job(  # noqa: PLR0914
    *,
    execution_status: execution_pb2.ExecutionStatus,
    execution_status_message: str,
    expected_job_status: JobStatus,
    upload_result: bool,
) -> None:
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    bucket_name = "test-bucket"
    s3_client.create_bucket(Bucket=bucket_name)

    job_repository = JobRepository(
        bucket_name=bucket_name,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )
    dynamodb_table_name = "test-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=job_repository,
        supported_backends={"qpu", "emulator"},
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
    )
    job_request = construct_sample_job_request()
    sample_result = quantum_program_pb2.QuantumProgramResult()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    job_id = initial_metadata.job_id

    physical_lab_version = "0.0.1"
    quantum_computer_version = "0.0.2"

    compile_started_at = get_current_timestamp()
    compile_finished_at = get_current_timestamp()
    execution_started_at = get_current_timestamp()
    execution_finished_at = get_current_timestamp()

    uploaded_result = job_pb2.JobUploadedResult(
        raw_size_bytes=2,
        encoded_size_bytes=1,
    )

    execution_result = execution_pb2.ReportExecutionResultRequest(
        job_id=job_id,
        status=execution_status,
        error=error_detail_pb2.ErrorDetail(code="", description=execution_status_message),
        timestamps=job_pb2.JobTimestamps(
            compile_started_at=compile_started_at,
            compile_finished_at=compile_finished_at,
            execution_started_at=execution_started_at,
            execution_finished_at=execution_finished_at,
        ),
        uploaded_result=uploaded_result,
        actual_backend="emulator",
        version=execution_pb2.ExecutionVersion(
            physical_lab=physical_lab_version,
            quantum_computer=quantum_computer_version,
        ),
    )

    # The physical lab layer should upload the execution result.
    if upload_result:
        s3_client.put_object(Bucket=bucket_name, Key=f"{job_id}.out.proto.gz", Body=sample_result.SerializeToString())

    finalize_start_time = get_current_datetime()
    response = job_manager.finalize_job(execution_result=execution_result)
    finalize_end_time = get_current_datetime()

    assert response == execution_pb2.ReportExecutionResultResponse()

    job_metadata = job_manager.get_job_metadata(job_id=job_id)
    assert job_metadata.status == expected_job_status
    assert not job_metadata.status_code
    assert job_metadata.status_message == execution_status_message
    assert job_metadata.actual_backend_name == "emulator"
    assert job_metadata.physical_lab_version == physical_lab_version
    assert job_metadata.quantum_computer_version == quantum_computer_version
    assert job_metadata.compile_started_at == compile_started_at
    assert job_metadata.compile_finished_at == compile_finished_at
    assert job_metadata.execution_started_at == execution_started_at
    assert job_metadata.execution_finished_at == execution_finished_at
    assert job_metadata.finished_at is not None
    assert finalize_start_time < convert_timestamp_to_datetime(job_metadata.finished_at) < finalize_end_time
    assert job_metadata.job_expiry is not None
    assert (
        finalize_start_time + timedelta(days=JOB_EXPIRY_DAYS)
        < convert_timestamp_to_datetime(job_metadata.job_expiry)
        < finalize_end_time + timedelta(days=JOB_EXPIRY_DAYS)
    )

    invalid_job_id = "invalid_job_id"
    execution_result.job_id = invalid_job_id
    response = job_manager.finalize_job(execution_result=execution_result)
    assert response.error.code == "NOT_FOUND"
    assert response.error.description == f"Job not found (ID: {invalid_job_id})."


@mock_aws
def test_job_manager_finalize_job_fails_on_check_item_exists(  # noqa: PLR0914
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    bucket_name = request.node.name
    s3_client.create_bucket(Bucket=bucket_name)

    job_manager = construct_sample_job_manager(
        request=request, backends={"qpu", "emulator"}, region_name=SAMPLE_AWS_CREDENTIALS.region_name
    )
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    job_id = initial_metadata.job_id

    physical_lab_version = "0.0.1"
    quantum_computer_version = "0.0.2"

    compile_started_at = get_current_timestamp()
    compile_finished_at = get_current_timestamp()
    execution_started_at = get_current_timestamp()
    execution_finished_at = get_current_timestamp()

    uploaded_result = job_pb2.JobUploadedResult(
        raw_size_bytes=2,
        encoded_size_bytes=1,
    )

    execution_result = execution_pb2.ReportExecutionResultRequest(
        job_id=job_id,
        status=execution_pb2.EXECUTION_STATUS_SUCCESS,
        timestamps=job_pb2.JobTimestamps(
            compile_started_at=compile_started_at,
            compile_finished_at=compile_finished_at,
            execution_started_at=execution_started_at,
            execution_finished_at=execution_finished_at,
        ),
        uploaded_result=uploaded_result,
        actual_backend="emulator",
        version=execution_pb2.ExecutionVersion(
            physical_lab=physical_lab_version,
            quantum_computer=quantum_computer_version,
        ),
    )

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="check_item_exists")
    mocker.patch.object(
        dynamodb_helper,
        "check_item_exists",
        side_effect=error,
    )
    response = job_manager.finalize_job(execution_result=execution_result)
    assert response.error.code == "INTERNAL"
    assert response.error.description == "An internal error occurred. Please try again later."


@mock_aws
def test_job_manager_finalize_job_fails_on_update_db(  # noqa: PLR0914
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    bucket_name = request.node.name
    s3_client.create_bucket(Bucket=bucket_name)

    job_manager = construct_sample_job_manager(
        request=request, backends={"qpu", "emulator"}, region_name=SAMPLE_AWS_CREDENTIALS.region_name
    )
    job_request = construct_sample_job_request()
    sample_result = quantum_program_pb2.QuantumProgramResult()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    job_id = initial_metadata.job_id

    physical_lab_version = "0.0.1"
    quantum_computer_version = "0.0.2"

    compile_started_at = get_current_timestamp()
    compile_finished_at = get_current_timestamp()
    execution_started_at = get_current_timestamp()
    execution_finished_at = get_current_timestamp()

    uploaded_result = job_pb2.JobUploadedResult(
        raw_size_bytes=2,
        encoded_size_bytes=1,
    )

    execution_result = execution_pb2.ReportExecutionResultRequest(
        job_id=job_id,
        status=execution_pb2.EXECUTION_STATUS_SUCCESS,
        timestamps=job_pb2.JobTimestamps(
            compile_started_at=compile_started_at,
            compile_finished_at=compile_finished_at,
            execution_started_at=execution_started_at,
            execution_finished_at=execution_finished_at,
        ),
        uploaded_result=uploaded_result,
        actual_backend="emulator",
        version=execution_pb2.ExecutionVersion(
            physical_lab=physical_lab_version,
            quantum_computer=quantum_computer_version,
        ),
    )

    # The physical lab layer should upload the execution result.
    s3_client.put_object(Bucket=bucket_name, Key=f"{job_id}.out.proto", Body=sample_result.SerializeToString())

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="update_item")
    mocker.patch.object(
        dynamodb_helper,
        "update_item",
        side_effect=error,
    )
    response = job_manager.finalize_job(execution_result=execution_result)
    assert response.error.code == "INTERNAL"
    assert response.error.description == "An internal error occurred. Please try again later."
    assert job_manager.get_job_metadata(execution_result.job_id).status == JobStatus.QUEUED


@mock_aws
def test_job_manager_finalize_job_fails_on_put_tags_to_result(  # noqa: PLR0914
    request: pytest.FixtureRequest, mocker: MockerFixture
) -> None:
    s3_client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    bucket_name = request.node.name
    s3_client.create_bucket(Bucket=bucket_name)

    job_manager = construct_sample_job_manager(
        request=request, backends={"qpu", "emulator"}, region_name=SAMPLE_AWS_CREDENTIALS.region_name
    )
    job_request = construct_sample_job_request()

    initial_metadata = job_manager.add_job_request(
        job_request=job_request, token_info=TokenInfo(name="user1", role="guest", expires_at=None)
    )
    job_id = initial_metadata.job_id

    physical_lab_version = "0.0.1"
    quantum_computer_version = "0.0.2"

    compile_started_at = get_current_timestamp()
    compile_finished_at = get_current_timestamp()
    execution_started_at = get_current_timestamp()
    execution_finished_at = get_current_timestamp()

    uploaded_result = job_pb2.JobUploadedResult(
        raw_size_bytes=2,
        encoded_size_bytes=1,
    )

    execution_result = execution_pb2.ReportExecutionResultRequest(
        job_id=job_id,
        status=execution_pb2.EXECUTION_STATUS_SUCCESS,
        timestamps=job_pb2.JobTimestamps(
            compile_started_at=compile_started_at,
            compile_finished_at=compile_finished_at,
            execution_started_at=execution_started_at,
            execution_finished_at=execution_finished_at,
        ),
        uploaded_result=uploaded_result,
        actual_backend="emulator",
        version=execution_pb2.ExecutionVersion(
            physical_lab=physical_lab_version,
            quantum_computer=quantum_computer_version,
        ),
    )

    error = ClientError(error_response={"Error": {"Code": "404"}}, operation_name="put_tags_to_result")
    mocker.patch.object(
        JobRepository,
        "put_tags_to_result",
        side_effect=error,
    )
    response = job_manager.finalize_job(execution_result=execution_result)
    assert response.error.code == "INTERNAL"
    assert response.error.description == "An internal error occurred. Please try again later."
    assert job_manager.get_job_metadata(execution_result.job_id).status == JobStatus.QUEUED
