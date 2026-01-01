from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict
import polars as pl

PerformanceMetrics = Dict[str, float]
IndicatorResults = Dict[str, pl.DataFrame]


class BacktestSummary(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    indicators: Optional[IndicatorResults] = None
    signals: Optional[pl.DataFrame] = None
    backtest_result: Optional[pl.DataFrame] = (
        None  # Renamed from backtest in Rust to match dict key often used, but Rust said 'backtest'. Wait, Rust IntoPyObject sets 'backtest_result'.
    )
    performance: Optional[PerformanceMetrics] = None
