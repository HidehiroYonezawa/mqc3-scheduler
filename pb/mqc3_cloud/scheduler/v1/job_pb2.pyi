from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from mqc3_cloud.program.v1 import quantum_program_pb2 as _quantum_program_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JobStateSavePolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATE_SAVE_POLICY_UNSPECIFIED: _ClassVar[JobStateSavePolicy]
    JOB_STATE_SAVE_POLICY_NONE: _ClassVar[JobStateSavePolicy]
    JOB_STATE_SAVE_POLICY_FIRST_ONLY: _ClassVar[JobStateSavePolicy]
    JOB_STATE_SAVE_POLICY_ALL: _ClassVar[JobStateSavePolicy]

class JobStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATUS_UNSPECIFIED: _ClassVar[JobStatus]
    JOB_STATUS_QUEUED: _ClassVar[JobStatus]
    JOB_STATUS_RUNNING: _ClassVar[JobStatus]
    JOB_STATUS_COMPLETED: _ClassVar[JobStatus]
    JOB_STATUS_FAILED: _ClassVar[JobStatus]
    JOB_STATUS_CANCELLED: _ClassVar[JobStatus]
    JOB_STATUS_TIMEOUT: _ClassVar[JobStatus]
JOB_STATE_SAVE_POLICY_UNSPECIFIED: JobStateSavePolicy
JOB_STATE_SAVE_POLICY_NONE: JobStateSavePolicy
JOB_STATE_SAVE_POLICY_FIRST_ONLY: JobStateSavePolicy
JOB_STATE_SAVE_POLICY_ALL: JobStateSavePolicy
JOB_STATUS_UNSPECIFIED: JobStatus
JOB_STATUS_QUEUED: JobStatus
JOB_STATUS_RUNNING: JobStatus
JOB_STATUS_COMPLETED: JobStatus
JOB_STATUS_FAILED: JobStatus
JOB_STATUS_CANCELLED: JobStatus
JOB_STATUS_TIMEOUT: JobStatus

class Job(_message.Message):
    __slots__ = ("program", "settings")
    PROGRAM_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    program: _quantum_program_pb2.QuantumProgram
    settings: JobExecutionSettings
    def __init__(self, program: _Optional[_Union[_quantum_program_pb2.QuantumProgram, _Mapping]] = ..., settings: _Optional[_Union[JobExecutionSettings, _Mapping]] = ...) -> None: ...

class JobManagementOptions(_message.Message):
    __slots__ = ("save_job",)
    SAVE_JOB_FIELD_NUMBER: _ClassVar[int]
    save_job: bool
    def __init__(self, save_job: bool = ...) -> None: ...

class JobTimestamps(_message.Message):
    __slots__ = ("submitted_at", "queued_at", "dequeued_at", "compile_started_at", "compile_finished_at", "execution_started_at", "execution_finished_at", "finished_at")
    SUBMITTED_AT_FIELD_NUMBER: _ClassVar[int]
    QUEUED_AT_FIELD_NUMBER: _ClassVar[int]
    DEQUEUED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPILE_STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPILE_FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    submitted_at: _timestamp_pb2.Timestamp
    queued_at: _timestamp_pb2.Timestamp
    dequeued_at: _timestamp_pb2.Timestamp
    compile_started_at: _timestamp_pb2.Timestamp
    compile_finished_at: _timestamp_pb2.Timestamp
    execution_started_at: _timestamp_pb2.Timestamp
    execution_finished_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    def __init__(self, submitted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., queued_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., dequeued_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., compile_started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., compile_finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., execution_started_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., execution_finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class JobExecutionSettings(_message.Message):
    __slots__ = ("backend", "n_shots", "timeout", "state_save_policy", "resource_squeezing_level", "role")
    BACKEND_FIELD_NUMBER: _ClassVar[int]
    N_SHOTS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    STATE_SAVE_POLICY_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_SQUEEZING_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    backend: str
    n_shots: int
    timeout: _duration_pb2.Duration
    state_save_policy: JobStateSavePolicy
    resource_squeezing_level: float
    role: str
    def __init__(self, backend: _Optional[str] = ..., n_shots: _Optional[int] = ..., timeout: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., state_save_policy: _Optional[_Union[JobStateSavePolicy, str]] = ..., resource_squeezing_level: _Optional[float] = ..., role: _Optional[str] = ...) -> None: ...

class JobExecutionVersion(_message.Message):
    __slots__ = ("scheduler_version", "physical_lab_version", "simulator_version")
    SCHEDULER_VERSION_FIELD_NUMBER: _ClassVar[int]
    PHYSICAL_LAB_VERSION_FIELD_NUMBER: _ClassVar[int]
    SIMULATOR_VERSION_FIELD_NUMBER: _ClassVar[int]
    scheduler_version: str
    physical_lab_version: str
    simulator_version: str
    def __init__(self, scheduler_version: _Optional[str] = ..., physical_lab_version: _Optional[str] = ..., simulator_version: _Optional[str] = ...) -> None: ...

class JobExecutionDetails(_message.Message):
    __slots__ = ("version", "timestamps")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMPS_FIELD_NUMBER: _ClassVar[int]
    version: JobExecutionVersion
    timestamps: JobTimestamps
    def __init__(self, version: _Optional[_Union[JobExecutionVersion, _Mapping]] = ..., timestamps: _Optional[_Union[JobTimestamps, _Mapping]] = ...) -> None: ...

class JobResultUploadTarget(_message.Message):
    __slots__ = ("upload_url", "expires_at")
    UPLOAD_URL_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    upload_url: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, upload_url: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class JobUploadedResult(_message.Message):
    __slots__ = ("raw_size_bytes", "encoded_size_bytes")
    RAW_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    ENCODED_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    raw_size_bytes: int
    encoded_size_bytes: int
    def __init__(self, raw_size_bytes: _Optional[int] = ..., encoded_size_bytes: _Optional[int] = ...) -> None: ...

class JobResult(_message.Message):
    __slots__ = ("result_url", "expires_at")
    RESULT_URL_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    result_url: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, result_url: _Optional[str] = ..., expires_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
