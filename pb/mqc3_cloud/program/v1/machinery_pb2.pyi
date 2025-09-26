from mqc3_cloud.common.v1 import function_pb2 as _function_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FeedForwardCoefficientGenerationMethod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_UNSPECIFIED: _ClassVar[FeedForwardCoefficientGenerationMethod]
    FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_ZERO_FILLED: _ClassVar[FeedForwardCoefficientGenerationMethod]
    FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_FROM_HOMODYNE_ANGLES: _ClassVar[FeedForwardCoefficientGenerationMethod]
FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_UNSPECIFIED: FeedForwardCoefficientGenerationMethod
FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_ZERO_FILLED: FeedForwardCoefficientGenerationMethod
FEED_FORWARD_COEFFICIENT_GENERATION_METHOD_FROM_HOMODYNE_ANGLES: FeedForwardCoefficientGenerationMethod

class MachineryFF(_message.Message):
    __slots__ = ("function", "from_macronode", "from_abcd", "to_macronode", "to_parameter")
    FUNCTION_FIELD_NUMBER: _ClassVar[int]
    FROM_MACRONODE_FIELD_NUMBER: _ClassVar[int]
    FROM_ABCD_FIELD_NUMBER: _ClassVar[int]
    TO_MACRONODE_FIELD_NUMBER: _ClassVar[int]
    TO_PARAMETER_FIELD_NUMBER: _ClassVar[int]
    function: int
    from_macronode: int
    from_abcd: int
    to_macronode: int
    to_parameter: int
    def __init__(self, function: _Optional[int] = ..., from_macronode: _Optional[int] = ..., from_abcd: _Optional[int] = ..., to_macronode: _Optional[int] = ..., to_parameter: _Optional[int] = ...) -> None: ...

