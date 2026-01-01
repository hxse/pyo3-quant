from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel
from .params_base import Param

IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
SignalParams = Dict[str, Param]


class PerformanceMetric(str, Enum):
    TotalReturn = "total_return"
    MaxDrawdown = "max_drawdown"
    MaxDrawdownDuration = "max_drawdown_duration"
    SharpeRatio = "sharpe_ratio"
    SortinoRatio = "sortino_ratio"
    CalmarRatio = "calmar_ratio"
    SharpeRatioRaw = "sharpe_ratio_raw"
    SortinoRatioRaw = "sortino_ratio_raw"
    CalmarRatioRaw = "calmar_ratio_raw"
    TotalTrades = "total_trades"
    AvgDailyTrades = "avg_daily_trades"
    WinRate = "win_rate"
    ProfitLossRatio = "profit_loss_ratio"
    AvgHoldingDuration = "avg_holding_duration"
    AvgEmptyDuration = "avg_empty_duration"
    MaxHoldingDuration = "max_holding_duration"
    MaxEmptyDuration = "max_empty_duration"
    MaxSafeLeverage = "max_safe_leverage"
    AnnualizationFactor = "annualization_factor"
    HasLeadingNanCount = "has_leading_nan_count"


class BacktestParams(BaseModel):
    sl_pct: Optional[Param] = None
    tp_pct: Optional[Param] = None
    tsl_pct: Optional[Param] = None

    sl_atr: Optional[Param] = None
    tp_atr: Optional[Param] = None
    tsl_atr: Optional[Param] = None
    atr_period: Optional[Param] = None

    tsl_psar_af0: Optional[Param] = None
    tsl_psar_af_step: Optional[Param] = None
    tsl_psar_max_af: Optional[Param] = None

    tsl_atr_tight: bool = False

    sl_exit_in_bar: bool = False
    tp_exit_in_bar: bool = False

    sl_trigger_mode: bool = False
    tp_trigger_mode: bool = False
    tsl_trigger_mode: bool = False

    sl_anchor_mode: bool = False
    tp_anchor_mode: bool = False
    tsl_anchor_mode: bool = False

    initial_capital: float
    fee_fixed: float
    fee_pct: float


class PerformanceParams(BaseModel):
    metrics: List[PerformanceMetric]
    risk_free_rate: float = 0.0
    leverage_safety_factor: Optional[float] = None


class SingleParamSet(BaseModel):
    indicators: IndicatorsParams
    signal: SignalParams
    backtest: BacktestParams
    performance: PerformanceParams


ParamContainer = List[SingleParamSet]
