"""A2 strip_indicator_time_columns contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import (
    build_result_pack,
    build_time_mapping,
    strip_indicator_time_columns,
)


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


def test_strip_indicator_time_columns_rejects_missing_time():
    """缺少 time 列时必须直接 fail-fast。"""
    with pytest.raises(ValueError, match="缺少 time 列"):
        strip_indicator_time_columns({"ohlcv_2ms": pl.DataFrame({"value": [1.0, 2.0]})})


def test_strip_indicator_time_columns_roundtrip_back_into_build_result_pack():
    """strip 后结果必须能直接回喂 build_result_pack。"""
    source = cast(
        dict[str, object],
        {
            "ohlcv_1ms": _ohlcv_df([0, 1, 2, 3]),
            "ohlcv_2ms": _ohlcv_df([0, 2], close_start=10.0),
        },
    )
    data = build_time_mapping(
        source=source,
        base_data_key="ohlcv_1ms",
    )
    result = build_result_pack(
        data=data,
        indicators={"ohlcv_2ms": pl.DataFrame({"value": [7.0, 8.0]})},
    )

    assert result.indicators is not None
    stripped = strip_indicator_time_columns(cast(dict[str, object], result.indicators))
    stripped_df = cast(pl.DataFrame, stripped["ohlcv_2ms"])
    assert stripped_df.columns == ["value"]
    assert stripped_df["value"].to_list() == [7.0, 8.0]

    rebuilt = build_result_pack(data=data, indicators=stripped)
    assert rebuilt.indicators is not None
    assert rebuilt.indicators["ohlcv_2ms"]["time"].to_list() == [0, 2]
    assert rebuilt.indicators["ohlcv_2ms"]["value"].to_list() == [7.0, 8.0]
