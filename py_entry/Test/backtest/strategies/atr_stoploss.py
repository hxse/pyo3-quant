"""
ATR 止损止盈策略

使用 ATR 方式的止损止盈，不使用 PCT：
- sl_atr: ATR 止损
- tp_atr: ATR 止盈
- tsl_atr: ATR 追踪止损
- tsl_atr_tight: 紧密追踪模式

使用 reversal_extreme 的信号模板来覆盖更多状态机状态
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


@register_strategy("atr_stoploss")
def get_config() -> StrategyConfig:
    """返回 ATR 止损止盈策略配置"""

    data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=1735689600000,
        num_bars=10000,
        fixed_seed=123,
        BaseDataKey="ohlcv_15m",
    )

    # 使用 reversal_extreme 的指标配置
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(3)},
            "sma_slow": {"period": Param.create(5)},
            "sma_exit": {"period": Param.create(7)},  # 用于独立离场
        },
    }

    signal_params = {}

    # 只使用 ATR 止损止盈 + ATR 追踪止损
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        sl_exit_in_bar=True,
        tp_exit_in_bar=True,
        sl_trigger_mode=True,
        tp_trigger_mode=True,
        tsl_trigger_mode=True,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        # ATR 止损止盈
        sl_atr=Param.create(1.5),
        tp_atr=Param.create(3),
        tsl_atr=Param.create(1),
        tsl_atr_tight=True,
        atr_period=Param.create(14),
    )

    # 使用 reversal_extreme 的信号模板（交叉信号）
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0"],
    )
    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast, ohlcv_15m, 0 x< sma_slow, ohlcv_15m, 0"],
    )
    # 离场条件：使用 close 和 sma_exit 的交叉（独立于进场信号）
    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 x< sma_exit, ohlcv_15m, 0"],
    )
    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 x> sma_exit, ohlcv_15m, 0"],
    )

    signal_template = SignalTemplate(
        entry_long=entry_long_group,
        entry_short=entry_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
    )

    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )

    return StrategyConfig(
        name="atr_stoploss",
        description="ATR 止损止盈策略（sl_atr + tp_atr + tsl_atr）- 覆盖全部 11 状态",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
