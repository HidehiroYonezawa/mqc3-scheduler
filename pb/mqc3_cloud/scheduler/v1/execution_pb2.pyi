from mqc3_cloud.common.v1 import error_detail_pb2 as _error_detail_pb2
from mqc3_cloud.scheduler.v1 import job_pb2 as _job_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ExecutionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EXECUTION_STATUS_UNSPECIFIED: _ClassVar[ExecutionStatus]
    EXECUTION_STATUS_SUCCESS: _ClassVar[ExecutionStatus]
    EXECUTION_STATUS_FAILURE: _ClassVar[ExecutionStatus]
    EXECUTION_STATUS_TIMEOUT: _ClassVar[ExecutionStatus]
EXECUTION_STATUS_UNSPECIFIED: ExecutionStatus
EXECUTION_STATUS_SUCCESS: ExecutionStatus
EXECUTION_STATUS_FAILURE: ExecutionStatus
EXECUTION_STATUS_TIMEOUT: ExecutionStatus

class ExecutionVersion(_message.Message):
    __slots__ = ("quantum_computer", "physical_lab", "simulator")
    QUANTUM_COMPUTER_FIELD_NUMBER: _ClassVar[int]
    PHYSICAL_LAB_FIELD_NUMBER: _ClassVar[int]
    SIMULATOR_FIELD_NUMBER: _ClassVar[int]
    quantum_computer: str
    physical_lab: str
    simulator: str
    def __init__(self, quantum_computer: _Optional[str] = ..., physical_lab: _Optional[str] = ..., simulator: _Optional[str] = ...) -> None: ...

class AssignNextJobRequest(_message.Message):
    __slots__ = ("backend",)
    BACKEND_FIELD_NUMBER: _ClassVar[int]
    backend: str
    def __init__(self, backend: _Optional[str] = ...) -> None: ...

class AssignNextJobResponse(_message.Message):
    __slots__ = ("error", "job_id", "job", "upload_target")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    JOB_FIELD_NUMBER: _ClassVar[int]
    UPLOAD_TARGET_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    job_id: str
    job: _job_pb2.Job
    upload_target: _job_pb2.JobResultUploadTarget
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., job_id: _Optional[str] = ..., job: _Optional[_Union[_job_pb2.Job, _Mapping]] = ..., upload_target: _Optional[_Union[_job_pb2.JobResultUploadTarget, _Mapping]] = ...) -> None: ...

class ReportExecutionResultRequest(_message.Message):
    __slots__ = ("job_id", "status", "error", "uploaded_result", "timestamps", "actual_backend", "version")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    UPLOADED_RESULT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMPS_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_BACKEND_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    status: ExecutionStatus
    error: _error_detail_pb2.ErrorDetail
    uploaded_result: _job_pb2.JobUploadedResult
    timestamps: _job_pb2.JobTimestamps
    actual_backend: str
    version: ExecutionVersion
    def __init__(self, job_id: _Optional[str] = ..., status: _Optional[_Union[ExecutionStatus, str]] = ..., error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., uploaded_result: _Optional[_Union[_job_pb2.JobUploadedResult, _Mapping]] = ..., timestamps: _Optional[_Union[_job_pb2.JobTimestamps, _Mapping]] = ..., actual_backend: _Optional[str] = ..., version: _Optional[_Union[ExecutionVersion, _Mapping]] = ...) -> None: ...

class ReportExecutionResultResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ...) -> None: ...

class RefreshUploadUrlRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class RefreshUploadUrlResponse(_message.Message):
    __slots__ = ("error", "upload_target")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    UPLOAD_TARGET_FIELD_NUMBER: _ClassVar[int]
    error: _error_detail_pb2.ErrorDetail
    upload_target: _job_pb2.JobResultUploadTarget
    def __init__(self, error: _Optional[_Union[_error_detail_pb2.ErrorDetail, _Mapping]] = ..., upload_target: _Optional[_Union[_job_pb2.JobResultUploadTarget, _Mapping]] = ...) -> None: ...
