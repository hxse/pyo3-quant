from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List


class OptimizeMetric(str, Enum):
    SharpeRatio = "sharpe_ratio"
    SortinoRatio = "sortino_ratio"
    CalmarRatio = "calmar_ratio"
    SharpeRatioRaw = "sharpe_ratio_raw"
    SortinoRatioRaw = "sortino_ratio_raw"
    CalmarRatioRaw = "calmar_ratio_raw"
    TotalReturn = "total_return"
    WinRate = "win_rate"
    ProfitLossRatio = "profit_loss_ratio"


class OptimizerConfig(BaseModel):
    explore_ratio: float = 0.30
    sigma_ratio: float = 0.15
    weight_decay: float = 0.10
    top_k_ratio: float = 0.70
    samples_per_round: int = 100
    max_samples: int = 10000
    min_samples: int = 400
    max_rounds: int = 200
    stop_patience: int = 10
    optimize_metric: OptimizeMetric = OptimizeMetric.CalmarRatioRaw
    return_top_k: int = 5
    init_samples: Optional[List[List[float]]] = None
    seed: Optional[int] = None