class MachineryRepresentation(_message.Message):
    __slots__ = ("n_local_macronodes", "n_steps", "homodyne_angles", "generating_method_for_ff_coeff_k_plus_1", "generating_method_for_ff_coeff_k_plus_n", "displacements_k_minus_1", "displacements_k_minus_n", "readout_macronodes_indices", "nlffs", "functions", "name")
    class MacronodeAngle(_message.Message):
        __slots__ = ("theta_a", "theta_b", "theta_c", "theta_d")
        THETA_A_FIELD_NUMBER: _ClassVar[int]
        THETA_B_FIELD_NUMBER: _ClassVar[int]
        THETA_C_FIELD_NUMBER: _ClassVar[int]
        THETA_D_FIELD_NUMBER: _ClassVar[int]
        theta_a: float
        theta_b: float
        theta_c: float
        theta_d: float
        def __init__(self, theta_a: _Optional[float] = ..., theta_b: _Optional[float] = ..., theta_c: _Optional[float] = ..., theta_d: _Optional[float] = ...) -> None: ...
    class DisplacementComplex(_message.Message):
        __slots__ = ("x", "p")
        X_FIELD_NUMBER: _ClassVar[int]
        P_FIELD_NUMBER: _ClassVar[int]
        x: float
        p: float
        def __init__(self, x: _Optional[float] = ..., p: _Optional[float] = ...) -> None: ...
    N_LOCAL_MACRONODES_FIELD_NUMBER: _ClassVar[int]
    N_STEPS_FIELD_NUMBER: _ClassVar[int]
    HOMODYNE_ANGLES_FIELD_NUMBER: _ClassVar[int]
    GENERATING_METHOD_FOR_FF_COEFF_K_PLUS_1_FIELD_NUMBER: _ClassVar[int]
    GENERATING_METHOD_FOR_FF_COEFF_K_PLUS_N_FIELD_NUMBER: _ClassVar[int]
    DISPLACEMENTS_K_MINUS_1_FIELD_NUMBER: _ClassVar[int]
    DISPLACEMENTS_K_MINUS_N_FIELD_NUMBER: _ClassVar[int]
    READOUT_MACRONODES_INDICES_FIELD_NUMBER: _ClassVar[int]
    NLFFS_FIELD_NUMBER: _ClassVar[int]
    FUNCTIONS_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    n_local_macronodes: int
    n_steps: int
    homodyne_angles: _containers.RepeatedCompositeFieldContainer[MachineryRepresentation.MacronodeAngle]
    generating_method_for_ff_coeff_k_plus_1: _containers.RepeatedScalarFieldContainer[FeedForwardCoefficientGenerationMethod]
    generating_method_for_ff_coeff_k_plus_n: _containers.RepeatedScalarFieldContainer[FeedForwardCoefficientGenerationMethod]
    displacements_k_minus_1: _containers.RepeatedCompositeFieldContainer[MachineryRepresentation.DisplacementComplex]
    displacements_k_minus_n: _containers.RepeatedCompositeFieldContainer[MachineryRepresentation.DisplacementComplex]
    readout_macronodes_indices: _containers.RepeatedScalarFieldContainer[int]
    nlffs: _containers.RepeatedCompositeFieldContainer[MachineryFF]
    functions: _containers.RepeatedCompositeFieldContainer[_function_pb2.PythonFunction]
    name: str
    def __init__(self, n_local_macronodes: _Optional[int] = ..., n_steps: _Optional[int] = ..., homodyne_angles: _Optional[_Iterable[_Union[MachineryRepresentation.MacronodeAngle, _Mapping]]] = ..., generating_method_for_ff_coeff_k_plus_1: _Optional[_Iterable[_Union[FeedForwardCoefficientGenerationMethod, str]]] = ..., generating_method_for_ff_coeff_k_plus_n: _Optional[_Iterable[_Union[FeedForwardCoefficientGenerationMethod, str]]] = ..., displacements_k_minus_1: _Optional[_Iterable[_Union[MachineryRepresentation.DisplacementComplex, _Mapping]]] = ..., displacements_k_minus_n: _Optional[_Iterable[_Union[MachineryRepresentation.DisplacementComplex, _Mapping]]] = ..., readout_macronodes_indices: _Optional[_Iterable[int]] = ..., nlffs: _Optional[_Iterable[_Union[MachineryFF, _Mapping]]] = ..., functions: _Optional[_Iterable[_Union[_function_pb2.PythonFunction, _Mapping]]] = ..., name: _Optional[str] = ...) -> None: ...

class MachineryResult(_message.Message):
    __slots__ = ("measured_vals",)
    class MacronodeMeasuredValue(_message.Message):
        __slots__ = ("m_a", "m_b", "m_c", "m_d", "index")
        M_A_FIELD_NUMBER: _ClassVar[int]
        M_B_FIELD_NUMBER: _ClassVar[int]
        M_C_FIELD_NUMBER: _ClassVar[int]
        M_D_FIELD_NUMBER: _ClassVar[int]
        INDEX_FIELD_NUMBER: _ClassVar[int]
        m_a: float
        m_b: float
        m_c: float
        m_d: float
        index: int
        def __init__(self, m_a: _Optional[float] = ..., m_b: _Optional[float] = ..., m_c: _Optional[float] = ..., m_d: _Optional[float] = ..., index: _Optional[int] = ...) -> None: ...
    class ShotMeasuredValue(_message.Message):
        __slots__ = ("measured_vals",)
        MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
        measured_vals: _containers.RepeatedCompositeFieldContainer[MachineryResult.MacronodeMeasuredValue]
        def __init__(self, measured_vals: _Optional[_Iterable[_Union[MachineryResult.MacronodeMeasuredValue, _Mapping]]] = ...) -> None: ...
    MEASURED_VALS_FIELD_NUMBER: _ClassVar[int]
    measured_vals: _containers.RepeatedCompositeFieldContainer[MachineryResult.ShotMeasuredValue]
    def __init__(self, measured_vals: _Optional[_Iterable[_Union[MachineryResult.ShotMeasuredValue, _Mapping]]] = ...) -> None: ...
