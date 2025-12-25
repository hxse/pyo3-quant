import pytest
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.data_generator import DataGenerationParams
from py_entry.data_conversion.types import (
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
        BaseDataKey="ohlcv_15m",
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
        fee_pct=0,
        pause_drawdown=Param.create(0),
        pause_sma=Param.create(0),
        pause_ema=Param.create(0),
        exit_in_bar=False,
        use_extrema_for_exit=False,
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
            PerformanceMetric.TOTAL_RETURN,
            PerformanceMetric.MAX_DRAWDOWN,
            PerformanceMetric.MAX_DRAWDOWN_DURATION,
            PerformanceMetric.SHARPE_RATIO,
            PerformanceMetric.SORTINO_RATIO,
            PerformanceMetric.CALMAR_RATIO,
            PerformanceMetric.TOTAL_TRADES,
            PerformanceMetric.AVG_DAILY_TRADES,
            PerformanceMetric.WIN_RATE,
            PerformanceMetric.PROFIT_LOSS_RATIO,
            PerformanceMetric.AVG_HOLDING_DURATION,
            PerformanceMetric.MAX_HOLDING_DURATION,
            PerformanceMetric.AVG_EMPTY_DURATION,
            PerformanceMetric.MAX_EMPTY_DURATION,
            PerformanceMetric.MAX_SAFE_LEVERAGE,
            PerformanceMetric.ANNUALIZATION_FACTOR,
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
