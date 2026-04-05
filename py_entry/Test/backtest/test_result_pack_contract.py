"""A2 ResultPack contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import build_result_pack, build_time_mapping
from py_entry.types import DataPack


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


def _data_pack() -> DataPack:
    """构造带 base + HTF 的最小 DataPack。"""
    source = cast(
        dict[str, object],
        {
            "ohlcv_1ms": _ohlcv_df([0, 1, 2, 3]),
            "ohlcv_2ms": _ohlcv_df([0, 2], close_start=10.0),
        },
    )
    return build_time_mapping(source=source, base_data_key="ohlcv_1ms")


def test_build_result_pack_attaches_time_and_preserves_mapping_subset():
    """ResultPack 必须只保留指标子集映射，并为指标补入原始 time 列。"""
    data = _data_pack()
    result = build_result_pack(
        data=data,
        indicators={"ohlcv_2ms": pl.DataFrame({"value": [10.0, 20.0]})},
    )

    assert result.mapping.columns == ["time", "ohlcv_2ms"]
    assert result.mapping["time"].to_list() == data.mapping["time"].to_list()
    assert result.mapping["ohlcv_2ms"].to_list() == data.mapping["ohlcv_2ms"].to_list()
    assert result.ranges["ohlcv_2ms"].pack_bars == data.ranges["ohlcv_2ms"].pack_bars
    assert result.base_data_key == data.base_data_key
    assert result.indicators is not None
    assert result.indicators["ohlcv_2ms"]["time"].to_list() == [0, 2]
    assert result.indicators["ohlcv_2ms"]["value"].to_list() == [10.0, 20.0]


def test_build_result_pack_rejects_indicator_with_existing_time_column():
    """上游 raw indicators 已携带 time 列时必须直接报错。"""
    data = _data_pack()

    with pytest.raises(ValueError, match="不允许预先携带 time 列"):
        build_result_pack(
            data=data,
            indicators={
                "ohlcv_2ms": pl.DataFrame({"time": [0, 2], "value": [10.0, 20.0]})
            },
        )


def test_build_result_pack_rejects_indicator_height_mismatch():
    """indicator 行数与对应 source 不一致时必须直接报错。"""
    data = _data_pack()

    with pytest.raises(
        ValueError, match="必须等于 data.source\\['ohlcv_2ms'\\].height\\(\\)=2"
    ):
        build_result_pack(
            data=data,
            indicators={"ohlcv_2ms": pl.DataFrame({"value": [10.0]})},
        )


def test_build_result_pack_rejects_signal_and_backtest_height_mismatch():
    """signals/backtest 高度不等于 mapping 高度时必须直接报错。"""
    data = _data_pack()
    signals = pl.DataFrame({"flag": [1, 0, 1]})
    backtest = pl.DataFrame({"equity": [1.0, 1.0, 1.0]})

    with pytest.raises(
        ValueError, match="signals.height\\(\\)=3 必须等于 data.mapping.height\\(\\)=4"
    ):
        build_result_pack(data=data, signals=signals)

    with pytest.raises(
        ValueError, match="backtest.height\\(\\)=3 必须等于 data.mapping.height\\(\\)=4"
    ):
        build_result_pack(data=data, backtest_result=backtest)


def test_build_result_pack_strips_internal_backtest_columns():
    """backtest 中的 has_leading_nan 只允许保留在 signals，不得进入正式 ResultPack.backtest。"""
    data = _data_pack()
    backtest = pl.DataFrame(
        {
            "equity": [10_000.0, 10_100.0, 10_050.0, 10_200.0],
            "has_leading_nan": [True, True, False, False],
        }
    )

    result = build_result_pack(data=data, backtest_result=backtest)
    assert result.backtest_result is not None
    assert "has_leading_nan" not in result.backtest_result.columns
    assert result.backtest_result["equity"].to_list() == backtest["equity"].to_list()
