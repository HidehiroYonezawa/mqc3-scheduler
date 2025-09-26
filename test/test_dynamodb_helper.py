"""Tests for the dynamodb helper."""

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.append(Path(__file__).parents[1].as_posix())

from common import construct_sample_settings, create_dynamodb_client, create_dynamodb_table
from job_manager import dynamodb_helper
from job_manager.job_metadata import JobMetadata, JobStatus
from moto import mock_aws


def construct_sample_dynamodb_item(job_id: str, status: JobStatus = JobStatus.UNSPECIFIED) -> dict[str, Any]:
    settings = construct_sample_settings()
    token = "token1"  # noqa: S105
    role = "guest"
    save_job = True
    job_metadata = JobMetadata(
        job_id=job_id,
        max_elapsed_s=10,
        sdk_version="0.0.0",
        token=token,
        role=role,
        requested_backend=settings.backend,
        n_shots=settings.n_shots,
        save_job=save_job,
        status=status,
    )
    return job_metadata.to_dynamodb_item()


@mock_aws
def test_check_dynamodb_table_exists():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"

    # Check if the table exists before creating the client
    assert not dynamodb_helper.check_table_exists(dynamodb_client=dynamodb_client, table_name=table_name)

    create_dynamodb_table(table_name)
    # Check if the table exists after creating the client
    assert dynamodb_helper.check_table_exists(dynamodb_client=dynamodb_client, table_name=table_name)

    # Check if the table exists with an invalid table name
    assert not dynamodb_helper.check_table_exists(dynamodb_client=dynamodb_client, table_name="invalid table name")


@mock_aws
def test_put_item():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"

    create_dynamodb_table(table_name)

    job_id = "job id"
    item = construct_sample_dynamodb_item(job_id=job_id)

    assert not dynamodb_helper.check_item_exists(dynamodb_client=dynamodb_client, table_name=table_name, job_id=job_id)

    dynamodb_helper.put_item(dynamodb_client=dynamodb_client, table_name=table_name, dynamodb_item=item)

    assert dynamodb_helper.check_item_exists(dynamodb_client=dynamodb_client, table_name=table_name, job_id=job_id)

    with pytest.raises(ValueError, match=f"An item with the job ID {job_id} already exists in the database."):
        dynamodb_helper.put_item(dynamodb_client=dynamodb_client, table_name=table_name, dynamodb_item=item)


@mock_aws
def test_get_item():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"
    create_dynamodb_table(table_name)

    job_id = "job id"
    item = construct_sample_dynamodb_item(job_id=job_id)

    dynamodb_helper.put_item(dynamodb_client=dynamodb_client, table_name=table_name, dynamodb_item=item)

    assert dynamodb_helper.get_item(dynamodb_client=dynamodb_client, table_name=table_name, job_id=job_id) == item

    invalid_job_id = "invalid job id"
    with pytest.raises(ValueError, match=f"The item with job ID {invalid_job_id} does not exist in the database."):
        dynamodb_helper.get_item(dynamodb_client=dynamodb_client, table_name=table_name, job_id=invalid_job_id)


@mock_aws
def test_get_items_by_status():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"
    create_dynamodb_table(table_name)

    num_queued = 10
    num_running = 5

    # Add `QUEUED` items
    for i in range(num_queued):
        item = construct_sample_dynamodb_item(job_id=f"job{i}", status=JobStatus.QUEUED)
        dynamodb_helper.put_item(dynamodb_client, table_name, item)

    # Add `RUNNING` items
    for i in range(num_running):
        item = construct_sample_dynamodb_item(job_id=f"job{num_queued + i}", status=JobStatus.RUNNING)
        dynamodb_helper.put_item(dynamodb_client, table_name, item)

    # Retrieve `QUEUED` items
    result_queued = dynamodb_helper.get_items_by_status(
        dynamodb_client=dynamodb_client, table_name=table_name, status=JobStatus.QUEUED.name
    )
    assert len(result_queued) == num_queued
    assert all(item["status"]["S"] == "QUEUED" for item in result_queued)

    # Retrieve `RUNNING` items
    result_running = dynamodb_helper.get_items_by_status(
        dynamodb_client=dynamodb_client, table_name=table_name, status=JobStatus.RUNNING.name
    )
    assert len(result_running) == num_running
    assert all(item["status"]["S"] == "RUNNING" for item in result_running)

    assert dynamodb_helper.get_items_by_status(dynamodb_client, table_name, JobStatus.UNSPECIFIED.name) == []
    assert dynamodb_helper.get_items_by_status(dynamodb_client, table_name, JobStatus.TIMEOUT.name) == []
    assert dynamodb_helper.get_items_by_status(dynamodb_client, table_name, JobStatus.FAILED.name) == []
    assert dynamodb_helper.get_items_by_status(dynamodb_client, table_name, JobStatus.COMPLETED.name) == []
    assert dynamodb_helper.get_items_by_status(dynamodb_client, table_name, JobStatus.CANCELLED.name) == []


