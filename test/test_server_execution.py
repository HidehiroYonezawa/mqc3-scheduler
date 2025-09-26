"""Tests for the execution server in scheduler."""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError
from google.protobuf.timestamp_pb2 import Timestamp
from moto import mock_aws

sys.path.append(Path(__file__).parents[1].as_posix())

from common import SAMPLE_AWS_CREDENTIALS, construct_sample_program, construct_sample_settings, create_dynamodb_table
from job_manager.job_manager import JobManager
from job_manager.job_metadata import JobMetadata, JobStatus
from job_manager.job_repository import JobRepository
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.scheduler.v1 import execution_pb2, job_pb2
from server_execution import ExecutionServer
from utility import AWSCredentials, get_current_timestamp


@mock_aws
def test_assign_next_job_success(mocker) -> None:  # noqa: ANN001, PLR0914
    """Test that the next job is assigned to physical laboratory server successfully."""
    token = "user_token"  # noqa: S105
    backend = "qpu"
    context = MagicMock()
    program = construct_sample_program()
    settings = construct_sample_settings()
    job = job_pb2.Job(program=program, settings=settings)
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token=token,
        role="guest",
        requested_backend=backend,
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.QUEUED,
    )
    result_url = "https://test_url.com"
    result_url_expires_at = get_current_timestamp()
    mock_upload_target = job_pb2.JobResultUploadTarget(
        upload_url=result_url,
        expires_at=result_url_expires_at,
    )
    patch_fetch_next_job = mocker.patch.object(
        JobManager,
        "fetch_next_job_to_execute",
        return_value=execution_pb2.AssignNextJobResponse(
            job_id=mock_metadata.job_id,
            job=job,
            upload_target=mock_upload_target,
        ),
    )

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={backend},
    )

    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    request = execution_pb2.AssignNextJobRequest(backend=backend)
    response = server.AssignNextJob(request, context)

    patch_fetch_next_job.assert_called_once_with(request)
    assert response.error == error_detail_pb2.ErrorDetail()
    assert response.job_id == mock_metadata.job_id
    assert response.job == job
    assert response.upload_target == mock_upload_target


@mock_aws
def test_assign_next_job_no_job(mocker) -> None:  # noqa: ANN001
    """Test that there is no job assigned to the physical laboratory server."""
    backend = "qpu"
    context = MagicMock()
    patch_fetch_next_job = mocker.patch.object(
        JobManager,
        "fetch_next_job_to_execute",
        return_value=execution_pb2.AssignNextJobResponse(),
    )

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={backend},
    )

    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    request = execution_pb2.AssignNextJobRequest(backend=backend)
    response = server.AssignNextJob(request, context)

    patch_fetch_next_job.assert_called_once_with(request)
    assert response == execution_pb2.AssignNextJobResponse()


@mock_aws
def test_report_execution_result_success(mocker) -> None:  # noqa: ANN001
    """Test that the execution result is reported to the job manager."""
    context = MagicMock()
    job_id = "test-job-id"
    request = execution_pb2.ReportExecutionResultRequest(
        job_id=job_id,
        status=execution_pb2.ExecutionStatus.EXECUTION_STATUS_SUCCESS,
        actual_backend="qpu",
        uploaded_result=job_pb2.JobUploadedResult(
            raw_size_bytes=2,
            encoded_size_bytes=1,
        ),
        version=execution_pb2.ExecutionVersion(
            physical_lab="0.0.2",
            quantum_computer="0.0.3",
        ),
        timestamps=job_pb2.JobTimestamps(
            submitted_at=Timestamp(seconds=1),
            queued_at=Timestamp(seconds=2),
            dequeued_at=Timestamp(seconds=3),
            compile_started_at=Timestamp(seconds=4),
            compile_finished_at=Timestamp(seconds=5),
            execution_started_at=Timestamp(seconds=6),
            execution_finished_at=Timestamp(seconds=7),
        ),
    )

    patch_finalize_job = mocker.patch.object(
        JobManager,
        "finalize_job",
        return_value=execution_pb2.ReportExecutionResultResponse(),
    )

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={"qpu"},
    )

    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    response = server.ReportExecutionResult(request, context)

    patch_finalize_job.assert_called_once_with(request)
    assert response == execution_pb2.ReportExecutionResultResponse()


