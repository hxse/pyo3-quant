"""
custom_backtest 公共示例策略

该策略复刻 py_entry/example/custom_backtest.py 的核心参数，
作为公共策略注册到 py_entry/strategies。
"""

from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    PerformanceMetric,
    PerformanceParams,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
)

from . import register_strategy
from .base import StrategyConfig

BASE_DATA_KEY = "ohlcv_15m"
TF_1H_KEY = "ohlcv_1h"
TF_4H_KEY = "ohlcv_4h"


@register_strategy("mtf_bbands_rsi_sma")
def get_config() -> StrategyConfig:
    """返回多周期 BBands + RSI + SMA 的公共策略配置。"""
    data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=10000,
        fixed_seed=42,
        base_data_key=BASE_DATA_KEY,
    )

    indicators_params = {
        BASE_DATA_KEY: {
            "bbands": {
                "period": Param(14),
                "std": Param(2),
            }
        },
        TF_1H_KEY: {
            "rsi": {
                "period": Param(14),
            }
        },
        TF_4H_KEY: {
            "sma_0": {
                "period": Param(8),
            },
            "sma_1": {
                "period": Param(16),
            },
        },
    }

    signal_params = {
        "rsi_center": Param(50, min=40, max=60, step=5),
    }

    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0,
        fee_pct=0.001,
        sl_exit_in_bar=True,
        tp_exit_in_bar=True,
        sl_trigger_mode=True,
        tp_trigger_mode=True,
        tsl_trigger_mode=True,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        tsl_atr_tight=True,
        sl_pct=Param(0.02),
        tp_atr=Param(6),
        tsl_atr=Param(2),
        atr_period=Param(14),
        tsl_psar_af0=Param(0.02),
        tsl_psar_af_step=Param(0.02),
        tsl_psar_max_af=Param(0.2),
    )

    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
            PerformanceMetric.CalmarRatio,
            PerformanceMetric.AnnualizationFactor,
            PerformanceMetric.HasLeadingNanCount,
        ],
        leverage_safety_factor=0.8,
    )

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "close > bbands_upper",
                f"rsi,{TF_1H_KEY}, > $rsi_center",
                f"sma_0,{TF_4H_KEY}, > sma_1,{TF_4H_KEY},",
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "close < bbands_lower",
                f"rsi,{TF_1H_KEY}, < $rsi_center",
                f"sma_0,{TF_4H_KEY}, < sma_1,{TF_4H_KEY},",
            ],
        ),
    )

    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.Performance,
        return_only_final=False,
    )

    return StrategyConfig(
        name="mtf_bbands_rsi_sma",
        description="多周期 BBands + RSI + SMA 示例策略",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        performance_params=performance_params,
    )
