import pytest
from py_entry.runner import Backtest
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.types import (
    BacktestParams,
    Param,
    PerformanceParams,
    PerformanceMetric,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)


@pytest.fixture(scope="module")
def full_performance_result():
    """运行一个包含所有指标的完整回测"""
    # br = BacktestRunner() # Removed

    # 1000根15m K线，约10.4天
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=1000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(5)},
            "sma_slow": {"period": Param.create(10)},
        },
    }

    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0,
        fee_pct=0.001,
        sl_exit_in_bar=False,
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        sl_pct=Param.create(2),
        tp_pct=Param.create(5),
    )

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0"],
        ),
        exit_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0"],
        ),
        exit_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
        ),
    )

    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
            PerformanceMetric.MaxDrawdownDuration,
            PerformanceMetric.SharpeRatio,
            PerformanceMetric.SortinoRatio,
            PerformanceMetric.CalmarRatio,
            PerformanceMetric.TotalTrades,
            PerformanceMetric.AvgDailyTrades,
            PerformanceMetric.WinRate,
            PerformanceMetric.ProfitLossRatio,
            PerformanceMetric.AvgHoldingDuration,
            PerformanceMetric.MaxHoldingDuration,
            PerformanceMetric.AvgEmptyDuration,
            PerformanceMetric.MaxEmptyDuration,
            PerformanceMetric.MaxSafeLeverage,
            PerformanceMetric.AnnualizationFactor,
        ],
        risk_free_rate=0.0,
        leverage_safety_factor=0.8,
    )

    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )

    # 7. 创建并运行 Backtest
    bt = Backtest(
        data_source=simulated_data_config,
        indicators=indicators_params,
        signal={},
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    result = bt.run()
    assert result.summary is not None
    return result.summary
