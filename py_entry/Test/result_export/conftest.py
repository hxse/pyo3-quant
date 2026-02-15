import pytest
from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


@pytest.fixture(scope="function")
def runner_with_results():
    """
    运行一个实际的 Backtest 并返回 RunResult。
    配置完全参考 custom_backtest.py
    """

    # 1. 创建 DataGenerationParams 对象
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=1000,  # 测试用 1000 根 BAR 足够
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. 构建指标参数
    indicators_params = {
        "ohlcv_15m": {
            "bbands": {
                "period": Param(14),
                "std": Param(2),
            }
        },
        "ohlcv_1h": {
            "rsi": {
                "period": Param(14),
            }
        },
        "ohlcv_4h": {
            "sma_0": {
                "period": Param(8),
            },
            "sma_1": {
                "period": Param(16),
            },
        },
    }

    # 3. 自定义信号参数
    signal_params = {
        # "rsi_upper": Param(70, 60, 80, 5),
        "rsi_center": Param(50, min=40, max=60, step=5),
        # "rsi_lower": Param(30, 20, 40, 5),
        # 为了测试 HorizontalLine 生成逻辑，我们补充 upper/lower
        "rsi_upper": Param(70),
        "rsi_lower": Param(30),
    }

    # 4. 自定义回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        sl_exit_in_bar=False,
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        sl_pct=Param(2),
        tp_pct=Param(2),
        tsl_pct=Param(1),
        sl_atr=Param(2),
        tp_atr=Param(3),
        tsl_atr=Param(2),
        atr_period=Param(14),
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
    # 为了测试 Chart生成，我们需要确保有结果返回，ExecutionStage.Backtest 或 PERFORMANCE 都可以
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.Backtest,
        return_only_final=False,  # 测试需要指标数据来生成图表配置
    )

    # 7. 创建并运行 Backtest
    bt = Backtest(
        data_source=simulated_data_config,
        indicators=indicators_params,
        signal=signal_params,
        backtest=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    result = bt.run()

    return result
