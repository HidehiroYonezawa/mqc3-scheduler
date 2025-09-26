"""get token information from database."""

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import grpc
from pb.mqc3_cloud.token_database.v1 import token_database_pb2, token_database_pb2_grpc

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information."""

    role: str
    name: str
    expires_at: datetime | None

    def is_expired(self, dt: datetime) -> bool:
        """Check if the token is expired.

        Returns:
            bool: True if the token is expired
        """
        return self.expires_at is not None and self.expires_at < dt


class TokenDatabaseError(Exception):
    """Unknown error from token database."""


def get_token_info(address_to_token_database: str, token: str) -> TokenInfo | None:
    """Get token information from token database.

    Args:
        address_to_token_database (str): address to token database
        token (str): user token

    Raises:
        TokenDatabaseError: token database returns unknown status or error

    Returns:
        TokenInfo | None: token information or None if not found
    """
    try:
        with grpc.insecure_channel(address_to_token_database) as channel:
            stub = token_database_pb2_grpc.TokenDatabaseServiceStub(channel)
            logger.info("Getting token info from token database (token: %s).", token)
            response: token_database_pb2.GetTokenInfoResponse = stub.GetTokenInfo(
                token_database_pb2.GetTokenInfoRequest(token=token),
            )
    except Exception as e:
        msg = f"Failed to get token info (token: {token})."
        logger.exception(msg)
        raise TokenDatabaseError(msg) from e

    if response.status == token_database_pb2.DatabaseOperationStatus.DATABASE_OPERATION_STATUS_OK:
        return TokenInfo(
            role=response.token_info.role,
            name=response.token_info.name,
            expires_at=(
                response.token_info.expires_at.ToDatetime(ZoneInfo("Asia/Tokyo"))
                if response.token_info.expires_at.seconds > 0
                else None
            ),
        )
    if response.status == token_database_pb2.DatabaseOperationStatus.DATABASE_OPERATION_STATUS_NOT_FOUND:
        return None
    if response.status == token_database_pb2.DatabaseOperationStatus.DATABASE_OPERATION_STATUS_UNSPECIFIED:
        msg = f"Token database returned an unexpected status (token: {token}, message: {response.detail})."
        logger.error(msg)
        raise TokenDatabaseError(msg)

    msg = (
        f"Token database returned an unknown status "
        f"(token: {token}, status: {response.status}, message: {response.detail})."
    )
    logger.error(msg)
    raise TokenDatabaseError(msg)
