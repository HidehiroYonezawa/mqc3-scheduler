"""Job manager module."""

import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, cast

import boto3
from __version__ import __version__
from botocore.client import ClientError
from botocore.config import Config
from get_token_info import TokenInfo
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from message_manager.message_manager import StatusMessage, get_status_message
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.scheduler.v1 import execution_pb2, job_pb2, submission_pb2
from utility import (
    AWSCredentials,
    convert_datetime_to_timestamp,
    convert_timestamp_to_datetime,
    get_current_datetime,
    get_current_timestamp,
    get_relative_timestamp,
)

from . import dynamodb_helper
from .job_metadata import JobMetadata, JobStatus, StateSavePolicy
from .job_queue import JobQueueContainer
from .job_repository import JobRepository

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


logger = logging.getLogger(__name__)


class JobManager:
    """Job manager class."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        queue_capacity_bytes: int,
        max_concurrent_jobs_per_token: dict[str, int] | None,
        job_repository: JobRepository,
        supported_backends: set[str],
        aws_credentials: AWSCredentials,
        dynamodb_table_name: str,
        dynamodb_max_attempts: int = 3,
        unify_backends: bool = False,
    ) -> None:
        """Initialize the job manager.

        Args:
            queue_capacity_bytes (int): The capacity of the job queue in bytes.
            max_concurrent_jobs_per_token (dict[str, int] | None):
                Mapping from role to the maximum number of concurrent jobs per token.

                Limits the number of jobs a single token can have concurrently for each role.
                If this is ``None`` or the role is not present in the mapping, no limit is applied.
            job_repository (JobRepository): The job repository.
            supported_backends (set[str]): Set of all supported backends.
            aws_credentials (AWSCredentials): The AWS credentials.
            dynamodb_table_name (str): The name of the DynamoDB table.
            dynamodb_max_attempts (int): The maximum number of attempts for each DynamoDB operation.
            unify_backends (bool): Whether to merge backends when scheduling jobs.

        Raises:
            RuntimeError: If the DynamoDB table is not available.
        """
        self.job_queue = JobQueueContainer(
            backends=supported_backends,
            capacity_bytes=queue_capacity_bytes,
            max_concurrent_jobs_per_token=max_concurrent_jobs_per_token,
            unify_backends=unify_backends,
        )

        self.job_repository = job_repository

        self.table_name = dynamodb_table_name
        self.dynamodb_client = cast(
            "DynamoDBClient",
            boto3.client(
                "dynamodb",
                endpoint_url=aws_credentials.endpoint_url,
                aws_access_key_id=aws_credentials.access_key_id,
                aws_secret_access_key=aws_credentials.secret_access_key,
                region_name=aws_credentials.region_name,
                config=Config(
                    retries={"total_max_attempts": dynamodb_max_attempts, "mode": "standard"},
                ),
            ),
        )

        if not dynamodb_helper.check_table_exists(dynamodb_client=self.dynamodb_client, table_name=self.table_name):
            msg = f"DynamoDB table '{self.table_name}' is not available."
            raise RuntimeError(msg)

        # Restore `QUEUED` jobs
        self._restore_job_queue()
        # Fail `RUNNING` jobs
        dynamodb_helper.change_items_status(
            dynamodb_client=self.dynamodb_client,
            table_name=self.table_name,
            old_status=JobStatus.RUNNING,
            new_status=JobStatus.FAILED,
        )

    def _map_execution_status_to_job_status(self, execution_status: execution_pb2.ExecutionStatus) -> JobStatus:
        """Map the execution status to the job status.

        Args:
            execution_status (execution_pb2.ExecutionStatus): The execution status.

        Returns:
            JobStatus: The job status.
        """
        match execution_status:
            case execution_pb2.ExecutionStatus.EXECUTION_STATUS_SUCCESS:
                return JobStatus.COMPLETED
            case execution_pb2.ExecutionStatus.EXECUTION_STATUS_FAILURE:
                return JobStatus.FAILED
            case execution_pb2.ExecutionStatus.EXECUTION_STATUS_TIMEOUT:
                return JobStatus.TIMEOUT
            case _:
                logger.warning("Unknown execution status: %s. Falling back to UNSPECIFIED.", execution_status)
                return JobStatus.UNSPECIFIED

    def _mark_queued_job_as_failed(self, job_id: str, status_message: StatusMessage, dequeued_at: Timestamp) -> None:
        """Update the status of a queued job to FAILED.

        Args:
            job_id (str): The job ID.
            status_message (StatusMessage): The status message representing the failure reason.
            dequeued_at (Timestamp): The timestamp when the job was dequeued.
        """
        update_values = {
            "status": JobStatus.FAILED,
            "status_code": status_message.code,
            "status_message": status_message.message,
            "dequeued_at": dequeued_at,
        }

        try:
            logger.debug("Updating the job status to FAILED (job ID: %s).", job_id)
            dynamodb_helper.update_item(
                dynamodb_client=self.dynamodb_client,
                table_name=self.table_name,
                job_id=job_id,
                update_values=update_values,
            )
        except Exception:
            logger.exception("Failed to update the job status to FAILED (job ID: %s).", job_id)

    def _restore_job_queue(self) -> None:
        """Restore the job queue from the DynamoDB table.

        Raises:
            RuntimeError: If failed to retrieve queued items from the DynamoDB table.
        """
        try:
            queued_items = dynamodb_helper.get_items_by_status(
                dynamodb_client=self.dynamodb_client, table_name=self.table_name, status=JobStatus.QUEUED.name
            )
        except ClientError as e:
            msg = "Failed to retrieve queued items."
            logger.exception(msg)
            raise RuntimeError(msg) from e

        for item in queued_items:
            job_metadata = JobMetadata.from_dynamodb_item(item)
            job_id = job_metadata.job_id

            requested_backend = job_metadata.requested_backend
            if job_metadata.requested_backend not in self.job_queue:
                logger.error(
                    "Failed to restore a job due to unknown backend (job ID: %s, requested backend: %s).",
                    job_id,
                    requested_backend,
                )
                self._mark_queued_job_as_failed(
                    job_id=job_id,
                    status_message=get_status_message(key="CRITICAL_ERROR"),
                    dequeued_at=get_current_timestamp(),
                )
                continue

            queued_at = job_metadata.queued_at
            if queued_at is None:
                logger.error(
                    "Failed to restore a job due to missing 'queued_at' (job ID: %s).",
                    job_id,
                )
                self._mark_queued_job_as_failed(
                    job_id=job_id,
                    status_message=get_status_message(key="CRITICAL_ERROR"),
                    dequeued_at=get_current_timestamp(),
                )
                continue

            program = self.job_repository.download_job_input(job_id=job_id)
            if program is None:
                logger.error("Failed to download a job program (job ID: %s).", job_id)
                self._mark_queued_job_as_failed(
                    job_id=job_id,
                    status_message=get_status_message(key="INTERNAL_ERROR"),
                    dequeued_at=get_current_timestamp(),
                )
                continue

            if not self.job_queue[requested_backend].try_push(
                job_id=job_id,
                program=program,
                token=job_metadata.token,
                role=job_metadata.role,
                queued_at=convert_timestamp_to_datetime(queued_at),
                timeout=timedelta(seconds=job_metadata.max_elapsed_s),
            ):
                logger.error("Failed to restore a job due to current resource limits (job ID: %s).", job_id)
                self._mark_queued_job_as_failed(
                    job_id=job_id,
                    status_message=get_status_message(key="RESOURCE_LIMIT_EXCEEDED"),
                    dequeued_at=get_current_timestamp(),
                )

    def add_job_request(self, job_request: submission_pb2.SubmitJobRequest, token_info: TokenInfo) -> JobMetadata:  # noqa: PLR0915
        """Add a job request to the job manager.

        Args:
           job_request (submission_pb2.SubmitJobRequest): The job request.
           token_info (TokenInfo): The token information.

        Returns:
           JobMetadata: The entry job metadata including the job ID.
        """
        requested_backend = job_request.job.settings.backend

        job_id = str(uuid.uuid4())
        logger.debug("Created a job ID: %s.", job_id)

        job_metadata = JobMetadata(
            job_id=job_id,
            max_elapsed_s=job_request.job.settings.timeout.seconds,
            sdk_version=job_request.sdk_version,
            token=job_request.token,
            role=token_info.role,
            requested_backend=requested_backend,
            n_shots=job_request.job.settings.n_shots,
            save_job=job_request.options.save_job,
            state_save_policy=StateSavePolicy(job_request.job.settings.state_save_policy),
            resource_squeezing_level=job_request.job.settings.resource_squeezing_level,
            scheduler_version=__version__,
        )

        logger.debug("Adding a job to the job queue (job ID: %s).", job_id)
        if requested_backend not in self.job_queue:
            logger.debug("%s is not a supported backend (job ID: %s).", requested_backend, job_id)
            status_message = get_status_message(
                key="INVALID_REQUEST", reason=f"{requested_backend} is not a supported backend."
            )
            job_metadata.status = JobStatus.FAILED
            job_metadata.status_code = status_message.code
            job_metadata.status_message = status_message.message
        else:
            # Add the job to the job queue
            try:
                queued_at = get_current_datetime()
                if self.job_queue[requested_backend].try_push(
                    job_id=job_id,
                    program=job_request.job.program,
                    token=job_request.token,
                    role=token_info.role,
                    queued_at=queued_at,
                    timeout=timedelta(seconds=job_request.job.settings.timeout.seconds),
                ):
                    job_metadata.status = JobStatus.QUEUED
                    job_metadata.queued_at = convert_datetime_to_timestamp(queued_at)
                else:
                    status_message = get_status_message(key="RESOURCE_LIMIT_EXCEEDED")
                    job_metadata.status = JobStatus.FAILED
                    job_metadata.status_code = status_message.code
                    job_metadata.status_message = status_message.message
            except ValueError:
                # If a job with the same ID is already in the queue, return immediately without overwriting it.
                logger.exception("Failed to add the job to the queue (job ID: %s).", job_id)
                status_message = get_status_message(key="CRITICAL_ERROR")
                job_metadata.status = JobStatus.FAILED
                job_metadata.status_code = status_message.code
                job_metadata.status_message = status_message.message
                return job_metadata

            if job_metadata.status != JobStatus.FAILED:
                try:
                    self.job_repository.upload_job_input(program=job_request.job.program, job_metadata=job_metadata)
                except ClientError:
                    status_message = get_status_message(key="INTERNAL_ERROR")
                    job_metadata.status = JobStatus.FAILED
                    job_metadata.status_code = status_message.code
                    job_metadata.status_message = status_message.message
                except Exception:
                    logger.exception("Failed to upload the job input (job ID: %s).", job_metadata.job_id)
                    status_message = get_status_message(key="CRITICAL_ERROR")
                    job_metadata.status = JobStatus.FAILED
                    job_metadata.status_code = status_message.code
                    job_metadata.status_message = status_message.message

        try:
            logger.debug("Uploading the job metadata to the database (job ID: %s).", job_id)
            dynamodb_helper.put_item(
                dynamodb_client=self.dynamodb_client,
                table_name=self.table_name,
                dynamodb_item=job_metadata.to_dynamodb_item(),
            )
        except Exception:
            logger.exception("Failed to upload the job metadata to the database (job ID: %s).", job_id)
            if job_metadata.status == JobStatus.QUEUED:
                self.job_queue[requested_backend].try_remove(job_id=job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            job_metadata.status = JobStatus.FAILED
            job_metadata.status_code = status_message.code
            job_metadata.status_message = status_message.message

        return job_metadata

    def cancel_job(self, job_id: str) -> tuple[bool, StatusMessage]:
        """Cancel a job.

        Args:
          job_id (str): Job ID.

        Returns:
           tuple[bool, StatusMessage]: A tuple of (success, error_message)
           - success (bool): True if the job was successfully cancelled, False otherwise.
           - error_message (StatusMessage): Error code and message on failure, empty on success.
        """
        try:
            # Check if the job exists in the DynamoDB table.
            if not dynamodb_helper.check_item_exists(
                dynamodb_client=self.dynamodb_client, table_name=self.table_name, job_id=job_id
            ):
                logger.debug("The item with job ID %s does not exist in the database.", job_id)
                return False, get_status_message(key="JOB_NOT_FOUND", job_id=job_id)

            # Remove the job from the queue.
            job_metadata = self.get_job_metadata(job_id=job_id)
            backend = job_metadata.requested_backend

            if self.job_queue[backend].try_remove(job_id=job_id):
                logger.debug("The job was successfully removed from the queue (job ID: %s).", job_id)
            else:
                logger.debug("The job may already be running or cancelled (job ID: %s).", job_id)
                return False, get_status_message(key="INVALID_JOB_STATE")

            # Update the job status to CANCELLED.
            logger.debug("Updating the job status to CANCELLED (job ID: %s).", job_id)
            dynamodb_helper.update_item(
                dynamodb_client=self.dynamodb_client,
                table_name=self.table_name,
                job_id=job_id,
                update_values={"status": JobStatus.CANCELLED},
            )
        except Exception:
            logger.exception("Failed to cancel the job (job ID: %s).", job_id)
            return False, get_status_message(key="INTERNAL_ERROR")

        return True, StatusMessage()

    def get_job_metadata(self, job_id: str, *, consistent_read: bool = False) -> JobMetadata:
        """Get the metadata of a job.

        Args:
          job_id (str): Job ID.
          consistent_read (bool): Determines the read consistency model.
            If set to True, a strongly consistent read is performed,
            which returns the most recent data but consumes double the read capacity units.
            If set to False, an eventually consistent read is performed.
            The results might not reflect a recently completed write.

        Raises:
           ValueError: If the job ID is invalid.

        Returns:
           JobMetadata: The metadata of the job.
        """
        if not dynamodb_helper.check_item_exists(
            dynamodb_client=self.dynamodb_client,
            table_name=self.table_name,
            job_id=job_id,
            consistent_read=consistent_read,
        ):
            msg = f"The item with job ID {job_id} does not exist in the database."
            raise ValueError(msg)
        item = dynamodb_helper.get_item(
            dynamodb_client=self.dynamodb_client, table_name=self.table_name, job_id=job_id
        )
        return JobMetadata.from_dynamodb_item(dynamodb_item=item)

    def fetch_next_job_to_execute(
        self, request: execution_pb2.AssignNextJobRequest
    ) -> execution_pb2.AssignNextJobResponse:
        """Fetch the next job from the queue and construct a job request for the physical lab layer.

        Args:
            request (execution_pb2.AssignNextJobRequest): The request from the physical lab layer.

        Returns:
           execution_pb2.AssignNextJobResponse: The job request for the physical lab layer.
        """
        requested_backend = request.backend
        if requested_backend not in self.job_queue:
            msg = f"{requested_backend} is not a supported backend."
            logger.debug(msg)
            status_message = get_status_message(key="INVALID_REQUEST", reason=msg)
            return execution_pb2.AssignNextJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Fetching the next job from the queue.")
        next_job = self.job_queue[requested_backend].try_pop()
        if next_job is None:
            return execution_pb2.AssignNextJobResponse()

        job_id, program = next_job
        dequeued_at = get_current_timestamp()

        # Retrieve the execution settings
        try:
            logger.debug("Retrieving the job metadata (job ID: %s).", job_id)
            job_metadata = self.get_job_metadata(job_id=job_id, consistent_read=True)
            settings = job_pb2.JobExecutionSettings(
                backend=job_metadata.requested_backend,
                n_shots=job_metadata.n_shots,
                timeout=Duration(seconds=job_metadata.max_elapsed_s),
                state_save_policy=job_metadata.state_save_policy.value,
                resource_squeezing_level=job_metadata.resource_squeezing_level,
                role=job_metadata.role,
            )
        except Exception:
            logger.exception("Failed to retrieve the execution settings (job ID: %s).", job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            self._mark_queued_job_as_failed(job_id=job_id, status_message=status_message, dequeued_at=dequeued_at)
            return execution_pb2.AssignNextJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                ),
            )

        # Generate the upload URL
        try:
            upload_url, expires_at = self.job_repository.generate_upload_url(job_id)
        except Exception:
            logger.exception("Failed to generate the upload URL (job ID: %s).", job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            self._mark_queued_job_as_failed(job_id=job_id, status_message=status_message, dequeued_at=dequeued_at)
            return execution_pb2.AssignNextJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                ),
            )

        # Update the job metadata
        try:
            logger.debug("Updating the job status to RUNNING (job ID: %s).", job_id)
            dynamodb_helper.update_item(
                dynamodb_client=self.dynamodb_client,
                table_name=self.table_name,
                job_id=job_id,
                update_values={
                    "status": JobStatus.RUNNING,
                    "dequeued_at": dequeued_at,
                },
            )
            return execution_pb2.AssignNextJobResponse(
                job_id=job_id,
                job=job_pb2.Job(
                    program=program,
                    settings=settings,
                ),
                upload_target=job_pb2.JobResultUploadTarget(
                    upload_url=upload_url,
                    expires_at=expires_at,
                ),
            )
        except Exception:
            logger.exception("Failed to update the job status to RUNNING (job ID: %s).", job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return execution_pb2.AssignNextJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                ),
            )

    def finalize_job(
        self, execution_result: execution_pb2.ReportExecutionResultRequest
    ) -> execution_pb2.ReportExecutionResultResponse:
        """Finalize a job.

        Args:
            execution_result (execution_pb2.ReportExecutionResultRequest): The result of the job execution.

        Returns:
            execution_pb2.ReportExecutionResultResponse: Response to the physical lab layer.
        """
        job_id = execution_result.job_id
        try:
            if not dynamodb_helper.check_item_exists(
                dynamodb_client=self.dynamodb_client, table_name=self.table_name, job_id=job_id
            ):
                logger.warning(
                    "Failed to finalize job because the corresponding job was not found (job ID: %s).", job_id
                )
                status_message = get_status_message(key="JOB_NOT_FOUND", job_id=job_id)
                return execution_pb2.ReportExecutionResultResponse(
                    error=error_detail_pb2.ErrorDetail(
                        code=status_message.code,
                        description=status_message.message,
                    )
                )
        except Exception:
            logger.exception("Failed to finalize job due to an internal error (job ID: %s).", job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return execution_pb2.ReportExecutionResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        status = self._map_execution_status_to_job_status(execution_result.status)

        if status == JobStatus.COMPLETED:
            # Set tags to the result object in S3 bucket.
            try:
                logger.debug("Set tags to the result object (job ID: %s).", job_id)
                job_metadata = self.get_job_metadata(job_id=job_id)
                self.job_repository.put_tags_to_result(
                    job_id=job_id, token_role=job_metadata.role, save_job=job_metadata.save_job
                )
            except Exception:
                logger.exception("Failed to set tags to the result object (job ID: %s).", job_id)
                status_message = get_status_message(key="INTERNAL_ERROR")
                return execution_pb2.ReportExecutionResultResponse(
                    error=error_detail_pb2.ErrorDetail(
                        code=status_message.code,
                        description=status_message.message,
                    )
                )

        try:
            logger.debug("Updating the job metadata (job ID: %s).", job_id)
            dynamodb_helper.update_item(
                dynamodb_client=self.dynamodb_client,
                table_name=self.table_name,
                job_id=job_id,
                update_values={
                    "status": status,
                    "status_code": execution_result.error.code,
                    "status_message": execution_result.error.description,
                    "actual_backend_name": execution_result.actual_backend,
                    "physical_lab_version": execution_result.version.physical_lab,
                    "quantum_computer_version": execution_result.version.quantum_computer,
                    "simulator_version": execution_result.version.simulator,
                    "compile_started_at": execution_result.timestamps.compile_started_at,
                    "compile_finished_at": execution_result.timestamps.compile_finished_at,
                    "execution_started_at": execution_result.timestamps.execution_started_at,
                    "execution_finished_at": execution_result.timestamps.execution_finished_at,
                    "raw_size_bytes": execution_result.uploaded_result.raw_size_bytes,
                    "encoded_size_bytes": execution_result.uploaded_result.encoded_size_bytes,
                    "finished_at": get_current_timestamp(),
                    "job_expiry": get_relative_timestamp(timedelta(days=30)),
                },
            )
        except Exception:
            logger.exception("Failed to update the job metadata (job ID: %s).", job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return execution_pb2.ReportExecutionResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        logger.info("Successfully updated the finished job metadata (job ID: %s).", job_id)
        return execution_pb2.ReportExecutionResultResponse()

    def get_job_result_download_url(self, job_id: str) -> tuple[str, Timestamp]:
        """Get the download URL of the result of the job.

        This method may raise an exception if generating the URL is failed.

        Args:
            job_id (str): Job ID.

        Returns:
            tuple[str, Timestamp]: Download URL of the result of the job and the timestamp when the URL expires.
        """
        return self.job_repository.generate_download_url(job_id=job_id)

    def get_job_result_upload_url(self, job_id: str) -> tuple[str, Timestamp]:
        """Get the upload URL of the result of the job.

        This method may raise an exception if generating the URL is failed.

        Args:
            job_id (str): Job ID.

        Returns:
            tuple[str, Timestamp]: Upload URL of the result of the job and the timestamp when the URL expires.
        """
        return self.job_repository.generate_upload_url(job_id=job_id)
