"""Server class for submission service."""

import logging
import threading
from dataclasses import dataclass

import grpc
from backend_manager.backend_manager import BackendAvailability, BackendManager
from get_token_info import TokenDatabaseError, TokenInfo, get_token_info
from job_manager.job_manager import JobManager
from job_manager.job_metadata import JobStatus
from message_manager.message_manager import get_status_message
from pb.mqc3_cloud.common.v1 import error_detail_pb2
from pb.mqc3_cloud.scheduler.v1 import (
    job_pb2,
    submission_pb2,
    submission_pb2_grpc,
)
from utility import get_current_datetime

# Logging configuration
log_format = "%(asctime)s - %(levelname)-8s - %(message)s - %(filename)s:%(lineno)d"
logging.basicConfig(level=logging.INFO, format=log_format)

logger = logging.getLogger(__name__)


@dataclass
class BackendStatusResult:
    """Result wrapper for backend availability resolution.

    This class represents the outcome of a backend availability check
    for a given backend and user role. It encapsulates either a successful
    result (`availability`) or an error (`error`), but never both.

    Attributes:
        availability (BackendAvailability | None):
            The availability information if the lookup succeeded.
            Will be `None` if an error occurred.

        error (ErrorDetail | None):
            The error information if the lookup failed (e.g., unknown backend or role).
            Will be `None` if the availability information is valid.
    """

    availability: BackendAvailability | None
    error: error_detail_pb2.ErrorDetail | None


