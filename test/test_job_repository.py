"""Tests for JobRepository."""

import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from pytest_mock import MockerFixture

sys.path.append(Path(__file__).parents[1].as_posix())


from common import SAMPLE_AWS_CREDENTIALS, construct_sample_program, construct_sample_settings
from google.protobuf.timestamp_pb2 import Timestamp
from job_manager.job_metadata import JobMetadata
from job_manager.job_repository import DOWNLOAD_URL_EXPIRATION_TIME, UPLOAD_URL_EXPIRATION_TIME, JobRepository


def create_bucket(bucket: str) -> None:
    """Create a bucket in S3.

    Args:
        bucket (str): bucket name
    """
    client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    client.create_bucket(Bucket=bucket)  # type: ignore  # noqa: PGH003

    client.put_object(Bucket=bucket, Key="job_1.out.proto.gz", Body="test_body")


@mock_aws
def test_job_repository_constructor() -> None:
    """Test constructor of JobRepository."""
    bucket = "test_bucket"
    create_bucket(bucket)

    s3_max_attempts = 10
    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
        s3_max_attempts=s3_max_attempts,
    )
    assert job_repository.bucket_name == bucket
    assert job_repository.s3.meta.config.retries["total_max_attempts"] == s3_max_attempts
    assert job_repository.s3.meta.config.retries["mode"] == "standard"


@mock_aws
def test_generate_upload_url(mocker: MockerFixture) -> None:
    """Test generating a presigned URL for uploading the result of a job to S3."""
    mocker.patch.object(Timestamp, "GetCurrentTime", return_value=Timestamp(seconds=0))
    bucket = "test_bucket"
    job_id = "test_job_id"
    create_bucket(bucket)
    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )

    # Default expiration time.
    upload_url, expires_at = job_repository.generate_upload_url(job_id)
    mocked_expected_expires_at = Timestamp(seconds=UPLOAD_URL_EXPIRATION_TIME)

    assert isinstance(expires_at, Timestamp)
    assert upload_url is not None
    assert bucket in upload_url
    assert job_id in upload_url
    assert expires_at == mocked_expected_expires_at

    # Custom expiration time.
    expires_in = 60 * 10
    upload_url, expires_at = job_repository.generate_upload_url(job_id, expires_in)
    mocked_expected_expires_at = Timestamp(seconds=expires_in)

    assert isinstance(expires_at, Timestamp)
    assert upload_url is not None
    assert bucket in upload_url
    assert job_id in upload_url
    assert expires_at == mocked_expected_expires_at


@mock_aws
def test_generate_download_url(mocker: MockerFixture) -> None:
    """Test generating a presigned URL for downloading the result of a job to S3."""
    mocker.patch.object(Timestamp, "GetCurrentTime", return_value=Timestamp(seconds=0))
    bucket = "test_bucket"
    job_id = "test_job_id"
    create_bucket(bucket)
    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )

    # Default expiration time.
    download_url, expires_at = job_repository.generate_download_url(job_id)
    mocked_expected_expires_at = Timestamp(seconds=DOWNLOAD_URL_EXPIRATION_TIME)

    assert isinstance(expires_at, Timestamp)
    assert download_url is not None
    assert bucket in download_url
    assert job_id in download_url
    assert expires_at == mocked_expected_expires_at

    # Custom expiration time.
    expires_in = 60 * 10
    download_url, expires_at = job_repository.generate_download_url(job_id, expires_in)
    mocked_expected_expires_at = Timestamp(seconds=expires_in)

    assert isinstance(expires_at, Timestamp)
    assert download_url is not None
    assert bucket in download_url
    assert job_id in download_url
    assert expires_at == mocked_expected_expires_at


@pytest.mark.parametrize(
    ("token_role", "save_job"),
    [
        ("admin", True),
        ("admin", False),
        ("user", True),
        ("user", False),
    ],
)
@mock_aws
def test_put_tags_to_result(token_role: str, save_job: bool) -> None:  # noqa: FBT001
    """Test putting tags to a job result."""
    bucket = "test_bucket"
    job_id = "job_1"
    create_bucket(bucket)
    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )

    job_repository.put_tags_to_result(job_id, token_role=token_role, save_job=save_job)
    client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    actual_tag = client.get_object_tagging(Bucket=bucket, Key=f"{job_id}.out.proto.gz")["TagSet"]
    actual_tag_dict = {tag["Key"]: tag["Value"] for tag in actual_tag}

    assert actual_tag_dict["token_role"] == token_role
    assert actual_tag_dict["save_job"] == str(save_job).lower()
    assert actual_tag_dict["upload-status"] == "complete"


@mock_aws
def test_upload_job_input() -> None:
    """Test uploading job input to S3."""
    bucket = "test_bucket"
    create_bucket(bucket)

    job_id = "job_1"
    token = "token1"  # noqa: S105
    role = "admin"
    save_job = True
    compiled_circuit = construct_sample_program()
    settings = construct_sample_settings()
    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=10,
        sdk_version="0.0.0",
        token=token,
        role=role,
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=save_job,
    )

    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )

    job_repository.upload_job_input(program=compiled_circuit, job_metadata=job_metadata)
    client = boto3.client("s3", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    actual_tag = client.get_object_tagging(Bucket=bucket, Key=f"{job_id}.in.proto")["TagSet"]
    actual_tag_dict = {tag["Key"]: tag["Value"] for tag in actual_tag}

    # Check if the object was uploaded with correct key.
    client.get_object(Bucket=bucket, Key=f"{job_id}.in.proto")

    assert actual_tag_dict["token_role"] == job_metadata.role
    assert actual_tag_dict["save_job"] == str(job_metadata.save_job).lower()
    assert actual_tag_dict["upload-status"] == "complete"


@mock_aws
def test_download_job_input() -> None:
    """Test downloading job input from S3."""
    bucket = "test_bucket"
    create_bucket(bucket)

    job_id = "job_1"
    compiled_circuit = construct_sample_program()
    settings = construct_sample_settings()
    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=10,
        sdk_version="0.0.0",
        token="token1",  # noqa: S106
        role="admin",
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=False,
    )

    job_repository = JobRepository(
        bucket_name=bucket,
        aws_credentials=SAMPLE_AWS_CREDENTIALS,
    )

    # Upload the job input to test downloading
    job_repository.upload_job_input(program=compiled_circuit, job_metadata=job_metadata)

    downloaded_program = job_repository.download_job_input(job_id=job_id)
    assert downloaded_program is not None
    assert downloaded_program == compiled_circuit

    assert job_repository.download_job_input(job_id="invalid job id") is None
