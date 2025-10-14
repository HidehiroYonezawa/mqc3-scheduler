"""Server module for the scheduler."""

import argparse
import logging
import os
import threading
from concurrent import futures
from copy import deepcopy

import boto3
import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from backend_manager.backend_manager import BackendManager
from job_manager.job_manager import JobManager
from job_manager.job_repository import JobRepository
from pb.mqc3_cloud.scheduler.v1 import execution_pb2, execution_pb2_grpc, submission_pb2, submission_pb2_grpc
from server_execution import ExecutionServer
from server_submission import SubmissionServer
from utility import AWSCredentials

# Logging configuration
log_format = "%(asctime)s - %(levelname)-8s - %(message)s - %(filename)s:%(lineno)d"
logging.basicConfig(level=logging.INFO, format=log_format)

logger = logging.getLogger(__name__)

SCHEDULER_SUBMISSION_MAX_WORKERS = int(os.getenv("SCHEDULER_SUBMISSION_MAX_WORKERS", "100"))
SCHEDULER_EXECUTION_MAX_WORKERS = int(os.getenv("SCHEDULER_EXECUTION_MAX_WORKERS", "10"))
SCHEDULER_SUBMISSION_MAX_MESSAGE_LENGTH = int(
    os.getenv("SCHEDULER_SUBMISSION_MAX_MESSAGE_LENGTH", str(10 * 1024 * 1024))  # 10 MB
)
SCHEDULER_EXECUTION_MAX_MESSAGE_LENGTH = int(
    os.getenv("SCHEDULER_EXECUTION_MAX_MESSAGE_LENGTH", str(10 * 1024 * 1024))  # 10 MB
)
SCHEDULER_MAX_QUEUE_BYTES = int(os.getenv("SCHEDULER_MAX_QUEUE_BYTES", str(100 * 1024 * 1024)))  # 100MB
SCHEDULER_MAX_CONCURRENT_JOBS_ADMIN = int(os.getenv("SCHEDULER_MAX_CONCURRENT_JOBS_ADMIN", "1000"))
SCHEDULER_MAX_CONCURRENT_JOBS_DEVELOPER = int(os.getenv("SCHEDULER_MAX_CONCURRENT_JOBS_DEVELOPER", "10"))
SCHEDULER_MAX_CONCURRENT_JOBS_GUEST = int(os.getenv("SCHEDULER_MAX_CONCURRENT_JOBS_GUEST", "5"))
SCHEDULER_MAX_JOB_BYTES_ADMIN = int(os.getenv("SCHEDULER_MAX_JOB_BYTES_ADMIN", str(10 * 1024 * 1024)))  # 10MB
SCHEDULER_MAX_JOB_BYTES_DEVELOPER = int(os.getenv("SCHEDULER_MAX_JOB_BYTES_DEVELOPER", str(10 * 1024 * 1024)))  # 10MB
SCHEDULER_MAX_JOB_BYTES_GUEST = int(os.getenv("SCHEDULER_MAX_JOB_BYTES_GUEST", str(1024 * 1024)))  # 1MB


def get_ssm_parameter(name: str, aws_credentials: AWSCredentials) -> str:
    """Get SSM parameter value.

    Args:
        name (str): The name of the SSM parameter.
        aws_credentials (AWSCredentials): AWS credentials.

    Returns:
        str: The value of the SSM parameter.

    Raises:
        ValueError: If the parameter is not found in SSM.
        RuntimeError: If there is a failure retrieving the SSM parameter.
    """
    logger.debug("Getting SSM parameter (name: %s, credentials: %s).", name, aws_credentials)

    ssm_client = boto3.client(
        "ssm",
        endpoint_url=aws_credentials.endpoint_url,
        aws_access_key_id=aws_credentials.access_key_id,
        aws_secret_access_key=aws_credentials.secret_access_key,
        region_name=aws_credentials.region_name,
    )

    try:
        response = ssm_client.get_parameter(
            Name=name,
            WithDecryption=True,
        )
    except ssm_client.exceptions.ParameterNotFound as e:
        msg = f"Parameter '{name}' not found in SSM."
        logger.exception(msg)
        raise ValueError(msg) from e
    except Exception as e:
        msg = f"Failed to get SSM parameter '{name}'."
        logger.exception(msg)
        raise RuntimeError(msg) from e

    logger.debug("Successfully retrieved SSM parameter (name: %s, value: %s).", name, response["Parameter"]["Value"])
    return response["Parameter"]["Value"]


