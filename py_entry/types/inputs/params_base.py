from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal, Optional


class ParamType(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class Param(BaseModel):
    value: float
    min: float = 0.0
    max: float = 0.0
    dtype: ParamType = ParamType.FLOAT
    optimize: bool = False
    log_scale: bool = False
    step: float = 0.0

    @classmethod
    def create(
        cls,
        value: float,
        min: Optional[float] = None,
        max: Optional[float] = None,
        dtype: ParamType = ParamType.FLOAT,
        optimize: bool = False,
        log_scale: bool = False,
        step: float = 0.0,
    ) -> "Param":
        if min is None:
            min = 0.0
        if max is None:
            max = 0.0
        return cls(
            value=value,
            min=min,
            max=max,
            dtype=dtype,
            optimize=optimize,
            log_scale=log_scale,
            step=step,
        )
