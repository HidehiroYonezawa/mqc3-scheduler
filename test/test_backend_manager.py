"""Tests for BackendManager."""

import sys
from pathlib import Path

import pytest

sys.path.append(Path(__file__).parents[1].as_posix())


import boto3
from backend_manager.backend_manager import BackendManager
from common import SAMPLE_AWS_CREDENTIALS
from moto import mock_aws
from pb.mqc3_cloud.scheduler.v1 import submission_pb2
from pytest_mock import MockerFixture


def set_ssm_parameter(name: str, value: str) -> None:
    ssm_client = boto3.client("ssm", region_name=SAMPLE_AWS_CREDENTIALS.region_name)
    ssm_client.put_parameter(
        Name=name,
        Value=value,
        Type="String",
        Overwrite=True,
    )


@mock_aws
def test_backend_manager_constructor_with_status_parameter():
    """Test successful construction of BackendManager with the status parameter."""
    status_parameter_name = "/test/status.toml"
    initial_status_toml = """
[backends.qpu.admin]
status = "available"
description = "ready"
"""
    set_ssm_parameter(
        name=status_parameter_name,
        value=initial_status_toml,
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)
    status_toml = manager._get_status_toml()  # noqa: SLF001
    assert status_toml == initial_status_toml


@mock_aws
def test_backend_manager_constructor_fails_on_validate_status():
    """Test that a RuntimeError is raised when validating the status parameter fails."""
    status_parameter_name = "/test/status.toml"
    invalid_toml = "not = [valid] = toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value=invalid_toml,
    )
    with pytest.raises(RuntimeError, match=r"Failed to validate the status parameter."):
        BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)


@mock_aws
def test_load_status_fails_on_get_status(mocker: MockerFixture):
    """Test that loading status fails when `_get_status_toml` fails."""
    status_parameter_name = "/test/status.toml"
    initial_status_toml = """
[backends.qpu.admin]
status = "available"
description = "ready"
"""
    set_ssm_parameter(
        name=status_parameter_name,
        value=initial_status_toml,
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)

    mocker.patch.object(
        BackendManager,
        "_get_status_toml",
        return_value=None,
    )
    assert manager._load_backend_status() is None  # noqa: SLF001


@mock_aws
def test_load_status_fails_on_parse_toml():
    """Test that loading status fails when `_parse_toml` fails."""
    status_parameter_name = "/test/status.toml"
    # Firstly, set valid toml.
    initial_status_toml = """
[backends.qpu.admin]
status = "available"
description = "ready"
"""
    set_ssm_parameter(
        name=status_parameter_name,
        value=initial_status_toml,
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)
    # Set an invalid TOML value
    invalid_toml = "not = [valid] = toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value=invalid_toml,
    )

    assert manager._load_backend_status() is None  # noqa: SLF001


@mock_aws
def test_backend_availability_success():
    """Test successful retrieval of backend status for a known backend and role."""
    status_parameter_name = "/test/status.toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value="""
[backends.qpu.admin]
status = "available"
description = "ready"
""",
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)
    result = manager.get_backend_availability("qpu", "admin")

    assert result.backend == "qpu"
    assert result.role == "admin"
    assert result.status == submission_pb2.ServiceStatus.SERVICE_STATUS_AVAILABLE
    assert result.description == "ready"


@mock_aws
def test_backend_role_missing():
    """Test that a ValueError is raised when the role is unknown in a known backend."""
    status_parameter_name = "/test/status.toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value="""
[backends.qpu.admin]
status = "available"
description = "ready"
""",
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)

    with pytest.raises(ValueError, match="Unknown role"):
        manager.get_backend_availability("qpu", "guest")


@mock_aws
def test_backend_missing():
    """Test that a ValueError is raised when the backend is unknown."""
    status_parameter_name = "/test/status.toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value="""
[backends.qpu.admin]
status = "available"
description = "ready"
""",
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)

    with pytest.raises(ValueError, match="Unknown backend"):
        manager.get_backend_availability("emulator", "admin")


@mock_aws
@pytest.mark.parametrize(
    ("toml_content", "expected_backends"),
    [
        (
            """
    [backends.qpu.admin]
    status = "available"

    [backends.qpu.developer]
    status = "available"

    [backends.qpu.guest]
    status = "unavailable"

    [backends.emulator]
    status = "maintenance"
    """,
            {"qpu", "emulator"},
        ),
        (
            """
    [backends.emulator]
    status = "available"
    """,
            {"emulator"},
        ),
        ("[valid]", set()),
    ],
)
def test_get_all_backends(toml_content: str, expected_backends: set[str]):
    """Test successful retrieval of all backend names from the status file."""
    status_parameter_name = "/test/status.toml"
    set_ssm_parameter(
        name=status_parameter_name,
        value=toml_content,
    )

    manager = BackendManager(status_parameter_name=status_parameter_name, aws_credentials=SAMPLE_AWS_CREDENTIALS)

    assert manager.get_all_backends() == expected_backends
