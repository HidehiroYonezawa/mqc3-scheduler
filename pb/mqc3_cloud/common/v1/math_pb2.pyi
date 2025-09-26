from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Complex(_message.Message):
    __slots__ = ("real", "imag")
    REAL_FIELD_NUMBER: _ClassVar[int]
    IMAG_FIELD_NUMBER: _ClassVar[int]
    real: float
    imag: float
    def __init__(self, real: _Optional[float] = ..., imag: _Optional[float] = ...) -> None: ...
