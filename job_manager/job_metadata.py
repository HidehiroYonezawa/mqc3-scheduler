"""Job metadata module."""

from dataclasses import Field, dataclass, field, fields
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Self, get_args

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from google.protobuf import timestamp_pb2
from pb.mqc3_cloud.scheduler.v1 import job_pb2
from utility import (
    convert_datetime_to_timestamp,
    convert_timestamp_to_datetime,
    get_current_timestamp,
    get_relative_timestamp,
)

JOB_EXPIRY_DAYS = 30


class JobStatus(Enum):
    """Job status enum."""

    UNSPECIFIED = job_pb2.JOB_STATUS_UNSPECIFIED
    QUEUED = job_pb2.JOB_STATUS_QUEUED
    RUNNING = job_pb2.JOB_STATUS_RUNNING
    COMPLETED = job_pb2.JOB_STATUS_COMPLETED
    FAILED = job_pb2.JOB_STATUS_FAILED
    CANCELLED = job_pb2.JOB_STATUS_CANCELLED
    TIMEOUT = job_pb2.JOB_STATUS_TIMEOUT


class StateSavePolicy(Enum):
    """State save policy enum."""

    UNSPECIFIED = job_pb2.JOB_STATE_SAVE_POLICY_UNSPECIFIED
    ALL = job_pb2.JOB_STATE_SAVE_POLICY_ALL
    FIRST_ONLY = job_pb2.JOB_STATE_SAVE_POLICY_FIRST_ONLY
    NONE = job_pb2.JOB_STATE_SAVE_POLICY_NONE


class DynamoDBTypeSerializer(TypeSerializer):
    """DynamoDB type serializer."""

    def serialize(self, value: object) -> dict[str, Any]:
        """Convert the value to a DynamoDB attribute value.

        Args:
           value: The value to convert to a DynamoDB attribute value.

        Returns:
            The DynamoDB attribute value.
        """
        if isinstance(value, JobStatus):
            return {"S": value.name}
        if isinstance(value, StateSavePolicy):
            return {"S": value.name}
        if isinstance(value, datetime):
            return {"S": value.isoformat()}
        if isinstance(value, timestamp_pb2.Timestamp):
            dt = convert_timestamp_to_datetime(value)
            return self.serialize(dt)
        if isinstance(value, float):
            decimal_f = Decimal(value)
            return self.serialize(decimal_f)
        return super().serialize(value)


