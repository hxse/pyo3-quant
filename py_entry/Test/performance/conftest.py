import pytest
from py_entry.types import (
    Param,
    PerformanceParams,
    PerformanceMetric,
    ExecutionStage,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import (
    TEST_START_TIME_MS,
    make_backtest_params,
    make_backtest_runner,
    make_engine_settings,
    make_ma_cross_template,
)


@pytest.fixture(scope="module")
def full_performance_result():
    """运行一个包含所有指标的完整回测"""
    # 1000根15m K线，约10.4天
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=TEST_START_TIME_MS,
        num_bars=1000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param(5)},
            "sma_slow": {"period": Param(10)},
        },
    }

    backtest_params = make_backtest_params(
        fee_fixed=0,
        fee_pct=0.001,
        sl_pct=Param(2),
        tp_pct=Param(5),
    )

    signal_template = make_ma_cross_template(
        fast_name="sma_fast",
        slow_name="sma_slow",
        source_key="ohlcv_15m",
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

    engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Performance,
        return_only_final=False,
    )

    # 创建并运行 Backtest
    bt = make_backtest_runner(
        data_source=simulated_data_config,
        indicators=indicators_params,
        signal={},
        backtest=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        performance=performance_params,
    )

    result = bt.run()
    assert result.summary is not None
    return result.summary
