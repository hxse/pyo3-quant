"""
搜索空间示例：30m + 4h + 1d 纯 MACD 共振。
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
    """返回单一策略组合搜索空间。"""
    base_key = "ohlcv_30m"
    htf_key = "ohlcv_4h"
    vhtf_key = "ohlcv_1d"

    # 中文注释：示例文件自包含，避免依赖未上传的私有公共模块。
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
        tsl_atr=Param(2.0, min=1.2, max=3.6, step=0.1, optimize=True),
        atr_period=Param(14, min=10, max=24, step=1.0, optimize=True),
    )

    wf_config = build_wf_cfg(opt_overrides={"seed": 303})

    variants = [
        {
            "name": "macd_3tf",
            "note": "30m+4h+1d 纯 MACD 共振",
            "indicators": {
                base_key: {
                    "macd_base": {
                        "fast_period": Param(
                            12, min=6, max=24, step=1.0, optimize=True, log_scale=True
                        ),
                        "slow_period": Param(
                            26, min=14, max=56, step=1.0, optimize=True, log_scale=True
                        ),
                        "signal_period": Param(
                            9, min=4, max=18, step=1.0, optimize=True, log_scale=True
                        ),
                    }
                },
                htf_key: {
                    "macd_htf": {
                        "fast_period": Param(
                            12, min=6, max=24, step=1.0, optimize=True, log_scale=True
                        ),
                        "slow_period": Param(
                            26, min=16, max=60, step=1.0, optimize=True, log_scale=True
                        ),
                        "signal_period": Param(
                            9, min=4, max=18, step=1.0, optimize=True, log_scale=True
                        ),
                    }
                },
                vhtf_key: {
                    "macd_vhtf": {
                        "fast_period": Param(
                            12, min=6, max=24, step=1.0, optimize=True, log_scale=True
                        ),
                        "slow_period": Param(
                            26, min=16, max=60, step=1.0, optimize=True, log_scale=True
                        ),
                        "signal_period": Param(
                            9, min=4, max=18, step=1.0, optimize=True, log_scale=True
                        ),
                    }
                },
            },
            "signal_params": {},
            "template": SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_base_macd, {base_key}, 0 x> macd_base_signal, {base_key}, 0",
                        f"macd_htf_macd, {htf_key}, 0 > macd_htf_signal, {htf_key}, 0",
                        f"macd_vhtf_macd, {vhtf_key}, 0 > macd_vhtf_signal, {vhtf_key}, 0",
                    ],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"macd_base_macd, {base_key}, 0 x< macd_base_signal, {base_key}, 0",
                        f"macd_htf_macd, {htf_key}, 0 < macd_htf_signal, {htf_key}, 0",
                        f"macd_vhtf_macd, {vhtf_key}, 0 < macd_vhtf_signal, {vhtf_key}, 0",
                    ],
                ),
                exit_long=None,
                exit_short=None,
            ),
        }
    ]
    return {
        "space_name": "macd_3tf",
        "symbol": "SOL/USDT",
        "base_data_key": base_key,
        "timeframes": ["30m", "4h", "1d"],
        "since": "2024-01-01 00:00:00",
        "limit": 30000,
        "backtest": backtest_params,
        "wf": wf_config,
        "variants": variants,
    }
