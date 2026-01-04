from typing import Dict, List, Tuple, Optional
from pydantic import BaseModel
from ..inputs.backtest import SingleParamSet
from .optimizer import RoundSummary


class WindowResult(BaseModel):
    window_id: int
    train_range: Tuple[int, int]
    test_range: Tuple[int, int]
    best_params: SingleParamSet
    optimize_metric: str
    train_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    history: Optional[List[RoundSummary]] = None


class WalkForwardResult(BaseModel):
    windows: List[WindowResult]
    optimize_metric: str
    aggregate_test_metrics: Dict[str, float]
