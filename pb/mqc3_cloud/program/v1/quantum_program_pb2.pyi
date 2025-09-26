from mqc3_cloud.program.v1 import circuit_pb2 as _circuit_pb2
from mqc3_cloud.program.v1 import graph_pb2 as _graph_pb2
from mqc3_cloud.program.v1 import machinery_pb2 as _machinery_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RepresentationFormat(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REPRESENTATION_FORMAT_UNSPECIFIED: _ClassVar[RepresentationFormat]
    REPRESENTATION_FORMAT_CIRCUIT: _ClassVar[RepresentationFormat]
    REPRESENTATION_FORMAT_GRAPH: _ClassVar[RepresentationFormat]
    REPRESENTATION_FORMAT_MACHINERY: _ClassVar[RepresentationFormat]
REPRESENTATION_FORMAT_UNSPECIFIED: RepresentationFormat
REPRESENTATION_FORMAT_CIRCUIT: RepresentationFormat
REPRESENTATION_FORMAT_GRAPH: RepresentationFormat
REPRESENTATION_FORMAT_MACHINERY: RepresentationFormat

class QuantumProgram(_message.Message):
    __slots__ = ("format", "circuit", "graph", "machinery")
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    CIRCUIT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_FIELD_NUMBER: _ClassVar[int]
    MACHINERY_FIELD_NUMBER: _ClassVar[int]
    format: RepresentationFormat
    circuit: _circuit_pb2.CircuitRepresentation
    graph: _graph_pb2.GraphRepresentation
    machinery: _machinery_pb2.MachineryRepresentation
    def __init__(self, format: _Optional[_Union[RepresentationFormat, str]] = ..., circuit: _Optional[_Union[_circuit_pb2.CircuitRepresentation, _Mapping]] = ..., graph: _Optional[_Union[_graph_pb2.GraphRepresentation, _Mapping]] = ..., machinery: _Optional[_Union[_machinery_pb2.MachineryRepresentation, _Mapping]] = ...) -> None: ...

class QuantumProgramResult(_message.Message):
    __slots__ = ("circuit_result", "graph_result", "machinery_result", "compiled_graph", "compiled_machinery", "circuit_state")
    CIRCUIT_RESULT_FIELD_NUMBER: _ClassVar[int]
    GRAPH_RESULT_FIELD_NUMBER: _ClassVar[int]
    MACHINERY_RESULT_FIELD_NUMBER: _ClassVar[int]
    COMPILED_GRAPH_FIELD_NUMBER: _ClassVar[int]
    COMPILED_MACHINERY_FIELD_NUMBER: _ClassVar[int]
    CIRCUIT_STATE_FIELD_NUMBER: _ClassVar[int]
    circuit_result: _circuit_pb2.CircuitResult
    graph_result: _graph_pb2.GraphResult
    machinery_result: _machinery_pb2.MachineryResult
    compiled_graph: _graph_pb2.GraphRepresentation
    compiled_machinery: _machinery_pb2.MachineryRepresentation
    circuit_state: _containers.RepeatedCompositeFieldContainer[_circuit_pb2.BosonicState]
    def __init__(self, circuit_result: _Optional[_Union[_circuit_pb2.CircuitResult, _Mapping]] = ..., graph_result: _Optional[_Union[_graph_pb2.GraphResult, _Mapping]] = ..., machinery_result: _Optional[_Union[_machinery_pb2.MachineryResult, _Mapping]] = ..., compiled_graph: _Optional[_Union[_graph_pb2.GraphRepresentation, _Mapping]] = ..., compiled_machinery: _Optional[_Union[_machinery_pb2.MachineryRepresentation, _Mapping]] = ..., circuit_state: _Optional[_Iterable[_Union[_circuit_pb2.BosonicState, _Mapping]]] = ...) -> None: ...
