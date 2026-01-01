from typing import Dict, List, Optional
from pydantic import BaseModel


class RoundSummary(BaseModel):
    round: int
    best_calmar: float
    median_calmar: float
    sample_count: int


class OptimizationResult(BaseModel):
    best_params: Dict[str, Dict[str, Dict[str, float]]]
    best_signal_params: Dict[str, float]
    best_backtest_params: Dict[str, float]
    best_calmar: float
    total_samples: int
    rounds: int
    history: List[RoundSummary]
