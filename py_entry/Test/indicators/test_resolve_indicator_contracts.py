import pytest

import pyo3_quant
from py_entry.types import Param


def _build_params(period_optimize: bool = False):
    """构造用于契约聚合测试的最小参数集。"""
    return {
        "ohlcv_15m": {
            "sma_0": {
                "period": Param(
                    value=10,
                    min=5,
                    max=20,
                    optimize=period_optimize,
                    step=1,
                )
            },
            "macd_0": {
                "fast_period": Param(12),
                "slow_period": Param(26),
                "signal_period": Param(9),
            },
            "psar_0": {
                "af0": Param(0.02),
                "af_step": Param(0.02),
                "max_af": Param(0.2),
            },
        }
    }


def test_resolve_indicator_contracts_returns_diagnosable_report():
    """校验聚合函数返回结构可诊断且字段完整。"""
    report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
        _build_params(period_optimize=False)
    )

    warmup_by_source = report.warmup_bars_by_source
    contracts = report.contracts_by_indicator

    assert warmup_by_source["ohlcv_15m"] == 33
    assert contracts["ohlcv_15m::sma_0"].warmup_bars == 9
    assert contracts["ohlcv_15m::macd_0"].warmup_bars == 33
    assert contracts["ohlcv_15m::psar_0"].warmup_mode == "Relaxed"


def test_resolve_indicator_contracts_uses_optimize_max_rule():
    """校验参数解析规则：optimize=true 使用 max。"""
    report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(
        _build_params(period_optimize=True)
    )

    contracts = report.contracts_by_indicator
    # sma period=20 -> warmup=19
    assert contracts["ohlcv_15m::sma_0"].warmup_bars == 19


def test_resolve_indicator_contracts_optimize_true_prefers_max_not_value():
    """optimize=true 时必须使用 max，而不是 value。"""
    params = {
        "ohlcv_15m": {
            "sma_opt": {
                "period": Param(
                    value=10,
                    min=5,
                    max=50,
                    optimize=True,
                    step=1,
                )
            }
        }
    }
    report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(params)
    contract = report.contracts_by_indicator["ohlcv_15m::sma_opt"]
    assert contract.warmup_bars == 49


def test_resolve_indicator_contracts_multi_source_heterogeneous_warmup():
    """多 source 异构 warmup：各 source 独立聚合，互不污染。"""
    params = {
        "ohlcv_15m": {
            "sma_15m": {"period": Param(5)},
        },
        "ohlcv_1h": {
            "sma_1h": {"period": Param(200)},
        },
    }
    report = pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(params)
    warmup = report.warmup_bars_by_source
    assert warmup["ohlcv_15m"] == 4
    assert warmup["ohlcv_1h"] == 199


def test_resolve_indicator_contracts_fails_fast_on_unknown_indicator():
    """未知指标必须直接报错，不允许静默跳过。"""
    bad_params = {
        "ohlcv_15m": {
            "unknown_0": {
                "period": Param(10),
            }
        }
    }

    with pytest.raises(Exception):
        pyo3_quant.backtest_engine.indicators.resolve_indicator_contracts(bad_params)
