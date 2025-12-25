"""
极端反手策略 - 全状态机覆盖测试

策略设计（简单直接）:
- 进场：close x SMA(4) 交叉
- 离场：close > SMA(14) (持续条件，非交叉)
- 风控：2% SL + 3×ATR TP + 1×ATR TSL

覆盖的 11 种状态机状态:
1. no_position          - 空仓
2. hold_long            - 持有多头
3. hold_short           - 持有空头
4. exit_long_signal     - 多头信号离场
5. exit_long_risk       - 多头风控离场
6. exit_short_signal    - 空头信号离场
7. exit_short_risk      - 空头风控离场
8. reversal_long_to_short - 多转空反手
9. reversal_short_to_long - 空转多反手
10. reversal_to_long_then_exit  - 反手做多后风控触发
11. reversal_to_short_then_exit - 反手做空后风控触发
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


@register_strategy("reversal_extreme")
def get_config() -> StrategyConfig:
    """返回极端反手策略配置"""

    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=800,
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )

    # 指标：只需要两个 SMA
    # - sma_fast(4): 进场交叉
    # - sma_exit(14): 离场条件
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(4)},
            "sma_exit": {"period": Param.create(14)},
        },
    }

    signal_params = {}

    # 回测参数：混合风控策略
    # - sl_pct: 2% 止损
    # - tp_atr: 3×ATR 止盈
    # - tsl_atr: 1×ATR 跟踪止损
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        pause_drawdown=Param.create(0),
        pause_sma=Param.create(0),
        pause_ema=Param.create(0),
        exit_in_bar=True,
        use_extrema_for_exit=False,
        sl_pct=Param.create(0.02),
        tp_atr=Param.create(3),
        tsl_atr=Param.create(1),
        atr_period=Param.create(14),
    )

    # 信号模板
    # 进场：close x sma_fast 交叉（快速反应）
    # 离场：close < sma_exit（持续条件，让信号离场有机会触发）
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 x> sma_fast, ohlcv_15m, 0"],
    )

    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 x< sma_fast, ohlcv_15m, 0"],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 < sma_exit, ohlcv_15m, 0"],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_15m, 0 > sma_exit, ohlcv_15m, 0"],
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
        name="reversal_extreme",
        description="全状态机覆盖策略（close×SMA4 进场 + SMA14 离场 + 混合风控）",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
