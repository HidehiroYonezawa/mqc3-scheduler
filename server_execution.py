"""Server class for execution service."""

import logging
import threading

import grpc
from job_manager.job_manager import JobManager
from job_manager.job_metadata import JobStatus
from message_manager.message_manager import get_status_message
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.scheduler.v1 import (
    execution_pb2,
    execution_pb2_grpc,
    job_pb2,
)

# Logging configuration
log_format = "%(asctime)s - %(levelname)-8s - %(message)s - %(filename)s:%(lineno)d"
logging.basicConfig(level=logging.INFO, format=log_format)

logger = logging.getLogger(__name__)


class ExecutionServer(execution_pb2_grpc.ExecutionService):
    """Server class for the execution service in scheduler."""

    job_manager: JobManager
    job_manager_lock: threading.RLock

    def __init__(
        self,
        job_manager: JobManager,
        job_manager_lock: threading.RLock,
    ) -> None:
        """Constructor of ExecutionServer.

        Args:
            job_manager (JobManager): Job manager.
            job_manager_lock (threading.RLock): Lock.
        """
        super().__init__()
        self.job_manager = job_manager
        self.job_manager_lock = job_manager_lock

    def AssignNextJob(
        self, request: execution_pb2.AssignNextJobRequest, _: grpc.RpcContext
    ) -> execution_pb2.AssignNextJobResponse:
        """Assign the job which will be executed on the physical lab server.

        Args:
            request (execution_pb2.AssignNextJobRequest): The request.
            _ (grpc.RpcContext): The gRPC context.

        Returns:
            execution_pb2.AssignNextJobResponse:  The next job sent to the physical laboratory.
        """
        with self.job_manager_lock:
            next_job = self.job_manager.fetch_next_job_to_execute(request)

        if next_job.job_id:
            logger.info(
                "Send a job to the physical laboratory (job ID: %s, backend: %s).", next_job.job_id, request.backend
            )

        return next_job

    def ReportExecutionResult(
        self,
        request: execution_pb2.ReportExecutionResultRequest,
        _: grpc.RpcContext,
    ) -> execution_pb2.ReportExecutionResultResponse:
        """Report the execution result of a job via the job manager.

        Args:
            request (execution_pb2.ReportExecutionResultRequest): The request.
            _ (grpc.RpcContext): The gRPC context.

        Returns:
            execution_pb2.ReportExecutionResultResponse: The response including error details when this request failed.
        """
        logger.debug("Reporting the execution result (job ID: %s).", request.job_id)
        with self.job_manager_lock:
            return self.job_manager.finalize_job(request)

    def RefreshUploadUrl(
        self, request: execution_pb2.RefreshUploadUrlRequest, _: grpc.RpcContext
    ) -> execution_pb2.RefreshUploadUrlResponse:
        """Regenerate new URL to upload the result of a job.

        Args:
            request (execution_pb2.RefreshUploadUrlRequest): The request including job_id.
            _ (grpc.RpcContext): The gRPC context.

        Returns:
            execution_pb2.RefreshUploadUrlResponse: The response including new upload URL and its expiration time.
        """
        # Check the current job status
        try:
            logger.info("Retrieving the job metadata (job ID: %s).", request.job_id)
            job_metadata = self.job_manager.get_job_metadata(request.job_id)
            if job_metadata.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                status_message = get_status_message(
                    key="INVALID_REQUEST",
                    reason="Job status is not QUEUED or RUNNING.",
                )
                logger.info("Job status is not QUEUED or RUNNING (job ID: %s).", request.job_id)
                return execution_pb2.RefreshUploadUrlResponse(
                    error=error_detail_pb2.ErrorDetail(
                        code=status_message.code,
                        description=status_message.message,
                    )
                )
        except ValueError as e:
            logger.info(str(e))
            status_message = get_status_message(key="JOB_NOT_FOUND", job_id=request.job_id)
            return execution_pb2.RefreshUploadUrlResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        except Exception:
            logger.exception("Failed to retrieve the job metadata (job ID: %s).", request.job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return execution_pb2.RefreshUploadUrlResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        try:
            logger.debug("Generating a new upload URL (job ID: %s).", request.job_id)
            upload_url, expires_at = self.job_manager.get_job_result_upload_url(request.job_id)
        except Exception:
            logger.exception("Failed to generate a new upload URL (job ID: %s).", request.job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return execution_pb2.RefreshUploadUrlResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.info("Successfully refreshed the upload URL (job ID: %s).", request.job_id)
        return execution_pb2.RefreshUploadUrlResponse(
            upload_target=job_pb2.JobResultUploadTarget(
                upload_url=upload_url,
                expires_at=expires_at,
            )
        )
