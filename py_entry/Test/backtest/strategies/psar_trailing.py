"""
PSAR 追踪止损策略

使用 PSAR 追踪止损：
- sl_pct: PCT 止损（保护性）
- tsl_psar_*: PSAR 追踪止损参数

使用 reversal_extreme 的信号模板来覆盖更多状态机状态
注意：PSAR 不支持 in_bar 模式
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


@register_strategy("psar_trailing")
def get_config() -> StrategyConfig:
    """返回 PSAR 追踪止损策略配置"""

    data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=1735689600000,
        num_bars=10000,
        fixed_seed=456,
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

    # 使用 PSAR 追踪止损 + PCT 止盈
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        pause_drawdown=Param.create(0),
        pause_sma=Param.create(0),
        pause_ema=Param.create(0),
        exit_in_bar=False,  # PSAR 不支持 in_bar
        use_extrema_for_exit=False,
        # PCT 保护性止损止盈
        sl_pct=Param.create(3),
        tp_pct=Param.create(5),
        # PSAR 追踪止损
        tsl_psar_af0=Param.create(0.02),
        tsl_psar_af_step=Param.create(0.02),
        tsl_psar_max_af=Param.create(0.2),
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
        name="psar_trailing",
        description="PSAR 追踪止损策略（tsl_psar + sl_pct + tp_pct）- 覆盖全部 11 状态",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )
