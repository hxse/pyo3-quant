"""A2 analyze_performance contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import build_data_pack
from pyo3_quant.backtest_engine.performance_analyzer import analyze_performance
from py_entry.types import DataPack, PerformanceMetric, PerformanceParams, SourceRange


def _ohlcv_df(times: list[int], close_start: float = 1.0) -> pl.DataFrame:
    """构造最小 OHLCV DataFrame。"""
    closes = [close_start + float(index) for index in range(len(times))]
    return pl.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * len(times),
        }
    )


def _data_pack_with_warmup() -> DataPack:
    """构造带 base warmup 的最小 DataPack。"""
    source = cast(dict[str, object], {"ohlcv_1ms": _ohlcv_df([0, 1, 2, 3, 4])})
    return build_data_pack(
        source=source,
        base_data_key="ohlcv_1ms",
        ranges={"ohlcv_1ms": SourceRange(warmup_bars=2, active_bars=3, pack_bars=5)},
    )


def _full_backtest_df() -> pl.DataFrame:
    """构造满足 analyze_performance 输入 contract 的最小 backtest。"""
    return pl.DataFrame(
        [
            pl.Series("equity", [100.0, 50.0, 100.0, 120.0, 130.0], dtype=pl.Float64),
            pl.Series("trade_pnl_pct", [0.0, 0.0, 0.10, 0.20, 0.0], dtype=pl.Float64),
            pl.Series(
                "current_drawdown", [0.0, 0.90, 0.20, 0.10, 0.0], dtype=pl.Float64
            ),
            pl.Series(
                "entry_long_price",
                [None, None, 1.0, None, None],
                dtype=pl.Float64,
            ),
            pl.Series(
                "entry_short_price",
                [None, None, None, None, None],
                dtype=pl.Float64,
            ),
            pl.Series(
                "total_return_pct",
                [-0.50, -0.50, 0.00, 0.20, 0.30],
                dtype=pl.Float64,
            ),
        ]
    )


def test_analyze_performance_rejects_active_only_backtest_input():
    """外部预切 active-only backtest 时必须直接报错。"""
    data = _data_pack_with_warmup()
    active_only = _full_backtest_df().slice(2, 3)

    with pytest.raises(
        Exception, match="backtest.height\\(\\)=3 必须等于 data.mapping.height\\(\\)=5"
    ):
        analyze_performance(
            data,
            active_only,
            PerformanceParams(metrics=[PerformanceMetric.TotalReturn]),
        )


def test_analyze_performance_only_reads_internal_active_slice():
    """绩效统计必须只基于 DataPack.ranges 切出的 active 段。"""
    data = _data_pack_with_warmup()
    metrics = analyze_performance(
        data,
        _full_backtest_df(),
        PerformanceParams(
            metrics=[
                PerformanceMetric.TotalReturn,
                PerformanceMetric.MaxDrawdown,
                PerformanceMetric.SpanMs,
            ]
        ),
    )

    # 中文注释：warmup 两行里故意放了更大的回撤和更差收益，
    # 若实现错误地把 warmup 计入统计，这里就不会得到下面的结果。
    assert metrics["total_return"] == pytest.approx(0.30)
    assert metrics["max_drawdown"] == pytest.approx(0.20)
    assert metrics["span_ms"] == pytest.approx(2.0)
