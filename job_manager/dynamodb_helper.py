"""DynamoDB helper module."""

import logging
import os
from typing import Any

from botocore.exceptions import ClientError
from mypy_boto3_dynamodb import DynamoDBClient

from .job_metadata import DynamoDBTypeSerializer, JobStatus

logger = logging.getLogger(__name__)

DYNAMODB_JOB_TABLE_GSI_NAME = os.getenv("DYNAMODB_JOB_TABLE_GSI_NAME", "status-index")


def check_table_exists(dynamodb_client: DynamoDBClient, table_name: str) -> bool:
    """Check if a DynamoDB table exists.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.

    Returns:
        bool: True if the table exists, False otherwise.

    Raises:
        ClientError: If an error occurs during checking the table existence.
    """
    try:
        logger.info("Checking if DynamoDB table exists (table name: %s).", table_name)
        dynamodb_client.describe_table(TableName=table_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        logger.exception("Failed to check if DynamoDB table '%s' exists.", table_name)
        raise
    else:
        return True


def put_item(dynamodb_client: DynamoDBClient, table_name: str, dynamodb_item: dict[str, dict[str, Any]]) -> None:
    """Add an item to a DynamoDB table.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        dynamodb_item (dict[str, dict[str, Any]]): Dictionary representing the DynamoDB item to be added.

    Raises:
        ClientError: If the item cannot be added to the table.
        ValueError: If the item with the same job ID already exists in the table.
    """
    try:
        logger.info("Adding an item to the database.")
        dynamodb_client.put_item(
            TableName=table_name, Item=dynamodb_item, ConditionExpression="attribute_not_exists(job_id)"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            msg = f"An item with the job ID {dynamodb_item['job_id']['S']} already exists in the database."
            logger.exception(msg)
            raise ValueError(msg) from e
        logger.exception("Failed to add an item to the database.")
        raise


def get_item(dynamodb_client: DynamoDBClient, table_name: str, job_id: str) -> dict[str, Any]:
    """Retrieve an item from the DynamoDB table by the job ID.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        job_id (str): The job ID of the item to retrieve.

    Returns:
        dict[str, Any]: The retrieved DynamoDB item as a dictionary.

    Raises:
        ValueError: If the item with the specified job_id does not exist
        ClientError: If an error occurs while retrieving the item.
    """
    try:
        logger.info("Retrieving an item from the database (job ID: %s).", job_id)
        response = dynamodb_client.get_item(
            TableName=table_name,
            Key={"job_id": {"S": job_id}},
        )
        if "Item" not in response:
            msg = f"The item with job ID {job_id} does not exist in the database."
            logger.error(msg)
            raise ValueError(msg)
        return response["Item"]
    except ClientError:
        logger.exception("Failed to retrieve an item from the database (job ID: %s).", job_id)
        raise


def get_items_by_status(
    dynamodb_client: DynamoDBClient, table_name: str, status: str
) -> list[dict[str, dict[str, Any]]]:
    """Retrieve all items with the specified status from the DynamoDB table.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        status (str): Status name to filter items.

    Returns:
        list[dict[str, dict[str, Any]]]: List of DynamoDB items with the specified status.

    Raises:
        ClientError: If an error occurs during the query operation.
    """
    result_items = []
    try:
        logger.info("Retrieving items with status '%s' from the database.", status)
        response = dynamodb_client.query(
            TableName=table_name,
            IndexName=DYNAMODB_JOB_TABLE_GSI_NAME,
            KeyConditionExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": status}},
        )
        result_items.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            logger.info(
                "Retrieving additional items with status '%s' from the database (current items: %d).",
                status,
                len(result_items),
            )
            response = dynamodb_client.query(
                TableName=table_name,
                IndexName=DYNAMODB_JOB_TABLE_GSI_NAME,
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": {"S": status}},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            result_items.extend(response.get("Items", []))

    except ClientError:
        logger.exception("Failed to retrieve items with status '%s' from the database.", status)
        raise

    return result_items


def update_item(dynamodb_client: DynamoDBClient, table_name: str, job_id: str, update_values: dict) -> None:
    """Update values of an item in the DynamoDB table.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        job_id (str): The job ID of the item to update.
        update_values (dict): Dictionary of attribute names to values to be updated.

    Raises:
        ClientError: If updating the item fails.
        ValueError: If the item with the given job ID does not exist in the table.
    """
    try:
        update_expression = "SET " + ", ".join(f"#{key} = :{key}" for key in update_values)
        expression_attribute_names = {f"#{key}": key for key in update_values}
        expression_attribute_values = {
            f":{key}": DynamoDBTypeSerializer().serialize(value) for key, value in update_values.items()
        }

        logger.info("Updating an item in the database (job ID: %s).", job_id)
        dynamodb_client.update_item(
            TableName=table_name,
            Key={"job_id": {"S": job_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ConditionExpression="attribute_exists(job_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            msg = f"The item with job ID {job_id} does not exist in the database."
            logger.exception(msg)
            raise ValueError(msg) from e
        logger.exception("Failed to update an item in the database (job ID: %s).", job_id)
        raise


def change_items_status(
    dynamodb_client: DynamoDBClient, table_name: str, old_status: JobStatus, new_status: JobStatus
) -> None:
    """Update all items with the specified old status to the specified new status in the DynamoDB table.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        old_status (JobStatus): Status name to filter items for update.
        new_status (JobStatus): New status to set for the items.

    Raises:
        ClientError: If an error occurs during the update operations.
    """
    try:
        items = get_items_by_status(dynamodb_client, table_name, old_status.name)
        for item in items:
            try:
                job_id = item["job_id"]["S"]
                update_expression = "SET #status = :new_status"
                condition_expression = "#status = :old_status"
                expression_attribute_names = {"#status": "status"}
                expression_attribute_values = {
                    ":new_status": {"S": new_status.name},
                    ":old_status": {"S": old_status.name},
                }
                logger.info(
                    "Updating the item status from '%s' to '%s' (job ID: %s).",
                    old_status.name,
                    new_status.name,
                    job_id,
                )
                dynamodb_client.update_item(
                    TableName=table_name,
                    Key={"job_id": {"S": job_id}},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                    ConditionExpression=condition_expression,
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    logger.warning("Skipping update because the item status has been changed (job ID: %s).", job_id)
                    continue
                logger.exception(
                    "Failed to update item %s from status %s to %s.", job_id, old_status.name, new_status.name
                )
                raise
    except ClientError:
        logger.exception("Failed to update items from status '%s' to '%s'.", old_status.name, new_status.name)
        raise


def check_item_exists(
    dynamodb_client: DynamoDBClient, table_name: str, job_id: str, *, consistent_read: bool = False
) -> bool:
    """Check if an item with the specified job_id exists in the DynamoDB table.

    Args:
        dynamodb_client (DynamoDBClient): DynamoDB client.
        table_name (str): DynamoDB table name.
        job_id (str): The job ID of the item to check.
        consistent_read (bool): Determines the read consistency model.
            If set to True, a strongly consistent read is performed,
            which returns the most recent data but consumes double the read capacity units.
            If set to False, an eventually consistent read is performed.
            The results might not reflect a recently completed write.

    Returns:
        bool: True if the item exists, False otherwise

    Raises:
        ClientError: If the query operation fails
    """
    try:
        logger.info("Checking if an item exists in the database (job ID: %s).", job_id)
        response = dynamodb_client.query(
            TableName=table_name,
            KeyConditionExpression="job_id = :job_id",
            ExpressionAttributeValues={":job_id": {"S": job_id}},
            Select="COUNT",
            Limit=1,
            ConsistentRead=consistent_read,
        )
        return response["Count"] > 0
    except ClientError:
        logger.exception("Failed to check if an item exists in the database (job ID: %s).", job_id)
        raise
