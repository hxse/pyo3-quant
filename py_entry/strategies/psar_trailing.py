"""
PSAR 追踪止损策略

使用 PSAR 追踪止损：
- sl_pct: PCT 止损（保护性）
- tsl_psar_*: PSAR 追踪止损参数

使用 reversal_extreme 的信号模板来覆盖更多状态机状态
注意：PSAR 不支持 in_bar 模式
"""

from py_entry.types import (
    Param,
    BacktestParams,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_generator import DataGenerationParams

from . import register_strategy
from .base import StrategyConfig

BASE_DATA_KEY = "ohlcv_15m"
TF_1H_KEY = "ohlcv_1h"


@register_strategy("psar_trailing")
def get_config() -> StrategyConfig:
    """返回 PSAR 追踪止损策略配置"""

    data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=1735689600000,
        num_bars=10000,
        fixed_seed=456,
        base_data_key=BASE_DATA_KEY,
    )

    # 使用 reversal_extreme 的指标配置
    indicators_params = {
        BASE_DATA_KEY: {
            "sma_fast": {"period": Param(3)},
            "sma_slow": {"period": Param(5)},
            "sma_exit": {"period": Param(7)},  # 用于独立离场
        },
    }

    signal_params = {}

    # 使用 PSAR 追踪止损 + PCT 止盈
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,
        sl_exit_in_bar=False,  # PSAR 不支持 in_bar
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        # PCT 保护性止损止盈
        sl_pct=Param(3),
        tp_pct=Param(5),
        # PSAR 追踪止损
        tsl_psar_af0=Param(0.02),
        tsl_psar_af_step=Param(0.02),
        tsl_psar_max_af=Param(0.2),
    )

    # 使用 reversal_extreme 的信号模板（交叉信号）
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[f"sma_fast, {BASE_DATA_KEY}, 0 x> sma_slow, {BASE_DATA_KEY}, 0"],
    )
    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[f"sma_fast, {BASE_DATA_KEY}, 0 x< sma_slow, {BASE_DATA_KEY}, 0"],
    )
    # 离场条件：使用 close 和 sma_exit 的交叉（独立于进场信号）
    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[f"close, {BASE_DATA_KEY}, 0 x< sma_exit, {BASE_DATA_KEY}, 0"],
    )
    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[f"close, {BASE_DATA_KEY}, 0 x> sma_exit, {BASE_DATA_KEY}, 0"],
    )

    signal_template = SignalTemplate(
        entry_long=entry_long_group,
        entry_short=entry_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
    )

    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.Performance,
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
