from mqc3_cloud.common.v1 import error_detail_pb2 as _error_detail_pb2
from mqc3_cloud.scheduler.v1 import job_pb2 as _job_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServiceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SERVICE_STATUS_UNSPECIFIED: _ClassVar[ServiceStatus]
    SERVICE_STATUS_AVAILABLE: _ClassVar[ServiceStatus]
    SERVICE_STATUS_UNAVAILABLE: _ClassVar[ServiceStatus]
    SERVICE_STATUS_MAINTENANCE: _ClassVar[ServiceStatus]
SERVICE_STATUS_UNSPECIFIED: ServiceStatus
SERVICE_STATUS_AVAILABLE: ServiceStatus
SERVICE_STATUS_UNAVAILABLE: ServiceStatus
SERVICE_STATUS_MAINTENANCE: ServiceStatus

class SubmitJobRequest(_message.Message):
    __slots__ = ("token", "job", "options", "sdk_version")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    JOB_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    SDK_VERSION_FIELD_NUMBER: _ClassVar[int]
    token: str
    job: _job_pb2.Job
    options: _job_pb2.JobManagementOptions
    sdk_version: str
    def __init__(self, token: _Optional[str] = ..., job: _Optional[_Union[_job_pb2.Job, _Mapping]] = ..., options: _Optional[_Union[_job_pb2.JobManagementOptions, _Mapping]] = ..., sdk_version: _Optional[str] = ...) -> None: ...

class SubmitJobResponse(_message.Message):
    __slots__ = ("error", "job_id")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    job_id: str
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., job_id: _Optional[str] = ...) -> None: ...

class CancelJobRequest(_message.Message):
    __slots__ = ("token", "job_id")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    token: str
    job_id: str
    def __init__(self, token: _Optional[str] = ..., job_id: _Optional[str] = ...) -> None: ...

class CancelJobResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ...) -> None: ...

class GetJobStatusRequest(_message.Message):
    __slots__ = ("token", "job_id")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    token: str
    job_id: str
    def __init__(self, token: _Optional[str] = ..., job_id: _Optional[str] = ...) -> None: ...

class GetJobStatusResponse(_message.Message):
    __slots__ = ("error", "status", "status_detail", "execution_details")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_DETAIL_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_DETAILS_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    status: _job_pb2.JobStatus
    status_detail: str
    execution_details: _job_pb2.JobExecutionDetails
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., status: _Optional[_Union[_job_pb2.JobStatus, str]] = ..., status_detail: _Optional[str] = ..., execution_details: _Optional[_Union[_job_pb2.JobExecutionDetails, _Mapping]] = ...) -> None: ...

class GetJobResultRequest(_message.Message):
    __slots__ = ("token", "job_id")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    token: str
    job_id: str
    def __init__(self, token: _Optional[str] = ..., job_id: _Optional[str] = ...) -> None: ...

class GetJobResultResponse(_message.Message):
    __slots__ = ("error", "status", "status_detail", "execution_details", "result")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_DETAIL_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_DETAILS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    status: _job_pb2.JobStatus
    status_detail: str
    execution_details: _job_pb2.JobExecutionDetails
    result: _job_pb2.JobResult
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., status: _Optional[_Union[_job_pb2.JobStatus, str]] = ..., status_detail: _Optional[str] = ..., execution_details: _Optional[_Union[_job_pb2.JobExecutionDetails, _Mapping]] = ..., result: _Optional[_Union[_job_pb2.JobResult, _Mapping]] = ...) -> None: ...

class GetServiceStatusRequest(_message.Message):
    __slots__ = ("token", "backend")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    BACKEND_FIELD_NUMBER: _ClassVar[int]
    token: str
    backend: str
    def __init__(self, token: _Optional[str] = ..., backend: _Optional[str] = ...) -> None: ...

class GetServiceStatusResponse(_message.Message):
    __slots__ = ("error", "status", "description")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    status: ServiceStatus
    description: str
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., status: _Optional[_Union[ServiceStatus, str]] = ..., description: _Optional[str] = ...) -> None: ...
