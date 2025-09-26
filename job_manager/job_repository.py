"""Uploading inputs and results of jobs to S3 bucket."""

import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from google.protobuf.timestamp_pb2 import Timestamp
from job_manager.job_metadata import JobMetadata
from pb.mqc3_cloud.program.v1 import quantum_program_pb2
from utility import AWSCredentials

logger = logging.getLogger(__name__)

UPLOAD_URL_EXPIRATION_TIME = 3600 * 3  # 3 hours
DOWNLOAD_URL_EXPIRATION_TIME = 180  # 3 minutes


class JobRepository:
    """Class to upload inputs and results of jobs to the S3 bucket."""

    def __init__(
        self,
        *,
        bucket_name: str,
        aws_credentials: AWSCredentials,
        s3_max_attempts: int = 3,
    ) -> None:
        """Initialize JobRepository object.

        Args:
            bucket_name (str): S3 bucket name
            aws_credentials (AWSCredentials): AWS credentials
            s3_max_attempts (int): The maximum number of attempts for each S3 operation.
        """
        self.bucket_name = bucket_name

        self.s3 = boto3.client(
            "s3",
            endpoint_url=aws_credentials.endpoint_url,
            aws_access_key_id=aws_credentials.access_key_id,
            aws_secret_access_key=aws_credentials.secret_access_key,
            region_name=aws_credentials.region_name,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
                retries={"total_max_attempts": s3_max_attempts, "mode": "standard"},
            ),
        )

    def bucket_exists(self) -> bool:
        """Check if the S3 bucket exists.

        Returns:
            bool: True if the S3 bucket exists, False otherwise.
        """
        try:
            logger.info("Checking if S3 bucket exists (bucket name: %s).", self.bucket_name)
            self.s3.head_bucket(Bucket=self.bucket_name)
        except self.s3.exceptions.NoSuchBucket:
            return False
        except Exception:
            logger.exception("Failed to check if S3 bucket exists (bucket name: %s).", self.bucket_name)
            return False

        return True

    def generate_upload_url(self, job_id: str, expires_in: int = UPLOAD_URL_EXPIRATION_TIME) -> tuple[str, Timestamp]:
        """Generate a presigned URL for uploading the result of a job.

        Args:
            job_id (str): ID of the job
            expires_in (int): Time in seconds until the generated URL expires.

        Returns:
            tuple[str, Timestamp]: A tuple containing the presigned URL and its expiration timestamp.

        Raises:
            ClientError: If the presigned URL could not be generated.
        """
        expires_at = Timestamp()
        expires_at.GetCurrentTime()
        expires_at.FromSeconds(expires_at.seconds + expires_in)
        try:
            logger.info("Generating a presigned URL for uploading the result (job ID: %s).", job_id)
            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": f"{job_id}.out.proto.gz",
                    "ContentType": "application/protobuf",
                    "ContentEncoding": "gzip",
                    "ContentDisposition": "attachment",
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
        except ClientError:
            logger.exception("Failed to generate a presigned URL for uploading the result (job ID: %s).", job_id)
            raise

        return url, expires_at

    def generate_download_url(
        self, job_id: str, expires_in: int = DOWNLOAD_URL_EXPIRATION_TIME
    ) -> tuple[str, Timestamp]:
        """Generate a presigned URL for downloading the result of a job.

        Args:
            job_id (str): ID of the job
            expires_in (int): Time in seconds until the generated URL expires.

        Returns:
            tuple[str, Timestamp]: A tuple containing the presigned URL and its expiration timestamp.

        Raises:
            ClientError: If the presigned URL could not be generated.
        """
        expires_at = Timestamp()
        expires_at.GetCurrentTime()
        expires_at.FromSeconds(expires_at.seconds + expires_in)
        try:
            logger.info("Generating a presigned URL for downloading the result (job ID: %s)", job_id)
            url = self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": f"{job_id}.out.proto.gz",
                },
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )
        except ClientError:
            logger.exception("Failed to generate a presigned URL for downloading the result (job ID: %s).", job_id)
            raise

        return url, expires_at

    def put_tags_to_result(self, job_id: str, *, token_role: str, save_job: bool) -> None:
        """Put tags to the result of a job.

        Args:
            job_id (str): ID of the job.
            token_role (str): Role of the token.
            save_job (bool): Whether to save the job.

        Raises:
            ClientError: If failed to put tags to the result of a job.
        """
        try:
            # `upload-status` tag is used to control one-time uploads via a presigned URL.
            logger.info("Putting tags to the job result (job ID: %s).", job_id)
            self.s3.put_object_tagging(
                Bucket=self.bucket_name,
                Key=f"{job_id}.out.proto.gz",
                Tagging={
                    "TagSet": [
                        {"Key": "token_role", "Value": token_role},
                        {"Key": "save_job", "Value": str(save_job).lower()},
                        {
                            "Key": "upload-status",
                            "Value": "complete",
                        },
                    ]
                },
            )
        except ClientError:
            logger.exception("Failed to put tags to the job result (job ID: %s).", job_id)
            raise

    def upload_job_input(self, program: quantum_program_pb2.QuantumProgram, job_metadata: JobMetadata) -> None:
        """Upload the input of a job to S3.

        Args:
            program (quantum_program_pb2.QuantumProgram): Program to upload.
            job_metadata (JobMetadata): Metadata of the job.
        """
        try:
            logger.info("Uploading the job input (job ID: %s).", job_metadata.job_id)
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=f"{job_metadata.job_id}.in.proto",
                Body=program.SerializeToString(),
                ContentType="application/protobuf",
                ContentDisposition="attachment",
                Tagging=f"token_role={job_metadata.role}&save_job={str(job_metadata.save_job).lower()}&upload-status=complete",
            )

        except ClientError:
            logger.exception("Failed to upload the job input (job ID: %s).", job_metadata.job_id)

    def download_job_input(self, job_id: str) -> quantum_program_pb2.QuantumProgram | None:
        """Download the input of a job from S3.

        Args:
            job_id (str): ID of the job.

        Returns:
            QuantumProgram | None: Deserialized program, or None if the download failed.
        """
        try:
            logger.info("Downloading the input of the job (job ID: %s).", job_id)
            response = self.s3.get_object(
                Bucket=self.bucket_name,
                Key=f"{job_id}.in.proto",
            )
            return quantum_program_pb2.QuantumProgram.FromString(response["Body"].read())

        except ClientError:
            logger.exception("Failed to download the job input (job ID: %s).", job_id)
            return None