@mock_aws
def test_get_items_by_large_datasets():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"
    create_dynamodb_table(table_name)

    num_items = 2000
    for i in range(num_items):
        item = construct_sample_dynamodb_item(job_id=f"job{i}", status=JobStatus.COMPLETED)
        dynamodb_helper.put_item(dynamodb_client, table_name, item)

    result = dynamodb_helper.get_items_by_status(
        dynamodb_client=dynamodb_client, table_name=table_name, status=JobStatus.COMPLETED.name
    )

    assert len(result) == num_items
    assert all(item["status"]["S"] == "COMPLETED" for item in result)


@mock_aws
def test_update_item():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"
    create_dynamodb_table(table_name)

    job_id = "job id"
    item = construct_sample_dynamodb_item(job_id=job_id)

    dynamodb_helper.put_item(dynamodb_client=dynamodb_client, table_name=table_name, dynamodb_item=item)

    dynamodb_helper.update_item(
        dynamodb_client=dynamodb_client,
        table_name=table_name,
        job_id=job_id,
        update_values={"status": JobStatus.COMPLETED.name, "physical_lab_version": "1.0.0"},
    )

    updated_item = dynamodb_helper.get_item(dynamodb_client=dynamodb_client, table_name=table_name, job_id=job_id)

    assert updated_item["physical_lab_version"] == {"S": "1.0.0"}
    assert updated_item["status"] == {"S": "COMPLETED"}

    invalid_job_id = "nonexistent job id"
    with pytest.raises(ValueError, match=f"The item with job ID {invalid_job_id} does not exist in the database."):
        dynamodb_helper.update_item(
            dynamodb_client=dynamodb_client,
            table_name=table_name,
            job_id=invalid_job_id,
            update_values={"physical_lab_version": "1.0.0"},
        )


@mock_aws
def test_change_items_status():
    dynamodb_client = create_dynamodb_client()
    table_name = "table name"
    create_dynamodb_table(table_name)

    queued_item = construct_sample_dynamodb_item(job_id="queued_job", status=JobStatus.QUEUED)
    running_item1 = construct_sample_dynamodb_item(job_id="running_job1", status=JobStatus.RUNNING)
    running_item2 = construct_sample_dynamodb_item(job_id="running_job2", status=JobStatus.RUNNING)
    failed_item = construct_sample_dynamodb_item(job_id="failed_job", status=JobStatus.FAILED)
    completed_item = construct_sample_dynamodb_item(job_id="completed_job", status=JobStatus.COMPLETED)

    dynamodb_helper.put_item(dynamodb_client, table_name, queued_item)
    dynamodb_helper.put_item(dynamodb_client, table_name, running_item1)
    dynamodb_helper.put_item(dynamodb_client, table_name, running_item2)
    dynamodb_helper.put_item(dynamodb_client, table_name, failed_item)
    dynamodb_helper.put_item(dynamodb_client, table_name, completed_item)

    # Update `RUNNING` items to `FAILED`
    dynamodb_helper.change_items_status(
        dynamodb_client=dynamodb_client,
        table_name=table_name,
        old_status=JobStatus.RUNNING,
        new_status=JobStatus.FAILED,
    )

    assert dynamodb_helper.get_item(dynamodb_client, table_name, "queued_job")["status"] == {"S": "QUEUED"}
    assert dynamodb_helper.get_item(dynamodb_client, table_name, "running_job1")["status"] == {"S": "FAILED"}
    assert dynamodb_helper.get_item(dynamodb_client, table_name, "running_job2")["status"] == {"S": "FAILED"}
    assert dynamodb_helper.get_item(dynamodb_client, table_name, "failed_job")["status"] == {"S": "FAILED"}
    assert dynamodb_helper.get_item(dynamodb_client, table_name, "completed_job")["status"] == {"S": "COMPLETED"}
