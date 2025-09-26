"""Utility functions."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.protobuf import timestamp_pb2


@dataclass
class AWSCredentials:
    """AWS credentials."""

    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    region_name: str | None = None


def get_current_datetime() -> datetime:
    """Get the current datetime.

    Returns:
       datetime: The current datetime.
    """
    return datetime.now(ZoneInfo("Asia/Tokyo"))


def get_current_timestamp() -> timestamp_pb2.Timestamp:
    """Get the current timestamp.

    Returns:
       timestamp_pb2.Timestamp: The current timestamp.
    """
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(datetime.now(ZoneInfo("Asia/Tokyo")))
    return timestamp


def get_relative_timestamp(dt: timedelta) -> timestamp_pb2.Timestamp:
    """Get a timestamp relative to the current time.

    Args:
        dt (timedelta): The timedelta from now.

    Returns:
        timestamp_pb2.Timestamp: The timestamp from now.
    """
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(datetime.now(ZoneInfo("Asia/Tokyo")) + dt)
    return timestamp


def convert_timestamp_to_datetime(timestamp: timestamp_pb2.Timestamp) -> datetime:
    """Convert a timestamp to a datetime.

    Args:
        timestamp (timestamp_pb2.Timestamp): The timestamp to convert.

    Returns:
       datetime: The converted datetime.
    """
    return timestamp.ToDatetime(tzinfo=ZoneInfo("Asia/Tokyo"))


def convert_datetime_to_timestamp(dt: datetime) -> timestamp_pb2.Timestamp:
    """Convert a datetime to a timestamp.

    Args:
       dt (datetime): The datetime to convert.

    Returns:
       timestamp_pb2.Timestamp: The converted timestamp.
    """
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt)
    return timestamp
