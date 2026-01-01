import pytest
from py_entry.runner import BacktestRunner
from py_entry.data_generator import DataGenerationParams
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
    br = BacktestRunner()

    # 1000根15m K线，约10.4天
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
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

    br.setup(
        data_source=simulated_data_config,
        indicators_params=indicators_params,
        signal_params={},
        backtest_params=backtest_params,
        performance_params=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    br.run()
    assert br.results is not None
    return br.results[0]
