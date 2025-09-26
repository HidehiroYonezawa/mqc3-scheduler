from google.api import annotations_pb2 as _annotations_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DatabaseOperationStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATABASE_OPERATION_STATUS_UNSPECIFIED: _ClassVar[DatabaseOperationStatus]
    DATABASE_OPERATION_STATUS_OK: _ClassVar[DatabaseOperationStatus]
    DATABASE_OPERATION_STATUS_NOT_FOUND: _ClassVar[DatabaseOperationStatus]
DATABASE_OPERATION_STATUS_UNSPECIFIED: DatabaseOperationStatus
DATABASE_OPERATION_STATUS_OK: DatabaseOperationStatus
DATABASE_OPERATION_STATUS_NOT_FOUND: DatabaseOperationStatus

class CreateTokenRequest(_message.Message):
    __slots__ = ("name", "role", "expires_at")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    name: str
    role: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, name: _Optional[str] = ..., role: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateTokenResponse(_message.Message):
    __slots__ = ("status", "detail", "token_info")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_INFO_FIELD_NUMBER: _ClassVar[int]
    status: DatabaseOperationStatus
    detail: str
    token_info: TokenInfo
    def __init__(self, status: _Optional[_Union[DatabaseOperationStatus, str]] = ..., detail: _Optional[str] = ..., token_info: _Optional[_Union[TokenInfo, _Mapping]] = ...) -> None: ...

class GetTokenInfoRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class GetTokenInfoResponse(_message.Message):
    __slots__ = ("status", "detail", "token_info")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_INFO_FIELD_NUMBER: _ClassVar[int]
    status: DatabaseOperationStatus
    detail: str
    token_info: TokenInfo
    def __init__(self, status: _Optional[_Union[DatabaseOperationStatus, str]] = ..., detail: _Optional[str] = ..., token_info: _Optional[_Union[TokenInfo, _Mapping]] = ...) -> None: ...

class DeleteTokenRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class DeleteTokenResponse(_message.Message):
    __slots__ = ("status", "detail")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    status: DatabaseOperationStatus
    detail: str
    def __init__(self, status: _Optional[_Union[DatabaseOperationStatus, str]] = ..., detail: _Optional[str] = ...) -> None: ...

class RenewTokenRequest(_message.Message):
    __slots__ = ("token", "role", "expires_at")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    token: str
    role: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, token: _Optional[str] = ..., role: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RenewTokenResponse(_message.Message):
    __slots__ = ("status", "detail", "token_info")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_INFO_FIELD_NUMBER: _ClassVar[int]
    status: DatabaseOperationStatus
    detail: str
    token_info: TokenInfo
    def __init__(self, status: _Optional[_Union[DatabaseOperationStatus, str]] = ..., detail: _Optional[str] = ..., token_info: _Optional[_Union[TokenInfo, _Mapping]] = ...) -> None: ...

class TokenInfo(_message.Message):
    __slots__ = ("token", "name", "role", "created_at", "expires_at")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    token: str
    name: str
    role: str
    created_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, token: _Optional[str] = ..., name: _Optional[str] = ..., role: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetTokenInfoListResponse(_message.Message):
    __slots__ = ("status", "detail", "token_list")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    TOKEN_LIST_FIELD_NUMBER: _ClassVar[int]
    status: DatabaseOperationStatus
    detail: str
    token_list: _containers.RepeatedCompositeFieldContainer[TokenInfo]
    def __init__(self, status: _Optional[_Union[DatabaseOperationStatus, str]] = ..., detail: _Optional[str] = ..., token_list: _Optional[_Iterable[_Union[TokenInfo, _Mapping]]] = ...) -> None: ...
