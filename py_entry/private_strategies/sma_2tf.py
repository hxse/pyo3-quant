"""
private 示例策略配置。

职责：
1. 仅提供策略与阶段配置函数；
2. 不包含执行骨架（由 template.py 统一编排）；
3. 供 CLI 与 ipynb 通过统一模板加载。
"""

from py_entry.private_strategies.config import (
    build_ohlcv_fetch_config,
    build_opt_cfg as build_opt_cfg_base,
    build_runtime_data_meta,
    build_runtime_config as build_runtime_config_base,
    build_sens_cfg as build_sens_cfg_base,
    build_wf_cfg as build_wf_cfg_base,
)
from py_entry.strategies.base import LiveMeta, StrategyConfig
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
)

BASE_DATA_KEY = "ohlcv_30m"
HTF_DATA_KEY = "ohlcv_4h"

SYMBOL = "BTC/USDT"
TIMEFRAMES = ["30m", "4h"]

STRATEGY_NAME = "sma_2tf"
STRATEGY_DESCRIPTION = "30m+4h 双均线共振 private 示例策略"


def get_live_config() -> StrategyConfig:
    """返回 live 策略配置。"""
    real_data_config = build_ohlcv_fetch_config(
        symbol=SYMBOL,
        timeframes=TIMEFRAMES,
        base_data_key=BASE_DATA_KEY,
    )

    indicators = {
        BASE_DATA_KEY: {
            "sma_fast_base": {
                "period": Param(
                    20, min=8, max=60, step=1.0, optimize=True, log_scale=True
                )
            },
            "sma_slow_base": {
                "period": Param(
                    60, min=20, max=200, step=1.0, optimize=True, log_scale=True
                )
            },
        },
        HTF_DATA_KEY: {
            "sma_fast_htf": {
                "period": Param(
                    20, min=8, max=60, step=1.0, optimize=True, log_scale=True
                )
            },
            "sma_slow_htf": {
                "period": Param(
                    60, min=20, max=200, step=1.0, optimize=True, log_scale=True
                )
            },
        },
    }

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast_htf, {HTF_DATA_KEY}, 0 > sma_slow_htf, {HTF_DATA_KEY}, 0",
                f"sma_fast_base, {BASE_DATA_KEY}, 0 x> sma_slow_base, {BASE_DATA_KEY}, 0",
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast_htf, {HTF_DATA_KEY}, 0 < sma_slow_htf, {HTF_DATA_KEY}, 0",
                f"sma_fast_base, {BASE_DATA_KEY}, 0 x< sma_slow_base, {BASE_DATA_KEY}, 0",
            ],
        ),
        exit_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast_base, {BASE_DATA_KEY}, 0 x< sma_slow_base, {BASE_DATA_KEY}, 0"
            ],
        ),
        exit_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast_base, {BASE_DATA_KEY}, 0 x> sma_slow_base, {BASE_DATA_KEY}, 0"
            ],
        ),
    )

    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0.0,
        fee_pct=0.001,
        sl_exit_in_bar=False,
        tp_exit_in_bar=False,
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        sl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True),
        tp_pct=Param(0.02, min=0.005, max=0.08, step=0.001, optimize=True),
        tsl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True),
    )

    strategy = StrategyConfig(
        name=STRATEGY_NAME,
        description=STRATEGY_DESCRIPTION,
        data_config=real_data_config,
        indicators_params=indicators,
        signal_params={},
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.Performance,
            return_only_final=False,
        ),
    )
    strategy.live_meta = LiveMeta(
        enabled=False,
        position_size_pct=0.2,
        leverage=2,
        settlement_currency="USDT",
    )
    return strategy


def build_opt_cfg():
    """构建优化阶段配置。"""
    return build_opt_cfg_base(
        {
            "max_samples": 1000,
            "samples_per_round": 50,
        }
    )


def build_sens_cfg():
    """构建敏感性阶段配置。"""
    return build_sens_cfg_base({"n_samples": 30})


def build_wf_cfg():
    """构建向前测试阶段配置。"""
    return build_wf_cfg_base(
        {
            "train_bars": 10000,
            "transition_bars": 2000,
            "test_bars": 5000,
        },
        opt_overrides={
            "min_samples": 200,
            "max_samples": 600,
            "samples_per_round": 50,
            "stop_patience": 4,
        },
    )


def build_runtime_config() -> dict[str, object]:
    """构建运行时摘要配置。"""
    opt_cfg = build_opt_cfg()
    wf_cfg = build_wf_cfg()
    runtime_data_meta = build_runtime_data_meta(
        symbol=SYMBOL,
        timeframes=TIMEFRAMES,
        base_data_key=BASE_DATA_KEY,
        strategy_logic=STRATEGY_DESCRIPTION,
    )
    return build_runtime_config_base(
        runtime_data_meta,
        wf_cfg=wf_cfg,
        opt_cfg=opt_cfg,
    )
