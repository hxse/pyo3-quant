from typing import Dict, List, Tuple
from pydantic import BaseModel


class WindowResult(BaseModel):
    window_id: int
    train_range: Tuple[int, int]
    test_range: Tuple[int, int]
    best_params: Dict[str, Dict[str, Dict[str, float]]]
    train_calmar: float
    test_calmar: float
    train_return: float
    test_return: float


class WalkForwardResult(BaseModel):
    windows: List[WindowResult]
    aggregate_test_calmar: float
    aggregate_test_return: float
