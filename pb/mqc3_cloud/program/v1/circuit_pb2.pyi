from mqc3_cloud.common.v1 import function_pb2 as _function_pb2
from mqc3_cloud.common.v1 import math_pb2 as _math_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CircuitFF(_message.Message):
    __slots__ = ("function", "from_operation", "to_operation", "to_parameter")
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    FROM_OPERATION_FIELD_NUMBER: _ClassVar[int]
    TO_OPERATION_FIELD_NUMBER: _ClassVar[int]
    TO_PARAMETER_FIELD_NUMBER: _ClassVar[int]
    function: int
    from_operation: int
    to_operation: int
    to_parameter: int
    def __init__(self, function: _Optional[int] = ..., from_operation: _Optional[int] = ..., to_operation: _Optional[int] = ..., to_parameter: _Optional[int] = ...) -> None: ...

class CircuitRepresentation(_message.Message):
    __slots__ = ("n_modes", "initial_states", "operations", "nlffs", "functions", "name")
    N_MODES_FIELD_NUMBER: _ClassVar[int]
    INITIAL_STATES_FIELD_NUMBER: _ClassVar[int]
    OPERATIONS_FIELD_NUMBER: _ClassVar[int]
    NLFFS_FIELD_NUMBER: _ClassVar[int]
    FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    n_modes: int
    initial_states: _containers.RepeatedCompositeFieldContainer[InitialState]
    operations: _containers.RepeatedCompositeFieldContainer[CircuitOperation]
    nlffs: _containers.RepeatedCompositeFieldContainer[CircuitFF]
    functions: _containers.RepeatedCompositeFieldContainer[_function_pb2.PythonFunction]
    name: str
    def __init__(self, n_modes: _Optional[int] = ..., initial_states: _Optional[_Iterable[_Union[InitialState, _Mapping]]] = ..., operations: _Optional[_Iterable[_Union[CircuitOperation, _Mapping]]] = ..., nlffs: _Optional[_Iterable[_Union[CircuitFF, _Mapping]]] = ..., functions: _Optional[_Iterable[_Union[_function_pb2.PythonFunction, _Mapping]]] = ..., name: _Optional[str] = ...) -> None: ...

class GaussianState(_message.Message):
    __slots__ = ("mean", "cov")
    MEAN_FIELD_NUMBER: _ClassVar[int]
    COV_FIELD_NUMBER: _ClassVar[int]
    mean: _containers.RepeatedCompositeFieldContainer[_math_pb2.Complex]
    cov: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, mean: _Optional[_Iterable[_Union[_math_pb2.Complex, _Mapping]]] = ..., cov: _Optional[_Iterable[float]] = ...) -> None: ...

class BosonicState(_message.Message):
    __slots__ = ("gaussian_states", "coeffs")
    GAUSSIAN_STATES_FIELD_NUMBER: _ClassVar[int]
    COEFFS_FIELD_NUMBER: _ClassVar[int]
    gaussian_states: _containers.RepeatedCompositeFieldContainer[GaussianState]
    coeffs: _containers.RepeatedCompositeFieldContainer[_math_pb2.Complex]
    def __init__(self, gaussian_states: _Optional[_Iterable[_Union[GaussianState, _Mapping]]] = ..., coeffs: _Optional[_Iterable[_Union[_math_pb2.Complex, _Mapping]]] = ...) -> None: ...

class HardwareConstrainedSqueezedState(_message.Message):
    __slots__ = ("theta",)
    THETA_FIELD_NUMBER: _ClassVar[int]
    theta: float
    def __init__(self, theta: _Optional[float] = ...) -> None: ...

class InitialState(_message.Message):
    __slots__ = ("squeezed", "bosonic")
    SQUEEZED_FIELD_NUMBER: _ClassVar[int]
    BOSONIC_FIELD_NUMBER: _ClassVar[int]
    squeezed: HardwareConstrainedSqueezedState
    bosonic: BosonicState
    def __init__(self, squeezed: _Optional[_Union[HardwareConstrainedSqueezedState, _Mapping]] = ..., bosonic: _Optional[_Union[BosonicState, _Mapping]] = ...) -> None: ...

