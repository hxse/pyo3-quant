"""
搜索空间示例：30m + 4h 双均线共振（经典基线）。
"""

from __future__ import annotations

from py_entry.private_strategies.config import build_wf_cfg
from py_entry.types import (
    BacktestParams,
    LogicOp,
    Param,
    SignalGroup,
    SignalTemplate,
)


def build_search_space() -> dict:
    """返回经典双周期双均线示例搜索空间。"""
    base_key = "ohlcv_30m"
    htf_key = "ohlcv_4h"

    # 中文注释：示例策略尽量保持朴素，便于审阅与迁移。
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
    )

    variants = [
        {
            "name": "sma_2tf",
            "note": "30m 均线交叉触发 + 4h 均线方向过滤",
            "indicators": {
                base_key: {
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
                htf_key: {
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
            },
            "signal_params": {},
            "template": SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast_htf, {htf_key}, 0 > sma_slow_htf, {htf_key}, 0",
                        f"sma_fast_base, {base_key}, 0 x> sma_slow_base, {base_key}, 0",
                    ],
                ),
                exit_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast_base, {base_key}, 0 x< sma_slow_base, {base_key}, 0",
                    ],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast_htf, {htf_key}, 0 < sma_slow_htf, {htf_key}, 0",
                        f"sma_fast_base, {base_key}, 0 x< sma_slow_base, {base_key}, 0",
                    ],
                ),
                exit_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast_base, {base_key}, 0 x> sma_slow_base, {base_key}, 0",
                    ],
                ),
            ),
        }
    ]

    return {
        "space_name": "sma_2tf",
        "symbol": "BTC/USDT",
        "base_data_key": base_key,
        "timeframes": ["30m", "4h"],
        "since": "2024-01-01 00:00:00",
        "limit": 30000,
        "backtest": backtest_params,
        "wf": build_wf_cfg(opt_overrides={"seed": 303}),
        "variants": variants,
    }
