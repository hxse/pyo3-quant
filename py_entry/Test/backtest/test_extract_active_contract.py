"""A2 extract_active contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import (
    build_data_pack,
    build_result_pack,
    extract_active,
)
from py_entry.types import DataPack, ResultPack, SourceRange


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


def _build_data_and_result() -> tuple[DataPack, ResultPack]:
    """构造带 warmup、indicators、signals、backtest、skip_mask 的同源输入。"""
    source = cast(
        dict[str, object],
        {
            "ohlcv_1ms": _ohlcv_df([0, 1, 2, 3, 4]),
            "ohlcv_2ms": _ohlcv_df([0, 2, 4], close_start=10.0),
        },
    )
    data = build_data_pack(
        source=source,
        base_data_key="ohlcv_1ms",
        ranges={
            "ohlcv_1ms": SourceRange(warmup_bars=2, active_bars=3, pack_bars=5),
            "ohlcv_2ms": SourceRange(warmup_bars=1, active_bars=2, pack_bars=3),
        },
        skip_mask=pl.DataFrame({"skip": [False, True, False, False, True]}),
    )
    result = build_result_pack(
        data=data,
        indicators={"ohlcv_2ms": pl.DataFrame({"value": [10.0, 20.0, 30.0]})},
        signals=pl.DataFrame({"signal": [0, 0, 1, 1, 0]}),
        backtest_result=pl.DataFrame({"equity": [100.0, 101.0, 102.0, 103.0, 104.0]}),
        performance={"total_return": 0.04},
    )
    return data, result


def test_extract_active_rebases_mapping_and_preserves_performance():
    """extract_active(...) 必须切 active、重基 mapping、继承 performance。"""
    data, result = _build_data_and_result()

    new_data, new_result = extract_active(data, result)

    assert new_data.mapping["time"].to_list() == [2, 3, 4]
    assert new_result.mapping["time"].to_list() == [2, 3, 4]
    assert new_result.mapping["ohlcv_2ms"].to_list() == [0, 0, 1]
    assert new_result.base_data_key == new_data.base_data_key
    assert new_result.ranges["ohlcv_1ms"].pack_bars == new_result.mapping.height
    assert new_result.ranges["ohlcv_2ms"].pack_bars == 2
    assert new_result.performance == result.performance
    assert new_data.skip_mask is not None
    assert new_data.skip_mask["skip"].to_list() == [False, False, True]
    assert new_result.signals is not None
    assert new_result.signals.height == new_result.mapping.height
    assert new_result.backtest_result is not None
    assert new_result.backtest_result.height == new_result.mapping.height
    assert new_result.indicators is not None
    assert new_result.indicators["ohlcv_2ms"]["time"].to_list() == [2, 4]
    assert new_data.source["ohlcv_2ms"]["time"].to_list() == [2, 4]


def test_extract_active_rejects_mismatched_base_data_key():
    """DataPack / ResultPack 的 base_data_key 不一致时必须直接报错。"""
    data, result = _build_data_and_result()
    wrong_result = ResultPack(
        mapping=result.mapping,
        ranges=result.ranges,
        base_data_key="ohlcv_2ms",
        performance=result.performance,
        indicators=result.indicators,
        signals=result.signals,
        backtest_result=result.backtest_result,
    )

    with pytest.raises(ValueError, match="base_data_key 一致"):
        extract_active(data, wrong_result)


def test_extract_active_rejects_mismatched_base_ranges():
    """同源配对前若 base ranges 已漂移，extract_active(...) 必须拒绝执行。"""
    data, result = _build_data_and_result()
    wrong_ranges = dict(result.ranges)
    wrong_ranges["ohlcv_1ms"] = SourceRange(warmup_bars=1, active_bars=4, pack_bars=5)
    wrong_result = ResultPack(
        mapping=result.mapping,
        ranges=wrong_ranges,
        base_data_key=result.base_data_key,
        performance=result.performance,
        indicators=result.indicators,
        signals=result.signals,
        backtest_result=result.backtest_result,
    )

    with pytest.raises(ValueError, match="base ranges 不一致"):
        extract_active(data, wrong_result)
