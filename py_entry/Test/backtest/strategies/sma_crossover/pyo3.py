"""
双均线交叉策略 - pyo3-quant 配置

策略逻辑:
- 快线: SMA(5)
- 慢线: SMA(10)
- 进场: 金叉做多，死叉做空（使用 crossover 交叉信号）
- 离场: 反向交叉
"""

from py_entry.data_generator import DataGenerationParams
from py_entry.types import (
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
from .btp import SmaCrossoverBtp


@register_strategy("sma_crossover")
def get_config() -> StrategyConfig:
    """返回双均线交叉策略配置"""

    # 数据配置 - 使用共享参数
    data_config = DataGenerationParams(
        timeframes=[C.timeframe],
        start_time=C.start_time,
        num_bars=C.num_bars,
        fixed_seed=C.fixed_seed,
        base_data_key=f"ohlcv_{C.timeframe}",
        allow_gaps=C.allow_gaps,  # 使用统一配置
    )

    # 指标参数 - 使用共享参数
    indicators_params = {
        f"ohlcv_{C.timeframe}": {
            "sma_fast": {"period": Param.create(C.sma_fast_period)},
            "sma_slow": {"period": Param.create(C.sma_slow_period)},
        },
    }

    signal_params = {}

    # 回测参数 - 使用共享参数（无风控）
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
    )

    # 信号模板：金叉做多，死叉做空（使用 crossover 交叉信号）
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"sma_fast, ohlcv_{C.timeframe}, 0 x> sma_slow, ohlcv_{C.timeframe}, 0"
        ],
    )

    entry_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"sma_fast, ohlcv_{C.timeframe}, 0 x< sma_slow, ohlcv_{C.timeframe}, 0"
        ],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"sma_fast, ohlcv_{C.timeframe}, 0 x< sma_slow, ohlcv_{C.timeframe}, 0"
        ],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            f"sma_fast, ohlcv_{C.timeframe}, 0 x> sma_slow, ohlcv_{C.timeframe}, 0"
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
        name="sma_crossover",
        description="双均线交叉策略（SMA5/SMA10）- 无风控",
        data_config=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        btp_strategy_class=SmaCrossoverBtp,
        custom_params={"equity_cutoff_ratio": C.equity_cutoff_ratio},
    )