@dataclass
class JobMetadata:
    """Job metadata class."""

    job_id: str
    sdk_version: str

    # Token information
    token: str
    role: str

    # Execution settings
    requested_backend: str
    n_shots: int
    max_elapsed_s: int

    # Job management options
    save_job: bool

    # Simulation settings
    state_save_policy: StateSavePolicy = field(default=StateSavePolicy.UNSPECIFIED)
    resource_squeezing_level: float = field(default=0.0)

    status: JobStatus = field(default=JobStatus.UNSPECIFIED)
    status_code: str = field(default="")
    status_message: str = field(default="")

    # Execution result
    actual_backend_name: str | None = field(default=None)
    raw_size_bytes: int | None = field(default=None)
    encoded_size_bytes: int | None = field(default=None)

    # Execution version
    quantum_computer_version: str | None = field(default=None)
    physical_lab_version: str | None = field(default=None)
    scheduler_version: str | None = field(default=None)
    simulator_version: str | None = field(default=None)

    # Timestamps
    submitted_at: timestamp_pb2.Timestamp | None = field(default=None)
    queued_at: timestamp_pb2.Timestamp | None = field(default=None)
    dequeued_at: timestamp_pb2.Timestamp | None = field(default=None)
    compile_started_at: timestamp_pb2.Timestamp | None = field(default=None)
    compile_finished_at: timestamp_pb2.Timestamp | None = field(default=None)
    execution_started_at: timestamp_pb2.Timestamp | None = field(default=None)
    execution_finished_at: timestamp_pb2.Timestamp | None = field(default=None)
    finished_at: timestamp_pb2.Timestamp | None = field(default=None)
    job_expiry: timestamp_pb2.Timestamp | None = field(default=None)

    def __post_init__(self) -> None:
        """Initialize the job metadata."""
        if self.submitted_at is None:
            self.submitted_at = get_current_timestamp()
        if self.job_expiry is None:
            self.job_expiry = get_relative_timestamp(timedelta(days=JOB_EXPIRY_DAYS))

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert the job metadata to a dictionary compatible with DynamoDB Item format.

        Returns:
            dict[str, dict[str, Any]]: Dictionary with DynamoDB attribute types.
        """
        result = {}
        dynamodb_serializer = DynamoDBTypeSerializer()
        for class_field in fields(self):
            field_name = class_field.name
            field_value = getattr(self, field_name)
            result[field_name] = dynamodb_serializer.serialize(value=field_value)
        return result

    def get_proto_execution_version(self) -> job_pb2.JobExecutionVersion:
        """Get the execution version as a proto message.

        Returns:
            job_pb2.JobExecutionVersion: Execution version as a proto message.
        """
        return job_pb2.JobExecutionVersion(
            physical_lab_version=self.physical_lab_version,
            scheduler_version=self.scheduler_version,
            simulator_version=self.simulator_version,
        )

    def get_proto_job_timestamps(self) -> job_pb2.JobTimestamps:
        """Get the job timestamps as a proto message.

        Returns:
            job_pb2.JobTimestamps: Job timestamps as a proto message.
        """
        return job_pb2.JobTimestamps(
            submitted_at=self.submitted_at,
            queued_at=self.queued_at,
            dequeued_at=self.dequeued_at,
            compile_started_at=self.compile_started_at,
            compile_finished_at=self.compile_finished_at,
            execution_started_at=self.execution_started_at,
            execution_finished_at=self.execution_finished_at,
            finished_at=self.finished_at,
        )

    @classmethod
    def from_dynamodb_item(cls, dynamodb_item: dict[str, dict[str, Any]]) -> Self:
        """Construct a job metadata object from a DynamoDB item created by the `to_dynamodb_item` method.

        Args:
            dynamodb_item: DynamoDB item created by the `to_dynamodb_item` method of a job metadata instance.

        Raises:
            ValueError: If the input item misses a required field.
            TypeError: If the input item has an invalid structure.

        Returns:
            JobMetadata: Job metadata object.
        """
        converted_data = {}
        for class_field in fields(cls):
            field_name = class_field.name

            if field_name not in dynamodb_item:
                msg = f"Missing field in DynamoDB item: {field_name}"
                raise ValueError(msg)

            attribute_value = dynamodb_item[field_name]
            if not isinstance(attribute_value, dict):
                msg = f"Invalid DynamoDB item structure for field {field_name}."
                raise TypeError(msg)

            converted_data[field_name] = JobMetadata.__get_field_value(
                attribute_value=attribute_value, target_field=class_field
            )

        return cls(**converted_data)

    @classmethod
    def __get_field_value(
        cls, attribute_value: dict[str, Any], target_field: Field
    ) -> str | int | float | bool | JobStatus | StateSavePolicy | datetime | timestamp_pb2.Timestamp | None:
        dynamodb_deserializer = TypeDeserializer()
        dynamodb_value = dynamodb_deserializer.deserialize(value=attribute_value)
        if dynamodb_value is None:
            return None

        field_type = target_field.type
        if field_type is JobStatus:
            field_value = JobStatus[dynamodb_value]
        elif field_type is StateSavePolicy:
            field_value = StateSavePolicy[dynamodb_value]
        elif datetime in get_args(field_type):
            field_value = datetime.fromisoformat(dynamodb_value)
        elif timestamp_pb2.Timestamp in get_args(field_type):
            dt = datetime.fromisoformat(dynamodb_value)
            field_value = convert_datetime_to_timestamp(dt)
        elif field_type in {bool, str} or {bool, str} & set(get_args(field_type)):
            field_value = dynamodb_value
        elif field_type is int or int in get_args(field_type):
            field_value = int(dynamodb_value)
        elif field_type is float or float in get_args(field_type):
            field_value = float(dynamodb_value)
        else:
            msg = f"Unsupported type for field {target_field.name}: {field_type}"
            raise ValueError(msg)

        return field_value
