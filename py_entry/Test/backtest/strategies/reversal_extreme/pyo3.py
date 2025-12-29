"""
极端反手策略 - pyo3-quant 配置

策略逻辑：
- 进场：close x> bbands_middle（做多）/ close x< bbands_middle（做空）
- 离场：close x> bbands_upper（多头）/ close x< bbands_lower（空头）
- 风控：2% SL + 4×ATR TP + 1.5×ATR TSL
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

from .. import register_strategy
from ..base import StrategyConfig
from .config import CONFIG as C
from .btp import ReversalExtremeBtp


@register_strategy("reversal_extreme")
def get_config() -> StrategyConfig:
    """返回极端反手策略配置"""

    # 数据配置 - 使用共享参数
    data_config = DataGenerationParams(
        timeframes=[C.timeframe],
        start_time=C.start_time,
        num_bars=C.num_bars,
        fixed_seed=C.fixed_seed,
        BaseDataKey=f"ohlcv_{C.timeframe}",
        allow_gaps=C.allow_gaps,  # 使用统一配置
    )

    # 指标参数 - 使用共享参数
    indicators_params = {
        f"ohlcv_{C.timeframe}": {
            "bbands": {
                "period": Param.create(C.bbands_period),
                "std": Param.create(C.bbands_std),
            }
        },
    }

    signal_params = {}

    # 回测参数 - 使用共享参数
    backtest_params = BacktestParams(
        initial_capital=C.initial_capital,
        fee_fixed=C.fee_fixed,
        fee_pct=C.fee_pct,
        sl_exit_in_bar=C.sl_exit_in_bar,
        tp_exit_in_bar=C.tp_exit_in_bar,
        sl_trigger_mode=C.sl_trigger_mode,
        tp_trigger_mode=C.tp_trigger_mode,
        tsl_trigger_mode=C.tsl_trigger_mode,
        sl_anchor_mode=C.sl_anchor_mode,
        tp_anchor_mode=C.tp_anchor_mode,
        tsl_anchor_mode=C.tsl_anchor_mode,
        sl_pct=Param.create(C.sl_pct),
        tp_atr=Param.create(C.tp_atr),
        tsl_atr=Param.create(C.tsl_atr),
        atr_period=Param.create(C.atr_period),
        tsl_atr_tight=C.tsl_atr_tight,
    )

    # 信号模板
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"close, ohlcv_{C.timeframe}, 0 x> bbands_middle, ohlcv_{C.timeframe}, 0"
        ],
    )

    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"close, ohlcv_{C.timeframe}, 0 x< bbands_middle, ohlcv_{C.timeframe}, 0"
        ],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            f"close, ohlcv_{C.timeframe}, 0 x> bbands_upper, ohlcv_{C.timeframe}, 0",
            f"close, ohlcv_{C.timeframe}, 0 x< bbands_middle, ohlcv_{C.timeframe}, 0",  # Reversal
        ],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            f"close, ohlcv_{C.timeframe}, 0 x< bbands_lower, ohlcv_{C.timeframe}, 0",
            f"close, ohlcv_{C.timeframe}, 0 x> bbands_middle, ohlcv_{C.timeframe}, 0",  # Reversal
        ],
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
        description="全状态机覆盖策略（BBands + 混合风控）",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        btp_strategy_class=ReversalExtremeBtp,
        custom_params={"equity_cutoff_ratio": C.equity_cutoff_ratio},
    )