class GuiMetadataCircuitOperation(_message.Message):
    __slots__ = ("slot",)
    SLOT_FIELD_NUMBER: _ClassVar[int]
    slot: int
    def __init__(self, slot: _Optional[int] = ...) -> None: ...

class CircuitOperation(_message.Message):
    __slots__ = ("type", "modes", "parameters", "gui_metadata")
    class OperationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OPERATION_TYPE_UNSPECIFIED: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_MEASUREMENT: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_DISPLACEMENT: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_PHASE_ROTATION: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_SHEAR_X_INVARIANT: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_SHEAR_P_INVARIANT: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_SQUEEZING: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_SQUEEZING_45: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_ARBITRARY: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_CONTROLLED_Z: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_BEAM_SPLITTER: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_TWO_MODE_SHEAR: _ClassVar[CircuitOperation.OperationType]
        OPERATION_TYPE_MANUAL: _ClassVar[CircuitOperation.OperationType]
    OPERATION_TYPE_UNSPECIFIED: CircuitOperation.OperationType
    OPERATION_TYPE_MEASUREMENT: CircuitOperation.OperationType
    OPERATION_TYPE_DISPLACEMENT: CircuitOperation.OperationType
    OPERATION_TYPE_PHASE_ROTATION: CircuitOperation.OperationType
    OPERATION_TYPE_SHEAR_X_INVARIANT: CircuitOperation.OperationType
    OPERATION_TYPE_SHEAR_P_INVARIANT: CircuitOperation.OperationType
    OPERATION_TYPE_SQUEEZING: CircuitOperation.OperationType
    OPERATION_TYPE_SQUEEZING_45: CircuitOperation.OperationType
    OPERATION_TYPE_ARBITRARY: CircuitOperation.OperationType
    OPERATION_TYPE_CONTROLLED_Z: CircuitOperation.OperationType
    OPERATION_TYPE_BEAM_SPLITTER: CircuitOperation.OperationType
    OPERATION_TYPE_TWO_MODE_SHEAR: CircuitOperation.OperationType
    OPERATION_TYPE_MANUAL: CircuitOperation.OperationType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    MODES_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    GUI_METADATA_FIELD_NUMBER: _ClassVar[int]
    type: CircuitOperation.OperationType
    modes: _containers.RepeatedScalarFieldContainer[int]
    parameters: _containers.RepeatedScalarFieldContainer[float]
    gui_metadata: GuiMetadataCircuitOperation
    def __init__(self, type: _Optional[_Union[CircuitOperation.OperationType, str]] = ..., modes: _Optional[_Iterable[int]] = ..., parameters: _Optional[_Iterable[float]] = ..., gui_metadata: _Optional[_Union[GuiMetadataCircuitOperation, _Mapping]] = ...) -> None: ...

class CircuitResult(_message.Message):
    __slots__ = ("measured_vals",)
    class OperationMeasuredValue(_message.Message):
        __slots__ = ("index", "value")
        INDEX_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        index: int
        value: float
        def __init__(self, index: _Optional[int] = ..., value: _Optional[float] = ...) -> None: ...
    class ShotMeasuredValue(_message.Message):
        __slots__ = ("measured_vals",)
        MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
        measured_vals: _containers.RepeatedCompositeFieldContainer[CircuitResult.OperationMeasuredValue]
        def __init__(self, measured_vals: _Optional[_Iterable[_Union[CircuitResult.OperationMeasuredValue, _Mapping]]] = ...) -> None: ...
    MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
    measured_vals: _containers.RepeatedCompositeFieldContainer[CircuitResult.ShotMeasuredValue]
    def __init__(self, measured_vals: _Optional[_Iterable[_Union[CircuitResult.ShotMeasuredValue, _Mapping]]] = ...) -> None: ...