# Server startup function
def serve(args: argparse.Namespace) -> None:  # noqa: PLR0915, PLR0914
    """Start server and wait for termination.

    Args:
        args (argparse.Namespace): Arguments parsed by argparse

    Raises:
        ValueError: If required arguments are missing or invalid
    """
    aws_credentials = AWSCredentials(
        endpoint_url=args.endpoint if args.dev else None,
        access_key_id=args.aws_access_key_id,
        secret_access_key=args.aws_secret_access_key,
        region_name=args.region,
    )
    if aws_credentials.endpoint_url:
        logger.debug("Using AWS endpoint '%s'.", aws_credentials.endpoint_url)

    # Check if required arguments are provided
    if not args.job_bucket_name_key:
        msg = "Job bucket name key is not provided."
        logger.error(msg)
        raise ValueError(msg)
    if not args.job_table_name_key:
        msg = "DynamoDB table name key is not provided."
        logger.error(msg)
        raise ValueError(msg)

    # Get job_bucket_name from SSM parameter store
    job_bucket_name = get_ssm_parameter(args.job_bucket_name_key, aws_credentials)

    if not job_bucket_name:
        msg = "Job bucket name is empty."
        logger.error(msg)
        raise ValueError(msg)

    s3_aws_credentials = deepcopy(aws_credentials)
    if args.dev and args.s3_endpoint:
        s3_aws_credentials.endpoint_url = args.s3_endpoint
    if s3_aws_credentials.endpoint_url:
        logger.debug("Using S3 endpoint URL '%s'.", s3_aws_credentials.endpoint_url)

    job_repository = JobRepository(bucket_name=job_bucket_name, aws_credentials=s3_aws_credentials)
    # Check the connection to S3.
    if not job_repository.bucket_exists():
        logger.error("S3 bucket does not exist (bucket name: %s).", job_bucket_name)

    server_submission_option = [
        ("grpc.max_send_message_length", SCHEDULER_SUBMISSION_MAX_MESSAGE_LENGTH),
        ("grpc.max_receive_message_length", SCHEDULER_SUBMISSION_MAX_MESSAGE_LENGTH),
    ]
    server_execution_option = [
        ("grpc.max_send_message_length", SCHEDULER_EXECUTION_MAX_MESSAGE_LENGTH),
        ("grpc.max_receive_message_length", SCHEDULER_EXECUTION_MAX_MESSAGE_LENGTH),
    ]

    server_submission = grpc.server(
        futures.ThreadPoolExecutor(SCHEDULER_SUBMISSION_MAX_WORKERS),
        options=server_submission_option,
    )
    server_execution = grpc.server(
        futures.ThreadPoolExecutor(SCHEDULER_EXECUTION_MAX_WORKERS),
        options=server_execution_option,
    )

    logger.info("Load the backend status from SSM (key: %s).", args.backend_status_parameter_name)
    backend_manager = BackendManager(
        status_parameter_name=args.backend_status_parameter_name,
        aws_credentials=aws_credentials,
        unify_backends=args.unify_backends,
    )
    backend_manager_lock = threading.RLock()

    logger.info("Get a DynamoDB job table name from SSM (key: %s).", args.job_table_name_key)
    dynamodb_table_name = get_ssm_parameter(args.job_table_name_key, aws_credentials)

    job_manager = JobManager(
        queue_capacity_bytes=SCHEDULER_MAX_QUEUE_BYTES,
        max_concurrent_jobs_per_token={
            "admin": SCHEDULER_MAX_CONCURRENT_JOBS_ADMIN,
            "developer": SCHEDULER_MAX_CONCURRENT_JOBS_DEVELOPER,
            "guest": SCHEDULER_MAX_CONCURRENT_JOBS_GUEST,
        },
        job_repository=job_repository,
        aws_credentials=aws_credentials,
        dynamodb_table_name=dynamodb_table_name,
        supported_backends=backend_manager.get_all_backends(),
        unify_backends=args.unify_backends,
    )
    job_manager_lock = threading.RLock()

    submission_pb2_grpc.add_SubmissionServiceServicer_to_server(
        servicer=SubmissionServer(
            address_to_token_database=args.address_to_token_database,
            backend_manager=backend_manager,
            backend_manager_lock=backend_manager_lock,
            job_manager=job_manager,
            job_manager_lock=job_manager_lock,
            max_job_bytes={
                "admin": SCHEDULER_MAX_JOB_BYTES_ADMIN,
                "developer": SCHEDULER_MAX_JOB_BYTES_DEVELOPER,
                "guest": SCHEDULER_MAX_JOB_BYTES_GUEST,
            },
        ),
        server=server_submission,
    )
    execution_pb2_grpc.add_ExecutionServiceServicer_to_server(
        servicer=ExecutionServer(
            job_manager=job_manager,
            job_manager_lock=job_manager_lock,
        ),
        server=server_execution,
    )

    health_pb2_grpc.add_HealthServicer_to_server(
        servicer=health.HealthServicer(
            experimental_non_blocking=True,
            experimental_thread_pool=futures.ThreadPoolExecutor(1),
        ),
        server=server_submission,
    )
    service_names_submission = (
        submission_pb2.DESCRIPTOR.services_by_name["SubmissionService"].full_name,
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names_submission, server_submission)

    health_pb2_grpc.add_HealthServicer_to_server(
        servicer=health.HealthServicer(
            experimental_non_blocking=True,
            experimental_thread_pool=futures.ThreadPoolExecutor(1),
        ),
        server=server_execution,
    )
    service_names_execution = (
        execution_pb2.DESCRIPTOR.services_by_name["ExecutionService"].full_name,
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names_execution, server_execution)

    # Start servers
    server_submission.add_insecure_port(args.port_for_submission)
    server_execution.add_insecure_port(args.port_for_execution)

    server_submission.start()
    logger.info("Submission server started on port %s.", args.port_for_submission)

    server_execution.start()
    logger.info("Execution server started on port %s.", args.port_for_execution)

    server_submission.wait_for_termination()
    server_execution.wait_for_termination()


