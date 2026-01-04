from typing import Dict, List, Optional
from pydantic import BaseModel
from ..inputs.backtest import SingleParamSet


class RoundSummary(BaseModel):
    round: int
    best_value: float
    median_value: float
    sample_count: int


class SamplePoint(BaseModel):
    values: List[float]
    metric_value: float
    all_metrics: Dict[str, float]


class OptimizationResult(BaseModel):
    best_params: SingleParamSet
    optimize_metric: str
    optimize_value: float
    metrics: Dict[str, float]
    total_samples: int
    rounds: int
    history: List[RoundSummary]
    top_k_params: List[SingleParamSet]
    top_k_samples: List[SamplePoint]
