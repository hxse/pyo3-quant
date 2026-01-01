from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal


class ParamType(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class Param(BaseModel):
    value: float
    initial_value: float = 0.0
    min: float = 0.0
    initial_min: float = 0.0
    max: float = 0.0
    initial_max: float = 0.0
    dtype: ParamType = ParamType.FLOAT
    optimize: bool = False
    log_scale: bool = False
    step: float = 0.0

    @classmethod
    def create(
        cls,
        value: float,
        initial_value: float = 0.0,
        min: float = 0.0,
        initial_min: float = 0.0,
        max: float = 0.0,
        initial_max: float = 0.0,
        dtype: ParamType = ParamType.FLOAT,
        optimize: bool = False,
        log_scale: bool = False,
        step: float = 0.0,
    ) -> "Param":
        return cls(
            value=value,
            initial_value=initial_value,
            min=min,
            initial_min=initial_min,
            max=max,
            initial_max=initial_max,
            dtype=dtype,
            optimize=optimize,
            log_scale=log_scale,
            step=step,
        )
