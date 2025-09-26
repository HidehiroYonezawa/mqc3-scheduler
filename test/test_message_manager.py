"""Tests for MessageManager."""

import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[1].as_posix())

from message_manager.message_manager import get_status_message


def test_get_status_message():
    requested_backend = "invalid_backend"
    reason = f"Unsupported backend requested: {requested_backend}."
    status_message = get_status_message(key="INVALID_REQUEST", reason=reason)
    assert status_message.code == "INVALID_ARGUMENT"
    assert status_message.message == f"Invalid request parameters: {reason}"

    reason = "Token is not found."
    status_message = get_status_message(key="INVALID_TOKEN", reason=reason)
    assert status_message.code == "UNAUTHENTICATED"
    assert status_message.message == f"Invalid token: {reason}"

    job_id = "job1"
    status_message = get_status_message(key="JOB_NOT_FOUND", job_id=job_id)
    assert status_message.code == "NOT_FOUND"
    assert status_message.message == f"Job not found (ID: {job_id})."

    status_message = get_status_message(key="RESOURCE_LIMIT_EXCEEDED")
    assert status_message.code == "RESOURCE_EXHAUSTED"
    assert status_message.message == "The job was not accepted due to current resource limits. Please try again later."

    status_message = get_status_message(key="INVALID_JOB_STATE")
    assert status_message.code == "FAILED_PRECONDITION"
    assert status_message.message == "The job can no longer be cancelled."

    status_message = get_status_message(key="INTERNAL_ERROR")
    assert status_message.code == "INTERNAL"
    assert status_message.message == "An internal error occurred. Please try again later."

    status_message = get_status_message(key="CRITICAL_ERROR")
    assert status_message.code == "INTERNAL"
    assert status_message.message == "An unexpected error occurred."

    status_message = get_status_message(key="SERVER_UNAVAILABLE")
    assert status_message.code == "UNAVAILABLE"
    assert status_message.message == "The server is currently unavailable. Please try again later."

    # Test with an invalid key
    status_message = get_status_message(key="INVALID_KEY")
    assert status_message.code == "UNKNOWN"
    assert status_message.message == "An unknown error occurred."
