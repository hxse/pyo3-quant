import pytest
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.types import (
    BacktestParams,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_conversion.data_generator import DataGenerationParams


@pytest.fixture(scope="function")
def runner_with_results():
    """
    运行一个实际的 BacktestRunner 并返回它（已包含 results）。
    配置完全参考 custom_backtest.py
    """

    # 1. 创建 DataGenerationParams 对象
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=1000,  # 测试用 1000 根 BAR 足够
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )

    # 2. 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "bbands": {
                "period": Param.create(14),
                "std": Param.create(2),
            }
        },
        "ohlcv_1h": {
            "rsi": {
                "period": Param.create(14),
            }
        },
        "ohlcv_4h": {
            "sma_0": {
                "period": Param.create(8),
            },
            "sma_1": {
                "period": Param.create(16),
            },
        },
    }

    # 3. 自定义信号参数
    signal_params = {
        # "rsi_upper": Param.create(70, 60, 80, 5),
        "rsi_center": Param.create(50, 40, 60, 5),
        # "rsi_lower": Param.create(30, 20, 40, 5),
        # 为了测试 HorizontalLine 生成逻辑，我们补充 upper/lower
        "rsi_upper": Param.create(70),
        "rsi_lower": Param.create(30),
    }

    # 4. 自定义回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        pause_drawdown=Param.create(0),
        pause_sma=Param.create(0),
        pause_ema=Param.create(0),
        exit_in_bar=False,
        use_extrema_for_exit=False,
        sl_pct=Param.create(2),
        tp_pct=Param.create(2),
        tsl_pct=Param.create(1),
        sl_atr=Param.create(2),
        tp_atr=Param.create(3),
        tsl_atr=Param.create(2),
        atr_period=Param.create(14),
    )

    # 5. 自定义信号模板
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close > bbands_upper",
            "rsi,ohlcv_1h, > $rsi_center",
            "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",
        ],
    )

    signal_template = SignalTemplate(entry_long=entry_long_group)

    # 6. 自定义引擎设置
    # 为了测试 Chart生成，我们需要确保有结果返回，ExecutionStage.BACKTEST 或 PERFORMANCE 都可以
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.BACKTEST,
        return_only_final=False,  # 测试需要指标数据来生成图表配置
    )

    # 7. 创建并运行 Runner
    runner = BacktestRunner()

    runner.setup(
        data_source=simulated_data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        param_set_size=1,
    )

    runner.run()

    return runner
