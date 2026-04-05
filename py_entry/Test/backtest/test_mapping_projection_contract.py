"""A1 mapping / projection contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import build_mapping_frame


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


def test_build_mapping_frame_keeps_time_first_and_uint32_projection():
    """mapping 必须固定 time-first，且投影列为 UInt32。"""
    source = cast(
        dict[str, object],
        {
            "ohlcv_1ms": _ohlcv_df([0, 1, 2, 3]),
            "ohlcv_2ms": _ohlcv_df([0, 2], close_start=10.0),
        },
    )
    mapping = cast(
        pl.DataFrame,
        build_mapping_frame(
            source=source,
            base_data_key="ohlcv_1ms",
        ),
    )

    assert mapping.columns[0] == "time"
    assert set(mapping.columns[1:]) == {"ohlcv_1ms", "ohlcv_2ms"}
    assert mapping["time"].dtype == pl.Int64
    assert mapping["ohlcv_1ms"].dtype == pl.UInt32
    assert mapping["ohlcv_2ms"].dtype == pl.UInt32
    assert mapping["ohlcv_2ms"].to_list() == [0, 0, 1, 1]


def test_build_mapping_frame_rejects_tail_coverage_gap():
    """尾覆盖不足时，mapping 构建必须直接 fail-fast。"""
    source = cast(
        dict[str, object],
        {
            "ohlcv_1ms": _ohlcv_df([0, 1, 2]),
            "ohlcv_2ms": _ohlcv_df([0], close_start=10.0),
        },
    )
    with pytest.raises(ValueError, match="尾覆盖失败"):
        build_mapping_frame(
            source=source,
            base_data_key="ohlcv_1ms",
        )
