from mqc3_cloud.common.v1 import function_pb2 as _function_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GraphFF(_message.Message):
    __slots__ = ("function", "from_macronode", "to_macronode", "from_bd", "to_parameter")
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    FROM_MACRONODE_FIELD_NUMBER: _ClassVar[int]
    TO_MACRONODE_FIELD_NUMBER: _ClassVar[int]
    FROM_BD_FIELD_NUMBER: _ClassVar[int]
    TO_PARAMETER_FIELD_NUMBER: _ClassVar[int]
    function: int
    from_macronode: int
    to_macronode: int
    from_bd: int
    to_parameter: int
    def __init__(self, function: _Optional[int] = ..., from_macronode: _Optional[int] = ..., to_macronode: _Optional[int] = ..., from_bd: _Optional[int] = ..., to_parameter: _Optional[int] = ...) -> None: ...

class GraphRepresentation(_message.Message):
    __slots__ = ("n_local_macronodes", "n_steps", "operations", "nlffs", "functions", "name")
    N_LOCAL_MACRONODES_FIELD_NUMBER: _ClassVar[int]
    N_STEPS_FIELD_NUMBER: _ClassVar[int]
    OPERATIONS_FIELD_NUMBER: _ClassVar[int]
    NLFFS_FIELD_NUMBER: _ClassVar[int]
    FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    n_local_macronodes: int
    n_steps: int
    operations: _containers.RepeatedCompositeFieldContainer[GraphOperation]
    nlffs: _containers.RepeatedCompositeFieldContainer[GraphFF]
    functions: _containers.RepeatedCompositeFieldContainer[_function_pb2.PythonFunction]
    name: str
    def __init__(self, n_local_macronodes: _Optional[int] = ..., n_steps: _Optional[int] = ..., operations: _Optional[_Iterable[_Union[GraphOperation, _Mapping]]] = ..., nlffs: _Optional[_Iterable[_Union[GraphFF, _Mapping]]] = ..., functions: _Optional[_Iterable[_Union[_function_pb2.PythonFunction, _Mapping]]] = ..., name: _Optional[str] = ...) -> None: ...

class GraphOperation(_message.Message):
    __slots__ = ("type", "initialized_modes", "displacement_k_minus_1", "displacement_k_minus_n", "macronode", "swap", "parameters", "readout")
    class OperationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OPERATION_TYPE_UNSPECIFIED: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_MEASUREMENT: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_INITIALIZATION: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_PHASE_ROTATION: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_SHEAR_X_INVARIANT: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_SHEAR_P_INVARIANT: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_SQUEEZING: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_SQUEEZING_45: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_ARBITRARY_FIRST: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_ARBITRARY_SECOND: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_CONTROLLED_Z: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_BEAM_SPLITTER: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_TWO_MODE_SHEAR: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_MANUAL: _ClassVar[GraphOperation.OperationType]
        OPERATION_TYPE_WIRING: _ClassVar[GraphOperation.OperationType]
    OPERATION_TYPE_UNSPECIFIED: GraphOperation.OperationType
    OPERATION_TYPE_MEASUREMENT: GraphOperation.OperationType
    OPERATION_TYPE_INITIALIZATION: GraphOperation.OperationType
    OPERATION_TYPE_PHASE_ROTATION: GraphOperation.OperationType
    OPERATION_TYPE_SHEAR_X_INVARIANT: GraphOperation.OperationType
    OPERATION_TYPE_SHEAR_P_INVARIANT: GraphOperation.OperationType
    OPERATION_TYPE_SQUEEZING: GraphOperation.OperationType
    OPERATION_TYPE_SQUEEZING_45: GraphOperation.OperationType
    OPERATION_TYPE_ARBITRARY_FIRST: GraphOperation.OperationType
    OPERATION_TYPE_ARBITRARY_SECOND: GraphOperation.OperationType
    OPERATION_TYPE_CONTROLLED_Z: GraphOperation.OperationType
    OPERATION_TYPE_BEAM_SPLITTER: GraphOperation.OperationType
    OPERATION_TYPE_TWO_MODE_SHEAR: GraphOperation.OperationType
    OPERATION_TYPE_MANUAL: GraphOperation.OperationType
    OPERATION_TYPE_WIRING: GraphOperation.OperationType
    class Displacement(_message.Message):
        __slots__ = ("x", "p")
        X_FIELD_NUMBER: _ClassVar[int]
        P_FIELD_NUMBER: _ClassVar[int]
        x: float
        p: float
        def __init__(self, x: _Optional[float] = ..., p: _Optional[float] = ...) -> None: ...
    TYPE_FIELD_NUMBER: _ClassVar[int]
    INITIALIZED_MODES_FIELD_NUMBER: _ClassVar[int]
    DISPLACEMENT_K_MINUS_1_FIELD_NUMBER: _ClassVar[int]
    DISPLACEMENT_K_MINUS_N_FIELD_NUMBER: _ClassVar[int]
    MACRONODE_FIELD_NUMBER: _ClassVar[int]
    SWAP_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    READOUT_FIELD_NUMBER: _ClassVar[int]
    type: GraphOperation.OperationType
    initialized_modes: _containers.RepeatedScalarFieldContainer[int]
    displacement_k_minus_1: GraphOperation.Displacement
    displacement_k_minus_n: GraphOperation.Displacement
    macronode: int
    swap: bool
    parameters: _containers.RepeatedScalarFieldContainer[float]
    readout: bool
    def __init__(self, type: _Optional[_Union[GraphOperation.OperationType, str]] = ..., initialized_modes: _Optional[_Iterable[int]] = ..., displacement_k_minus_1: _Optional[_Union[GraphOperation.Displacement, _Mapping]] = ..., displacement_k_minus_n: _Optional[_Union[GraphOperation.Displacement, _Mapping]] = ..., macronode: _Optional[int] = ..., swap: bool = ..., parameters: _Optional[_Iterable[float]] = ..., readout: bool = ...) -> None: ...

class GraphResult(_message.Message):
    __slots__ = ("n_local_macronodes", "measured_vals")
    class MacronodeMeasuredValue(_message.Message):
        __slots__ = ("index", "m_b", "m_d")
        INDEX_FIELD_NUMBER: _ClassVar[int]
        M_B_FIELD_NUMBER: _ClassVar[int]
        M_D_FIELD_NUMBER: _ClassVar[int]
        index: int
        m_b: float
        m_d: float
        def __init__(self, index: _Optional[int] = ..., m_b: _Optional[float] = ..., m_d: _Optional[float] = ...) -> None: ...
    class ShotMeasuredValue(_message.Message):
        __slots__ = ("measured_vals",)
        MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
        measured_vals: _containers.RepeatedCompositeFieldContainer[GraphResult.MacronodeMeasuredValue]
        def __init__(self, measured_vals: _Optional[_Iterable[_Union[GraphResult.MacronodeMeasuredValue, _Mapping]]] = ...) -> None: ...
    N_LOCAL_MACRONODES_FIELD_NUMBER: _ClassVar[int]
    MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
    n_local_macronodes: int
    measured_vals: _containers.RepeatedCompositeFieldContainer[GraphResult.ShotMeasuredValue]
    def __init__(self, n_local_macronodes: _Optional[int] = ..., measured_vals: _Optional[_Iterable[_Union[GraphResult.ShotMeasuredValue, _Mapping]]] = ...) -> None: ...