def get_arg_parser() -> argparse.ArgumentParser:
    """Construct argument parser.

    Returns:
        argparse.ArgumentParser: parser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--port-for-submission", default="[::]:8082")
    parser.add_argument("--port-for-execution", default="[::]:8081")
    parser.add_argument("-t", "-at", "--address_to_token_database", default="token_database:8084")
    parser.add_argument("-k", "--aws_access_key_id", default=None)
    parser.add_argument("-s", "--aws_secret_access_key", default=None)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", ""))
    parser.add_argument("--job_bucket_name_key", default=os.getenv("JOB_BUCKET_NAME_KEY", ""))
    parser.add_argument("--job_table_name_key", default=os.getenv("DYNAMODB_JOB_TABLE_NAME_KEY", ""))
    parser.add_argument("--backend_status_parameter_name", default=os.getenv("BACKEND_STATUS_PARAMETER_NAME", ""))
    parser.add_argument("--unify_backends", action="store_true")
    parser.add_argument("--dev", action="store_true", help="Run in development mode")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="AWS endpoint for development. This option is only effective with the --dev flag.",
    )
    parser.add_argument(
        "--s3_endpoint",
        default=None,
        help=(
            "S3 endpoint for development. "
            "This option is only effective with the --dev flag and overrides the value of endpoint."
        ),
    )
    return parser


if __name__ == "__main__":
    parser = get_arg_parser()
    args = parser.parse_args()
    if not args.dev and (args.endpoint or args.s3_endpoint):
        parser.error("--endpoint/--s3_endpoint can only be used with --dev")

    serve(args)
