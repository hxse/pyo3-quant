import polars as pl
import pytest

from pyo3_quant.backtest_engine.data_ops import (
    build_time_mapping,
    is_natural_mapping_column,
    slice_data_pack,
)


def _build_source_df(times: list[int], closes: list[float]) -> pl.DataFrame:
    # 中文注释：测试用最小 OHLCV 结构，time 列为映射/切片核心。
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


def test_build_time_mapping_includes_base_and_htf_mapping():
    # 中文注释：base 1ms，HTF 2ms，验证 Rust 端映射语义与自然序列判定。
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])

    mapped = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
        base_data_key="ohlcv_1ms",
    )

    assert mapped.mapping.columns == ["time", "ohlcv_1ms", "ohlcv_2ms"]
    assert mapped.mapping["ohlcv_1ms"].to_list() == [0, 1, 2, 3, 4]
    assert mapped.mapping["ohlcv_2ms"].to_list() == [0, 0, 1, 1, 2]
    assert is_natural_mapping_column(mapped, "ohlcv_1ms") is True
    assert is_natural_mapping_column(mapped, "ohlcv_2ms") is False


def test_slice_data_pack_rebases_mapping_for_window():
    # 中文注释：窗口切片后，base 与 HTF 的 source 和 mapping 都应切到窗口局部索引。
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    mapped = build_time_mapping(
        source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
        base_data_key="ohlcv_1ms",
    )

    sliced = slice_data_pack(mapped, start=1, length=3)

    assert sliced.source["ohlcv_1ms"]["time"].to_list() == [1, 2, 3]
    assert sliced.source["ohlcv_2ms"]["time"].to_list() == [0, 2]
    assert sliced.mapping["ohlcv_1ms"].to_list() == [0, 1, 2]
    assert sliced.mapping["ohlcv_2ms"].to_list() == [0, 1, 1]


def test_build_time_mapping_align_to_base_range_keeps_predecessor_for_asof_mapping():
    # 中文注释：source 超出 base 时间范围时，默认对齐并保留前置一根，避免前序 asof 剪过头。
    base_df = _build_source_df([10, 11, 12], [10, 11, 12])
    src_df = _build_source_df([8, 9, 10, 11, 12, 13], [1, 2, 3, 4, 5, 6])

    mapped_aligned = build_time_mapping(
        source={"ohlcv_1ms": base_df, "htf_1ms": src_df},
        base_data_key="ohlcv_1ms",
        align_to_base_range=True,
    )

    # 中文注释：显式开启对齐后，source 会被裁到 [base_start, base_end] 并保留一根前置（9）。
    assert mapped_aligned.source["htf_1ms"]["time"].to_list() == [9, 10, 11, 12]
    assert mapped_aligned.mapping["htf_1ms"].to_list() == [1, 2, 3]


def test_build_time_mapping_can_disable_align_to_base_range():
    # 中文注释：显式关闭对齐时，保留 source 原始时间范围。
    base_df = _build_source_df([10, 11, 12], [10, 11, 12])
    src_df = _build_source_df([8, 9, 10, 11, 12, 13], [1, 2, 3, 4, 5, 6])

    mapped_no_align = build_time_mapping(
        source={"ohlcv_1ms": base_df, "htf_1ms": src_df},
        base_data_key="ohlcv_1ms",
        align_to_base_range=False,
    )
    assert mapped_no_align.source["htf_1ms"]["time"].to_list() == [
        8,
        9,
        10,
        11,
        12,
        13,
    ]
    assert mapped_no_align.mapping["htf_1ms"].to_list() == [2, 3, 4]


def test_build_time_mapping_rejects_base_not_smallest_interval():
    # 中文注释：base=5m，但存在 1m source，必须直接报错而不是继续构建映射。
    base_df = _build_source_df([0, 300_000, 600_000], [10, 11, 12])
    finer_df = _build_source_df([0, 60_000, 120_000, 180_000], [20, 21, 22, 23])

    with pytest.raises(ValueError, match="base_data_key 必须是最小周期"):
        build_time_mapping(
            source={"ohlcv_5m": base_df, "ohlcv_1m": finer_df},
            base_data_key="ohlcv_5m",
        )


def test_build_time_mapping_rejects_source_time_finer_than_declared_period():
    # 中文注释：source 命名为 5m，但 time 最小正间隔为 1m，应直接报错。
    base_df = _build_source_df([0, 60_000, 120_000], [10, 11, 12])
    wrong_declared_df = _build_source_df([0, 60_000, 120_000], [20, 21, 22])

    with pytest.raises(ValueError, match="小于命名周期"):
        build_time_mapping(
            source={"ohlcv_1m": base_df, "ohlcv_5m": wrong_declared_df},
            base_data_key="ohlcv_1m",
        )


def test_build_time_mapping_align_to_base_range_allows_single_predecessor_source():
    # 中文注释：对齐裁剪后若高周期 source 只剩一根 predecessor，仍应允许通过。
    base_df = _build_source_df([900_000, 1_800_000], [10, 11])
    htf_df = _build_source_df([0, 3_600_000], [20, 21])

    mapped = build_time_mapping(
        source={"ohlcv_15m": base_df, "ohlcv_1h": htf_df},
        base_data_key="ohlcv_15m",
        align_to_base_range=True,
    )

    assert mapped.source["ohlcv_1h"]["time"].to_list() == [0]
    assert mapped.mapping["ohlcv_1h"].to_list() == [0, 0]


def test_build_time_mapping_rejects_non_standard_source_name():
    # 中文注释：全部 source key 都必须走统一 resolver，非标准命名必须 fail-fast。
    base_df = _build_source_df([0, 60_000, 120_000], [10, 11, 12])
    custom_df = _build_source_df([0, 90_000, 180_000], [20, 21, 22])

    with pytest.raises(ValueError, match="source_key 'test_data'.*非法"):
        build_time_mapping(
            source={"ohlcv_1m": base_df, "test_data": custom_df},
            base_data_key="ohlcv_1m",
        )


def test_build_time_mapping_rejects_non_standard_base_data_key():
    # 中文注释：base_data_key 必须命名规范，否则直接报错。
    base_df = _build_source_df([0, 60_000, 120_000], [10, 11, 12])

    with pytest.raises(ValueError, match="source_key 'test_data'.*非法"):
        build_time_mapping(
            source={"test_data": base_df},
            base_data_key="test_data",
        )


def test_build_time_mapping_rejects_duplicate_base_time():
    # 中文注释：TimeProjectionIndex 必须严格递增，重复时间戳不允许进入 mapping。
    base_df = _build_source_df([0, 1, 1, 2], [10, 11, 12, 13])
    htf_df = _build_source_df([0, 2], [20, 21])

    with pytest.raises(ValueError, match="严格递增"):
        build_time_mapping(
            source={"ohlcv_1ms": base_df, "ohlcv_2ms": htf_df},
            base_data_key="ohlcv_1ms",
        )
