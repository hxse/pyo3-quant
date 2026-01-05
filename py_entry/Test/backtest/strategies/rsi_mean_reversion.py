"""
RSI 均值回归策略

策略逻辑:
- RSI(14) 超卖区间做多，超买区间做空
- 进场: RSI < 30 做多，RSI > 70 做空
- 离场: RSI 回归中性区域
"""

from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.types import (
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


@register_strategy("rsi_mean_reversion")
def get_config() -> StrategyConfig:
    """返回 RSI 均值回归策略配置"""

    # 数据配置
    data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=10000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 指标参数
    indicators_params = {
        "ohlcv_15m": {
            "rsi": {"period": Param.create(14)},
        },
    }

    # 信号参数：无自定义信号参数（阈值已在信号模板中硬编码）
    signal_params = {}

    # 回测参数（带风控）
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
        sl_pct=Param.create(3),
        tp_pct=Param.create(5),
        tsl_pct=Param.create(0),
        sl_atr=Param.create(0),
        tp_atr=Param.create(0),
        tsl_atr=Param.create(0),
        atr_period=Param.create(14),
    )

    # 信号模板：RSI 超卖做多，超买做空
    # RSI < 30 进多
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 < 30"],
    )

    # RSI > 70 进空
    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 > 70"],
    )

    # RSI > 50 离多
    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 > 50"],
    )

    # RSI < 50 离空
    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 < 50"],
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
        name="rsi_mean_reversion",
        description="RSI 均值回归策略（RSI14）- 超买超卖反转",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