class SubmissionServer(submission_pb2_grpc.SubmissionService):
    """Server class for the submission service in scheduler."""

    address_to_token_database: str
    job_manager: JobManager
    job_manager_lock: threading.RLock

    def __init__(  # noqa: PLR0913
        self,
        *,
        address_to_token_database: str,
        backend_manager: BackendManager,
        backend_manager_lock: threading.RLock,
        job_manager: JobManager,
        job_manager_lock: threading.RLock,
        max_job_bytes: dict[str, int],
    ) -> None:
        """Constructor of SubmissionServer.

        Args:
            address_to_token_database (str): the Address to token database server.
            backend_manager (BackendManager): Backend manager.
            backend_manager_lock (threading.RLock): Lock.
            job_manager (JobManager): Job manager.
            job_manager_lock (threading.RLock): Lock.
            max_job_bytes (dict[str, int]): Role to maximum byte size of submission job.
        """
        super().__init__()
        self.address_to_token_database = address_to_token_database
        self.backend_manager = backend_manager
        self.backend_manager_lock = backend_manager_lock
        self.job_manager = job_manager
        self.job_manager_lock = job_manager_lock
        self.max_job_bytes = max_job_bytes

    def __verify_token(self, token: str) -> tuple[TokenInfo | None, str]:
        """Verify token sent by user.

        Args:
            token (str): Token sent by user.

        Raises:
            TokenDatabaseError: If failed to verify token.

        Returns:
            tuple[TokenInfo | None, str]: Token information and error message.
                If token is valid, token information is returned and error message is empty.
                If token is invalid, token information is None and error message is returned.
        """
        if not token:
            return None, "Token is empty."

        # Get token information from token database
        try:
            logger.info("Retrieving the token info from the token database (token: %s).", token)
            token_info = get_token_info(self.address_to_token_database, token)
        except TokenDatabaseError as e:
            msg = f"Failed to verify token (token: {token})."
            raise TokenDatabaseError(msg) from e

        # token is not found
        if token_info is None:
            return None, f"Token is not found (token: {token})."

        # token is expired
        if token_info.is_expired(get_current_datetime()):
            return None, f"Token is expired (token: {token})."

        return token_info, ""

    def _resolve_service_status(self, backend: str, role: str) -> BackendStatusResult:
        """Attempt to retrieve the backend status for a given backend and role.

        Returns:
            BackendStatusResult: Contains either a valid availability or an error.
        """
        with self.backend_manager_lock:
            try:
                return BackendStatusResult(
                    availability=self.backend_manager.get_backend_availability(backend, role),
                    error=None,
                )
            except ValueError as e:
                logger.info(str(e))
                status_message = get_status_message(key="INVALID_REQUEST", reason=str(e))
                return BackendStatusResult(
                    availability=None,
                    error=error_detail_pb2.ErrorDetail(
                        code=status_message.code,
                        description=status_message.message,
                    ),
                )
            except Exception:
                logger.exception("Failed to resolve the service status (backend: %s, role: %s).", backend, role)
                status_message = get_status_message(key="CRITICAL_ERROR")
                return BackendStatusResult(
                    availability=None,
                    error=error_detail_pb2.ErrorDetail(
                        code=status_message.code,
                        description=status_message.message,
                    ),
                )

    def SubmitJob(  # noqa: PLR0911
        self,
        request: submission_pb2.SubmitJobRequest,
        _: grpc.RpcContext,
    ) -> submission_pb2.SubmitJobResponse:
        """Register the job submitted by user to job manager.

        Args:
            request (submission_pb2.SubmitJobRequest): Request message.
            _ (grpc.RpcContext): gRPC context.

        Returns:
            submission_pb2.SubmitJobResponse: Response message.
        """
        logger.debug("Verifying the token for `SubmitJob` (token: %s).", request.token)
        try:
            token_info, error_message = self.__verify_token(request.token)
        except TokenDatabaseError:
            logger.exception("Failed to verify token due to token database error.")
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.SubmitJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        if token_info is None:
            logger.info(error_message)
            status_message = get_status_message(key="INVALID_TOKEN", reason=error_message)
            return submission_pb2.SubmitJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Checking the job byte size (role: %s).", token_info.role)
        byte_size = len(request.SerializeToString())
        if token_info.role in self.max_job_bytes and self.max_job_bytes[token_info.role] < byte_size:
            status_message = get_status_message(
                key="INVALID_REQUEST",
                reason=(
                    f"Byte size of request ({byte_size}) "
                    f"exceeds the allowed limit ({self.max_job_bytes[token_info.role]})"
                ),
            )
            return submission_pb2.SubmitJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Checking the current service status (role: %s).", token_info.role)
        service_status = self._resolve_service_status(request.job.settings.backend, token_info.role)

        if service_status.error is not None:
            return submission_pb2.SubmitJobResponse(error=service_status.error)
        assert service_status.availability is not None  # noqa: S101

        if service_status.availability.status != submission_pb2.ServiceStatus.SERVICE_STATUS_AVAILABLE:
            logger.info(
                "Service is not available (role: %s, status: %s).", token_info.role, service_status.availability.status
            )
            status_message = get_status_message(key="SERVER_UNAVAILABLE")
            return submission_pb2.SubmitJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Adding a job request to the job manager.")
        # Add the job to job manager.
        with self.job_manager_lock:
            initial_job_metadata = self.job_manager.add_job_request(job_request=request, token_info=token_info)

        if initial_job_metadata.status != JobStatus.QUEUED:
            logger.warning("Failed to register a job (job ID: %s).", initial_job_metadata.job_id)
            return submission_pb2.SubmitJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=initial_job_metadata.status_code,
                    description=initial_job_metadata.status_message,
                ),
            )

        logger.info("Successfully submitted a job (job ID: %s).", initial_job_metadata.job_id)
        return submission_pb2.SubmitJobResponse(job_id=initial_job_metadata.job_id)

    def GetJobStatus(
        self,
        request: submission_pb2.GetJobStatusRequest,
        _: grpc.RpcContext,
    ) -> submission_pb2.GetJobStatusResponse:
        """Return job status of the specified job_id.

        Args:
            request (submission_pb2.GetJobStatusRequest): Request message.
            _ (grpc.RpcContext): gRPC context.

        Returns:
            submission_pb2.GetJobStatusResponse: Response message.
        """
        logger.debug("Verifying the token for `GetJobStatus` (token: %s).", request.token)
        try:
            token_info, error_message = self.__verify_token(request.token)
        except TokenDatabaseError:
            logger.exception("Failed to verify token due to token database error.")
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetJobStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        if token_info is None:
            logger.info(error_message)
            status_message = get_status_message(key="INVALID_TOKEN", reason=error_message)
            return submission_pb2.GetJobStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        try:
            logger.info("Retrieving the job metadata (job ID: %s).", request.job_id)
            metadata = self.job_manager.get_job_metadata(job_id=request.job_id)
        except ValueError as e:
            logger.info(str(e))
            status_message = get_status_message(key="JOB_NOT_FOUND", job_id=request.job_id)
            return submission_pb2.GetJobStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        except Exception:
            logger.exception("Failed to retrieve the job metadata (job ID: %s).", request.job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetJobStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.info("Successfully retrieved the job status (job ID: %s).", request.job_id)
        return submission_pb2.GetJobStatusResponse(
            status=metadata.status.value,
            status_detail=metadata.status_message,
            execution_details=job_pb2.JobExecutionDetails(
                version=metadata.get_proto_execution_version(),
                timestamps=metadata.get_proto_job_timestamps(),
            ),
        )

    def GetJobResult(  # noqa: PLR0911
        self,
        request: submission_pb2.GetJobResultRequest,
        _: grpc.RpcContext,
    ) -> submission_pb2.GetJobResultResponse:
        """Return job result including presigned URL to download the result.

        Args:
            request (submission_pb2.GetJobResultRequest): Request message.
            _ (grpc.RpcContext): gRPC context.

        Returns:
            submission_pb2.GetJobResultResponse: Response message.
        """
        logger.debug("Verifying the token for `GetJobResult` (token: %s).", request.token)
        try:
            token_info, error_message = self.__verify_token(request.token)
        except TokenDatabaseError:
            logger.exception("Failed to verify token due to token database error.")
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        if token_info is None:
            logger.info(error_message)
            status_message = get_status_message(key="INVALID_TOKEN", reason=error_message)
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        try:
            logger.info("Retrieving the job metadata (job ID: %s).", request.job_id)
            metadata = self.job_manager.get_job_metadata(job_id=request.job_id)
        except ValueError as e:
            logger.info(str(e))
            status_message = get_status_message(key="JOB_NOT_FOUND", job_id=request.job_id)
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        except Exception:
            logger.exception("Failed to retrieve the job metadata (job ID: %s).", request.job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        if metadata.status != JobStatus.COMPLETED:
            description = (
                f"The job is not completed (job ID: {request.job_id}, current status: {metadata.status.name})."
            )
            logger.info(description)
            status_message = get_status_message(key="INVALID_REQUEST", reason=description)
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        try:
            logger.debug("Generating the URL to download the job result (job ID: %s).", request.job_id)
            result_url, _expires_at = self.job_manager.get_job_result_download_url(job_id=request.job_id)
        except Exception:
            logger.exception("Failed to generate the download URL (job ID: %s).", request.job_id)
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetJobResultResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        result = job_pb2.JobResult(result_url=result_url)

        logger.info("Successfully retrieved the job result (job ID: %s).", request.job_id)
        return submission_pb2.GetJobResultResponse(
            status=metadata.status.value,
            status_detail=metadata.status_message,
            execution_details=job_pb2.JobExecutionDetails(
                version=metadata.get_proto_execution_version(),
                timestamps=metadata.get_proto_job_timestamps(),
            ),
            result=result,
        )

    def CancelJob(
        self,
        request: submission_pb2.CancelJobRequest,
        _: grpc.RpcContext,
    ) -> submission_pb2.CancelJobResponse:
        """Cancel the specified job.

        Args:
            request (submission_pb2.CancelJobRequest): Request message.
            _ (grpc.RpcContext): gRPC context.

        Returns:
            submission_pb2.CancelJobResponse: Response message.
        """
        logger.debug("Verifying the token for `CancelJob` (token: %s).", request.token)
        try:
            token_info, error_message = self.__verify_token(request.token)
        except TokenDatabaseError:
            logger.exception("Failed to verify token due to token database error.")
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.CancelJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        if token_info is None:
            logger.info(error_message)
            status_message = get_status_message(key="INVALID_TOKEN", reason=error_message)
            return submission_pb2.CancelJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Canceling the job (job ID: %s).", request.job_id)
        with self.job_manager_lock:
            success, error_message = self.job_manager.cancel_job(job_id=request.job_id)

        if not success:
            logger.info("Failed to cancel the job (job ID: %s).", request.job_id)
            return submission_pb2.CancelJobResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=error_message.code,
                    description=error_message.message,
                )
            )

        # Return an empty response if the job is successfully cancelled.
        logger.info("Successfully cancelled the job (job ID: %s).", request.job_id)
        return submission_pb2.CancelJobResponse()

    def GetServiceStatus(
        self,
        request: submission_pb2.GetServiceStatusRequest,
        _: grpc.RpcContext,
    ) -> submission_pb2.GetServiceStatusResponse:
        """Return service status.

        Args:
            request (submission_pb2.GetServiceStatusRequest): Request message.
            _ (grpc.RpcContext): gRPC context.

        Returns:
            submission_pb2.GetServiceStatusResponse: Response message.
        """
        logger.debug("Verifying the token for `GetServiceStatus` (token: %s).", request.token)
        try:
            token_info, error_message = self.__verify_token(request.token)
        except TokenDatabaseError:
            logger.exception("Failed to verify token due to token database error.")
            status_message = get_status_message(key="INTERNAL_ERROR")
            return submission_pb2.GetServiceStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )
        if token_info is None:
            logger.info(error_message)
            status_message = get_status_message(key="INVALID_TOKEN", reason=error_message)
            return submission_pb2.GetServiceStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.debug("Resolving the service status (backend: %s, role: %s).", request.backend, token_info.role)
        service_status = self._resolve_service_status(request.backend, token_info.role)

        if service_status.error is not None:
            return submission_pb2.GetServiceStatusResponse(error=service_status.error)
        assert service_status.availability is not None  # noqa: S101

        if service_status.availability.status != submission_pb2.ServiceStatus.SERVICE_STATUS_AVAILABLE:
            logger.info(
                "Service is not available (role: %s, status: %s).", token_info.role, service_status.availability.status
            )
            status_message = get_status_message(key="SERVER_UNAVAILABLE")
            return submission_pb2.GetServiceStatusResponse(
                error=error_detail_pb2.ErrorDetail(
                    code=status_message.code,
                    description=status_message.message,
                )
            )

        logger.info("Service is available (role: %s).", token_info.role)
        return submission_pb2.GetServiceStatusResponse(
            status=service_status.availability.status,
            description=service_status.availability.description,
        )
