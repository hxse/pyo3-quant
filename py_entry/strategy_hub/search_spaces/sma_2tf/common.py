"""sma_2tf 策略族公共构建函数。"""

from __future__ import annotations

from py_entry.strategy_hub.core.config import (
    REQUIRED_SYMBOL_PLACEHOLDER,
    build_engine_settings,
    build_ohlcv_fetch_config,
    build_opt_cfg,
    build_performance_params,
    build_sens_cfg,
    build_wf_cfg,
)
from py_entry.strategy_hub.core.spec import (
    ResearchSpec,
    SearchSpaceSpec,
    VariantPayload,
)
from py_entry.types import BacktestParams, LogicOp, Param, SignalGroup, SignalTemplate

STRATEGY_VERSION = "v1"

BASE_DATA_KEY = "ohlcv_30m"
HTF_DATA_KEY = "ohlcv_4h"
TIMEFRAMES = ["30m", "4h"]


def build_sma_2tf_bundle(
    *,
    strategy_name: str,
    use_sl: bool,
    use_tsl: bool,
) -> SearchSpaceSpec:
    """构建 sma_2tf 族策略。"""

    data_config = build_ohlcv_fetch_config(
        symbol=REQUIRED_SYMBOL_PLACEHOLDER,
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
        # 中文注释：trigger/anchor 仅表达“用 close 还是 high/low 检测”，不表达功能开关。
        sl_trigger_mode=False,
        tp_trigger_mode=False,
        tsl_trigger_mode=False,
        sl_anchor_mode=False,
        tp_anchor_mode=False,
        tsl_anchor_mode=False,
        # 中文注释：use_sl/use_tsl 通过参数是否存在来控制功能启用，符合 BacktestParams 语义。
        sl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True)
        if use_sl
        else None,
        tp_pct=Param(0.02, min=0.005, max=0.08, step=0.001, optimize=True),
        tsl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True)
        if use_tsl
        else None,
    )

    variant = VariantPayload(
        indicators_params=indicators,
        signal_params={},
        backtest_params=backtest_params,
        signal_template=signal_template,
    )
    research = ResearchSpec(
        # 中文注释：优化用全局配置，非必要不覆盖。
        opt_cfg=build_opt_cfg(),
        sens_cfg=build_sens_cfg(),
        wf_cfg=build_wf_cfg(),
    )

    return SearchSpaceSpec(
        name=strategy_name,
        version=STRATEGY_VERSION,
        data_config=data_config,
        variant=variant,
        engine_settings=build_engine_settings(),
        performance_params=build_performance_params(),
        research=research,
    )
