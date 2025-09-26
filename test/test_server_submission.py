"""Tests for the submission server in scheduler."""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

sys.path.append(Path(__file__).parents[1].as_posix())

from backend_manager.backend_manager import BackendManager
from common import SAMPLE_AWS_CREDENTIALS, construct_sample_program, construct_sample_settings, create_dynamodb_table
from get_token_info import TokenInfo
from job_manager.job_manager import JobManager
from job_manager.job_metadata import JobMetadata, JobStatus
from job_manager.job_repository import JobRepository
from message_manager.message_manager import StatusMessage, get_status_message
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.scheduler.v1 import job_pb2, submission_pb2
from server_submission import SubmissionServer
from utility import AWSCredentials, get_current_timestamp

ADDRESS_TOKEN_DB = "token_database:8084"  # noqa: S105
ENDPOINT_URL = None
ACCESS_KEY_ID = None
SECRET_ACCESS_KEY = None
REGION_NAME = "us-east-1"
STATUS_PARAMETER_NAME = "/test/status.toml"
MAX_JOB_BYTES = {
    "admin": 10 * 1024 * 1024,
    "developer": 10 * 1024 * 1024,
    "guest": 1024 * 1024,
}


def create_bucket(bucket: str) -> None:
    client = boto3.client("s3", region_name=REGION_NAME)
    client.create_bucket(Bucket=bucket)


@pytest.fixture
def verify_token_success(mocker):  # noqa: ANN001
    """Mock __verify_token to be successful."""
    mock_token_info = TokenInfo(
        "guest",
        "test user",
        None,
    )

    return mocker.patch.object(
        SubmissionServer,
        "_SubmissionServer__verify_token",
        return_value=(mock_token_info, ""),
    )


def set_ssm_parameter() -> None:
    ssm_client = boto3.client("ssm", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    initial_status_toml = """
[backends.qpu.guest]
status = "available"
description = "ready"

[backends.emulator.guest]
status = "available"
description = "ready"
"""

    ssm_client.put_parameter(
        Name=STATUS_PARAMETER_NAME,
        Value=initial_status_toml,
        Type="String",
        Overwrite=True,
    )


def create_backend_manager() -> BackendManager:
    return BackendManager(
        status_parameter_name=STATUS_PARAMETER_NAME,
        aws_credentials=AWSCredentials(
            endpoint_url=ENDPOINT_URL,
            access_key_id=ACCESS_KEY_ID,
            secret_access_key=SECRET_ACCESS_KEY,
            region_name=REGION_NAME,
        ),
    )


@mock_aws
def test_submit_job_success(mocker, verify_token_success) -> None:  # noqa: ANN001, ARG001
    """Test that a job is submitted successfully."""
    token = "user_token"  # noqa: S105
    context = MagicMock()
    program = construct_sample_program()
    settings = construct_sample_settings()
    job = job_pb2.Job(program=program, settings=settings)
    options = job_pb2.JobManagementOptions(save_job=False)

    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token=token,
        role="guest",
        requested_backend="emulator",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.QUEUED,
    )
    mocker.patch.object(JobManager, "add_job_request", return_value=mock_metadata)

    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name=bucket,
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )
    response = server.SubmitJob(
        submission_pb2.SubmitJobRequest(job=job, token=token, options=options, sdk_version=mock_metadata.sdk_version),
        context,
    )
    assert response.error == error_detail_pb2.ErrorDetail()
    assert response.job_id == mock_metadata.job_id


@mock_aws
def test_get_job_status_success(mocker, verify_token_success) -> None:  # noqa: ANN001, ARG001
    """Test that a job status is retrieved successfully."""
    token = "user_token"  # noqa: S105
    context = MagicMock()
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token=token,
        role="guest",
        requested_backend="emulator",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.QUEUED,
        status_message="test_status_message",
    )
    mocker.patch.object(JobManager, "get_job_metadata", return_value=mock_metadata)

    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name=bucket,
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )
    response = server.GetJobStatus(
        submission_pb2.GetJobStatusRequest(token=token, job_id=mock_metadata.job_id),
        context,
    )

    assert response.error == error_detail_pb2.ErrorDetail()
    assert response.status == mock_metadata.status.value
    assert response.status_detail == mock_metadata.status_message
    assert response.execution_details == job_pb2.JobExecutionDetails(
        version=mock_metadata.get_proto_execution_version(),
        timestamps=mock_metadata.get_proto_job_timestamps(),
    )


