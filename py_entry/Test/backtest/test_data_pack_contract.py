"""A1 DataPack contract tests."""

from __future__ import annotations

import polars as pl
import pytest
from typing import cast

from pyo3_quant.backtest_engine.data_ops import build_data_pack
from py_entry.types import DataPack, SourceRange


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


def _valid_source() -> dict[str, object]:
    """构造最小多周期 source。"""
    source: dict[str, object] = {
        "ohlcv_1ms": _ohlcv_df([0, 1, 2]),
        "ohlcv_2ms": _ohlcv_df([0, 2], close_start=10.0),
    }
    return source


def _valid_ranges() -> dict[str, SourceRange]:
    """构造与 source 对齐的合法 ranges。"""
    return {
        "ohlcv_1ms": SourceRange(warmup_bars=1, active_bars=2, pack_bars=3),
        "ohlcv_2ms": SourceRange(warmup_bars=0, active_bars=2, pack_bars=2),
    }


def test_build_data_pack_preserves_mapping_and_range_contract():
    """build_data_pack(...) 必须产出 time-first 且 dtype 正确的 mapping。"""
    pack = build_data_pack(
        source=_valid_source(),
        base_data_key="ohlcv_1ms",
        ranges=_valid_ranges(),
    )

    assert cast(pl.DataFrame, pack.mapping).columns[0] == "time"
    assert set(cast(pl.DataFrame, pack.mapping).columns[1:]) == {
        "ohlcv_1ms",
        "ohlcv_2ms",
    }
    assert cast(pl.DataFrame, pack.mapping)["time"].dtype == pl.Int64
    assert cast(pl.DataFrame, pack.mapping)["ohlcv_1ms"].dtype == pl.UInt32
    assert cast(pl.DataFrame, pack.mapping)["ohlcv_2ms"].dtype == pl.UInt32
    assert cast(pl.DataFrame, pack.mapping)["time"].null_count() == 0
    assert cast(pl.DataFrame, pack.mapping)["ohlcv_1ms"].null_count() == 0
    assert cast(pl.DataFrame, pack.mapping)["ohlcv_2ms"].null_count() == 0
    assert (
        cast(pl.DataFrame, pack.mapping).height
        == cast(pl.DataFrame, pack.source["ohlcv_1ms"]).height
    )
    assert pack.ranges["ohlcv_1ms"].pack_bars == cast(pl.DataFrame, pack.mapping).height


@pytest.mark.parametrize(
    ("skip_mask", "expected_msg"),
    [
        (
            pl.DataFrame({"skip": [True, False, True], "other": [1, 2, 3]}),
            "skip_mask 必须是单列表 DataFrame",
        ),
        (
            pl.DataFrame({"other": [True, False, True]}),
            "唯一合法列名必须是 'skip'",
        ),
        (
            pl.DataFrame({"skip": [1, 0, 1]}),
            "dtype 必须是 Boolean",
        ),
        (
            pl.DataFrame({"skip": [True, None, False]}),
            "不允许存在 null",
        ),
        (
            pl.DataFrame({"skip": [True, False]}),
            "必须等于 base 高度 3",
        ),
    ],
)
def test_build_data_pack_rejects_invalid_skip_mask(
    skip_mask: pl.DataFrame,
    expected_msg: str,
):
    """skip_mask 结构非法时必须直接 fail-fast。"""
    with pytest.raises(ValueError, match=expected_msg):
        build_data_pack(
            source=_valid_source(),
            base_data_key="ohlcv_1ms",
            ranges=_valid_ranges(),
            skip_mask=skip_mask,
        )


@pytest.mark.parametrize(
    ("ranges", "expected_msg"),
    [
        (
            {"ohlcv_1ms": SourceRange(warmup_bars=1, active_bars=2, pack_bars=3)},
            "ranges 必须完整且仅覆盖全部 source keys",
        ),
        (
            {
                "ohlcv_1ms": SourceRange(warmup_bars=4, active_bars=0, pack_bars=3),
                "ohlcv_2ms": SourceRange(warmup_bars=0, active_bars=2, pack_bars=2),
            },
            "warmup_bars 不能大于 pack_bars",
        ),
        (
            {
                "ohlcv_1ms": SourceRange(warmup_bars=1, active_bars=1, pack_bars=3),
                "ohlcv_2ms": SourceRange(warmup_bars=0, active_bars=2, pack_bars=2),
            },
            "必须满足 warmup_bars \\+ active_bars == pack_bars",
        ),
        (
            {
                "ohlcv_1ms": SourceRange(warmup_bars=1, active_bars=3, pack_bars=4),
                "ohlcv_2ms": SourceRange(warmup_bars=0, active_bars=2, pack_bars=2),
            },
            "必须等于 source\\['ohlcv_1ms'\\]\\.height\\(\\)=3",
        ),
    ],
)
def test_build_data_pack_rejects_invalid_ranges(
    ranges: dict[str, SourceRange],
    expected_msg: str,
):
    """ranges 与 source 不一致时必须直接 fail-fast。"""
    with pytest.raises(ValueError, match=expected_msg):
        build_data_pack(
            source=_valid_source(),
            base_data_key="ohlcv_1ms",
            ranges=ranges,
        )
