"""D1 窗口切片契约测试。"""

from __future__ import annotations

import polars as pl

from pyo3_quant.backtest_engine.data_ops import (
    build_data_pack,
    build_result_pack,
    build_time_mapping,
    slice_data_pack,
    slice_result_pack,
)
from py_entry.types import SourceRange


def _build_source_df(times: list[int], closes: list[float]) -> pl.DataFrame:
    """构造最小 OHLCV DataFrame。"""
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


def test_window_slice_contract_slices_skip_mask_with_base_axis():
    """窗口切片后，skip_mask 必须与新的 base 轴严格对齐。"""
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    mapped = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
        base_data_key="ohlcv_1ms",
        skip_mask=pl.DataFrame({"skip": [False, True, False, True, False]}),
    )

    sliced = slice_data_pack(mapped, start=1, length=3)

    assert sliced.skip_mask is not None
    assert sliced.source["ohlcv_1ms"]["time"].to_list() == [1, 2, 3]
    assert sliced.skip_mask["skip"].to_list() == [True, False, True]
    assert sliced.skip_mask.height == sliced.source["ohlcv_1ms"].height


def test_window_slice_contract_keeps_left_predecessor_for_coverage():
    """窗口左侧映射需要 predecessor 时，切片后的 source 必须保留它。"""
    base_df = _build_source_df([10, 11, 12], [10, 11, 12])
    src_df = _build_source_df([9, 12], [20, 21])
    mapped = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_3ms": src_df},
        base_data_key="ohlcv_1ms",
    )

    sliced = slice_data_pack(mapped, start=1, length=2)

    # 中文注释：base 窗口已经从 11 开始，但高周期 source 仍需保留 9 作为左侧 predecessor。
    assert sliced.source["ohlcv_1ms"]["time"].to_list() == [11, 12]
    assert sliced.source["ohlcv_3ms"]["time"].to_list() == [9, 12]
    assert sliced.mapping["ohlcv_3ms"].to_list() == [0, 1]


def test_window_slice_contract_preserves_projected_warmup_ranges():
    """公开切片入口必须保留按当前 DataPack.ranges 推导出的 warmup 真值。"""
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    src_df = _build_source_df([-3, 0, 3], [20, 21, 22])
    data_pack = build_data_pack(
        source={"ohlcv_1ms": base_df, "ohlcv_3ms": src_df},
        base_data_key="ohlcv_1ms",
        ranges={
            "ohlcv_1ms": SourceRange(warmup_bars=2, active_bars=3, pack_bars=5),
            "ohlcv_3ms": SourceRange(warmup_bars=0, active_bars=3, pack_bars=3),
        },
    )

    sliced = slice_data_pack(data_pack, start=0, length=5)

    # 中文注释：公开 slice_data_pack(...) 只消费当前 DataPack 自身的 ranges 真值，
    # 不会伪造 planner 内部未冻结的额外 predecessor。
    assert sliced.source["ohlcv_3ms"]["time"].to_list() == [0, 3]
    assert sliced.ranges["ohlcv_3ms"].warmup_bars == 0
    assert sliced.ranges["ohlcv_3ms"].active_bars == 2
    assert sliced.ranges["ohlcv_3ms"].pack_bars == 2


def test_result_slice_contract_preserves_mapping_subset_without_indicators():
    """无指标 ResultPack 切片后，mapping 仍只能保留 time。"""
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    data_pack = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
        base_data_key="ohlcv_1ms",
    )
    result_pack = build_result_pack(data=data_pack)

    sliced = slice_result_pack(result_pack, data_pack, start=1, length=3)

    assert sliced.mapping.columns == ["time"]
    assert set(sliced.ranges) == {"ohlcv_1ms"}
    assert sliced.ranges["ohlcv_1ms"].warmup_bars == 0
    assert sliced.ranges["ohlcv_1ms"].active_bars == 3


def test_result_slice_contract_supports_indicator_subset():
    """只有子集 indicators 时，ResultPack 切片不能假装覆盖全部 source。"""
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    data_pack = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
        base_data_key="ohlcv_1ms",
    )
    result_pack = build_result_pack(
        data=data_pack,
        indicators={"ohlcv_2ms": pl.DataFrame({"value": [1.0, 2.0, 3.0]})},
    )

    sliced = slice_result_pack(result_pack, data_pack, start=1, length=3)

    assert sliced.mapping.columns == ["time", "ohlcv_2ms"]
    assert sliced.mapping["ohlcv_2ms"].to_list() == [0, 1, 1]
    assert sliced.indicators is not None
    assert sliced.indicators["ohlcv_2ms"]["time"].to_list() == [0, 2]
    assert set(sliced.ranges) == {"ohlcv_1ms", "ohlcv_2ms"}