@mock_aws
def test_get_job_result_success(mocker, verify_token_success) -> None:  # noqa: ANN001, ARG001
    """Test that a job result is retrieved successfully."""
    token = "user_token"  # noqa: S105
    context = MagicMock()
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token=token,
        role="guest",
        requested_backend="emulator",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.COMPLETED,
    )
    mock_result_url = "test_result_url"
    expires_at = get_current_timestamp()
    mocker.patch.object(JobManager, "get_job_result_download_url", return_value=(mock_result_url, expires_at))
    mocker.patch.object(JobManager, "get_job_metadata", return_value=mock_metadata)

    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name=bucket,
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )
    response = server.GetJobResult(
        submission_pb2.GetJobResultRequest(
            token=token,
            job_id=mock_metadata.job_id,
        ),
        context,
    )

    assert response.error == error_detail_pb2.ErrorDetail()
    assert response.result == job_pb2.JobResult(result_url=mock_result_url)


@mock_aws
def test_get_service_status_success(mocker, verify_token_success) -> None:  # noqa: ANN001, ARG001
    """Test that the service status is retrieved successfully."""
    token = "user_token"  # noqa: S105
    context = MagicMock()
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token=token,
        role="guest",
        requested_backend="emulator",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.COMPLETED,
    )
    mocker.patch.object(JobManager, "get_job_metadata", return_value=mock_metadata)

    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name=bucket,
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )

    response = server.GetServiceStatus(
        submission_pb2.GetServiceStatusRequest(
            token=token,
            backend="qpu",
        ),
        context,
    )
    assert response.error == error_detail_pb2.ErrorDetail()
    assert response.status == submission_pb2.ServiceStatus.SERVICE_STATUS_AVAILABLE
    assert response.description


@mock_aws
def test_cancel_job(mocker, verify_token_success) -> None:  # noqa: ANN001, ARG001
    """Test that a job is cancelled successfully."""
    token = "user_token"  # noqa: S105
    context = MagicMock()

    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )

    mocker.patch.object(JobManager, "cancel_job", return_value=(True, StatusMessage()))
    response = server.CancelJob(submission_pb2.CancelJobRequest(job_id="test_job_id", token=token), context)
    assert response.error == error_detail_pb2.ErrorDetail()

    error_message = get_status_message(key="INVALID_JOB_STATE")
    mocker.patch.object(JobManager, "cancel_job", return_value=(False, error_message))
    response = server.CancelJob(submission_pb2.CancelJobRequest(job_id="test_job_id", token=token), context)
    assert response.error == error_detail_pb2.ErrorDetail(code=error_message.code, description=error_message.message)


@mock_aws
def test_resolve_service_status_failed():
    """Test that resolving service status fails."""
    bucket = "test-bucket"
    create_bucket(bucket)
    set_ssm_parameter()
    backend_manager = create_backend_manager()

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=ENDPOINT_URL,
                access_key_id=ACCESS_KEY_ID,
                secret_access_key=SECRET_ACCESS_KEY,
                region_name=REGION_NAME,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
    )
    server = SubmissionServer(
        address_to_token_database=ADDRESS_TOKEN_DB,
        backend_manager=backend_manager,
        backend_manager_lock=threading.RLock(),
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
        max_job_bytes=MAX_JOB_BYTES,
    )

    invalid_backend_status_result = server._resolve_service_status(backend="invalid_backend", role="guest")  # noqa: SLF001
    assert invalid_backend_status_result.error is not None
    assert invalid_backend_status_result.error.code == "INVALID_ARGUMENT"
    assert (
        invalid_backend_status_result.error.description
        == "Invalid request parameters: Unknown backend: 'invalid_backend'."
    )

    invalid_role_status_result = server._resolve_service_status(backend="qpu", role="invalid_role")  # noqa: SLF001
    assert invalid_role_status_result.error is not None
    assert invalid_role_status_result.error.code == "INVALID_ARGUMENT"
    assert (
        invalid_role_status_result.error.description
        == "Invalid request parameters: Unknown role: 'invalid_role' in backend 'qpu'."
    )
