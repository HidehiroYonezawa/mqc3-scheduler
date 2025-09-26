"""Backend availability management for a scheduler using AWS SSM Parameter Store.

This module defines the `BackendManager` class for managing and querying backend
availability data stored in AWS SSM Parameter Store. The status is maintained as
a TOML-formatted parameter in the store.
"""

import logging
import tomllib
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.client import ClientError
from pb.mqc3_cloud.scheduler.v1 import submission_pb2
from utility import AWSCredentials

logger = logging.getLogger(__name__)


@dataclass
class BackendAvailability:
    """Represents the availability state of a backend for a specific user role."""

    backend: str
    role: str

    status: submission_pb2.ServiceStatus
    description: str


class BackendManager:
    """Manages backend availability by reading and syncing a TOML-formatted parameter in AWS SSM Parameter Store.

    Provides methods to fetch availability by backend and role, and supports
    synchronization with AWS SSM Parameter Store for durability.
    """

    @staticmethod
    def _parse_toml(toml_str: str) -> dict[str, Any]:
        return tomllib.loads(toml_str)

    @staticmethod
    def _to_service_status(status: str) -> submission_pb2.ServiceStatus:
        if status == "available":
            return submission_pb2.ServiceStatus.SERVICE_STATUS_AVAILABLE
        if status == "maintenance":
            return submission_pb2.ServiceStatus.SERVICE_STATUS_MAINTENANCE
        if status == "unavailable":
            return submission_pb2.ServiceStatus.SERVICE_STATUS_UNAVAILABLE

        logger.error("Invalid status string '%s'. Falling back to 'unavailable'.", status)
        return submission_pb2.ServiceStatus.SERVICE_STATUS_UNAVAILABLE

    def __init__(
        self,
        status_parameter_name: str,
        aws_credentials: AWSCredentials,
        *,
        unify_backends: bool = False,
    ) -> None:
        """Initialize the backend manager.

        Args:
            status_parameter_name (str): Name of the parameter in AWS SSM Parameter Store.
            aws_credentials (AWSCredentials): AWS credentials for accessing the SSM Parameter Store.
            unify_backends (bool): Whether to merge the backends from the status parameter with `all`.

        Raises:
            RuntimeError: If failed to initialize the status parameter.
        """
        self.status_parameter_name = status_parameter_name
        self.ssm_client = boto3.client(
            "ssm",
            region_name=aws_credentials.region_name,
            endpoint_url=aws_credentials.endpoint_url,
            aws_access_key_id=aws_credentials.access_key_id,
            aws_secret_access_key=aws_credentials.secret_access_key,
        )
        self.unify_backends = unify_backends

        # Validate the status parameter.
        status_toml = self._get_status_toml()
        if status_toml is None:
            msg = "Failed to retrieve the status parameter."
            raise RuntimeError(msg)
        try:
            self._parse_toml(toml_str=status_toml)
        except Exception as e:
            msg = "Failed to validate the status parameter."
            raise RuntimeError(msg) from e

    def _get_status_toml(self) -> str | None:
        """Read the backend status parameter from the parameter store.

        Returns:
            str | None: A string representing the backend status in TOML, or None
                if the parameter does not exist.

        Raises:
            ClientError: Any AWS client error other than `ParameterNotFound`.

        """
        try:
            logger.info("Retrieving the backend status parameter from SSM (key: %s).", self.status_parameter_name)
            response = self.ssm_client.get_parameter(Name=self.status_parameter_name, WithDecryption=True)
            return response["Parameter"]["Value"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                return None
            raise

    def _load_backend_status(self) -> dict[str, Any] | None:
        """Retrieve the backend status from AWS SSM Parameter Store.

        Returns:
            dict[str, Any] | None: The backend status as a dictionary, or None if an error occurs.
        """
        try:
            status_toml = self._get_status_toml()
            if status_toml is None:
                return None
            return self._parse_toml(status_toml)
        except Exception:
            logger.exception("Failed to load the backend status.")
            return None

    def get_backend_availability(self, backend: str, role: str) -> BackendAvailability:
        """Retrieve availability status for the specified backend and user role.

        Args:
            backend (str): The backend name (e.g. 'qpu', 'emulator').
            role (str): The user role (e.g. 'admin', 'developer', 'guest').

        Returns:
            BackendAvailability: Availability status and description.

        Raises:
            ValueError: If the backend or role is not found.
        """
        backend_status = self._load_backend_status()
        if backend_status is None:
            return BackendAvailability(
                backend=backend,
                role=role,
                status=self._to_service_status("unavailable"),
                description="Failed to load the backend status.",
            )

        if "backends" not in backend_status:
            # This block should never be reached under normal conditions.
            # If it is reached, the parameter store data is likely corrupted or malformed
            # due to a bug in the system that updates it.
            logger.error("Missing 'backends' section in the status parameter '%s'.", self.status_parameter_name)
            return BackendAvailability(
                backend=backend,
                role=role,
                status=self._to_service_status("unavailable"),
                description="Status data is corrupted or invalid.",
            )

        backend_infos = backend_status["backends"]
        if self.unify_backends:
            backend = "all"

        if backend not in backend_infos:
            msg = f"Unknown backend: '{backend}'."
            raise ValueError(msg)
        if role not in backend_infos[backend]:
            msg = f"Unknown role: '{role}' in backend '{backend}'."
            raise ValueError(msg)

        try:
            backend_info = backend_infos[backend][role]
            return BackendAvailability(
                backend=backend,
                role=role,
                status=BackendManager._to_service_status(backend_info["status"]),
                description=backend_info["description"],
            )
        except Exception:
            # This block should never be reached under normal conditions.
            # If it is reached, the parameter store data is likely corrupted or malformed
            # due to a bug in the system that updates it.
            logger.exception("Malformed status entry (backend: %s, role: %s).", backend, role)
            return BackendAvailability(
                backend=backend,
                role=role,
                status=self._to_service_status("unavailable"),
                description="Status data is corrupted or invalid.",
            )

    def get_all_backends(self) -> set[str]:
        """Return a set of all backend names defined in the parameter store.

        Returns:
            set[str]: Set of all backend names (e.g. 'qpu', 'emulator').
        """
        backend_status = self._load_backend_status()
        if backend_status is None:
            return set()

        if "backends" not in backend_status:
            # This block should never be reached under normal conditions.
            # If it is reached, the parameter store data is likely corrupted or malformed
            # due to a bug in the system that updates it.
            logger.error("Missing 'backends' section in the status parameter '%s'.", self.status_parameter_name)
            return set()

        return set(backend_status["backends"].keys())
