"""
双均线交叉策略

策略逻辑:
- 快线: SMA(5)
- 慢线: SMA(10)
- 进场: 金叉做多，死叉做空
- 离场: 反向交叉 或 风控触发
"""

from py_entry.data_conversion.data_generator import DataGenerationParams
from py_entry.data_conversion.types import (
    BacktestParams,
    Param,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)

from . import register_strategy
from .base import StrategyConfig


@register_strategy("sma_crossover")
def get_config() -> StrategyConfig:
    """返回双均线交叉策略配置"""

    # 数据配置
    data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=10000,
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )

    # 指标参数
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(5)},
            "sma_slow": {"period": Param.create(10)},
        },
    }

    # 信号参数
    signal_params = {}

    # 回测参数（带风控）
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

    # 信号模板：金叉做多，死叉做空
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
    )

    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0"],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0"],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0"],
    )

    signal_template = SignalTemplate(
        entry_long=entry_long_group,
        entry_short=entry_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
    )

    # 引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )

    return StrategyConfig(
        name="sma_crossover",
        description="双均线交叉策略（SMA5/SMA10）- 带风控",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