@mock_aws
def test_refresh_upload_url_success(mocker) -> None:  # noqa: ANN001
    """Test that refreshing the upload url successfully."""
    context = MagicMock()
    job_id = "test-job-id"
    request = execution_pb2.RefreshUploadUrlRequest(job_id=job_id)
    mock_upload_url = "refreshed-url"
    expires_at = Timestamp(seconds=get_current_timestamp().seconds + 1000)
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token="test-token",  # noqa: S106
        role="guest",
        requested_backend="qpu",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.RUNNING,
    )
    patch_get_job_result_download_url = mocker.patch.object(
        JobManager,
        "get_job_result_upload_url",
        return_value=(mock_upload_url, expires_at),
    )
    mocker.patch.object(JobManager, "get_job_metadata", return_value=mock_metadata)

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={"qpu"},
    )
    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    response = server.RefreshUploadUrl(request, context)

    patch_get_job_result_download_url.assert_called_once_with(job_id)
    assert response == execution_pb2.RefreshUploadUrlResponse(
        upload_target=job_pb2.JobResultUploadTarget(upload_url=mock_upload_url, expires_at=expires_at)
    )


@mock_aws
def test_refresh_upload_url_failed(mocker) -> None:  # noqa: ANN001
    """Test that refreshing the upload url is failed."""
    context = MagicMock()
    job_id = "test-job-id"
    request = execution_pb2.RefreshUploadUrlRequest(job_id=job_id)
    mock_error = ClientError(error_response={"Error": {"Code": "400", "Message": "mock error"}}, operation_name="test")
    mock_metadata = JobMetadata(
        job_id="test_job_id",
        sdk_version="0.0.2",
        token="test-token",  # noqa: S106
        role="guest",
        requested_backend="qpu",
        n_shots=1,
        max_elapsed_s=1,
        save_job=False,
        status=JobStatus.RUNNING,
    )
    patch_get_job_result_download_url = mocker.patch.object(
        JobManager,
        "get_job_result_upload_url",
        side_effect=mock_error,
    )
    mocker.patch.object(JobManager, "get_job_metadata", return_value=mock_metadata)

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={"qpu"},
    )
    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    response = server.RefreshUploadUrl(request, context)

    patch_get_job_result_download_url.assert_called_once_with(job_id)
    assert response == execution_pb2.RefreshUploadUrlResponse(
        error=error_detail_pb2.ErrorDetail(
            code="INTERNAL", description="An internal error occurred. Please try again later."
        )
    )


@mock_aws
def test_refresh_upload_url_metadata_not_found(mocker) -> None:  # noqa: ANN001
    """Test that refreshing the upload url in case the metadata is not found in DB."""
    context = MagicMock()
    job_id = "test-job-id"
    request = execution_pb2.RefreshUploadUrlRequest(job_id=job_id)
    mock_upload_url = "refreshed-url"
    expires_at = Timestamp(seconds=get_current_timestamp().seconds + 1000)
    mock_error = ValueError("test error message")
    patch_get_job_result_download_url = mocker.patch.object(
        JobManager,
        "get_job_result_upload_url",
        return_value=(mock_upload_url, expires_at),
    )
    mocker.patch.object(JobManager, "get_job_metadata", side_effect=mock_error)

    dynamodb_table_name = "test-job-table"
    create_dynamodb_table(dynamodb_table_name)
    job_manager = JobManager(
        queue_capacity_bytes=1000,
        max_concurrent_jobs_per_token=None,
        job_repository=JobRepository(
            bucket_name="test-bucket",
            aws_credentials=AWSCredentials(
                endpoint_url=None,
                access_key_id=None,
                secret_access_key=None,
                region_name=None,
            ),
        ),
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends={"qpu"},
    )
    server = ExecutionServer(
        job_manager=job_manager,
        job_manager_lock=threading.RLock(),
    )

    response = server.RefreshUploadUrl(request, context)

    assert patch_get_job_result_download_url.call_count == 0
    assert response == execution_pb2.RefreshUploadUrlResponse(
        error=error_detail_pb2.ErrorDetail(code="NOT_FOUND", description=f"Job not found (ID: {job_id}).")
    )
