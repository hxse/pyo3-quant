import polars as pl

from pyo3_quant import DataContainer
from pyo3_quant.backtest_engine.data_ops import (
    build_time_mapping,
    is_natural_mapping_column,
    slice_data_container,
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
    # 中文注释：base 1m，HTF 5m，验证 Rust 端映射语义与自然序列判定。
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    raw_data = DataContainer(
        mapping=pl.DataFrame({}),
        skip_mask=None,
        source={"ohlcv_1m": base_df, "ohlcv_5m": htf_df},
        base_data_key="ohlcv_1m",
    )

    mapped = build_time_mapping(raw_data)

    assert mapped.mapping.columns == ["ohlcv_1m", "ohlcv_5m"]
    assert mapped.mapping["ohlcv_1m"].to_list() == [0, 1, 2, 3, 4]
    assert mapped.mapping["ohlcv_5m"].to_list() == [0, 0, 1, 1, 2]
    assert is_natural_mapping_column(mapped, "ohlcv_1m") is True
    assert is_natural_mapping_column(mapped, "ohlcv_5m") is False


def test_slice_data_container_rebases_mapping_for_window():
    # 中文注释：窗口切片后，base 与 HTF 的 source 和 mapping 都应切到窗口局部索引。
    base_df = _build_source_df([0, 1, 2, 3, 4], [10, 11, 12, 13, 14])
    htf_df = _build_source_df([0, 2, 4], [20, 21, 22])
    raw_data = DataContainer(
        mapping=pl.DataFrame({}),
        skip_mask=None,
        source={"ohlcv_1m": base_df, "ohlcv_5m": htf_df},
        base_data_key="ohlcv_1m",
    )
    mapped = build_time_mapping(raw_data)

    sliced = slice_data_container(mapped, start=1, length=3)

    assert sliced.source["ohlcv_1m"]["time"].to_list() == [1, 2, 3]
    assert sliced.source["ohlcv_5m"]["time"].to_list() == [0, 2]
    assert sliced.mapping["ohlcv_1m"].to_list() == [0, 1, 2]
    assert sliced.mapping["ohlcv_5m"].to_list() == [0, 1, 1]


def test_build_time_mapping_align_to_base_range_keeps_predecessor_for_backward_asof():
    # 中文注释：source 超出 base 时间范围时，默认对齐并保留前置一根，避免 backward asof 剪过头。
    base_df = _build_source_df([10, 11, 12], [10, 11, 12])
    src_df = _build_source_df([8, 9, 10, 11, 12, 13], [1, 2, 3, 4, 5, 6])
    raw_data = DataContainer(
        mapping=pl.DataFrame({}),
        skip_mask=None,
        source={"ohlcv_1m": base_df, "ohlcv_5m": src_df},
        base_data_key="ohlcv_1m",
    )

    mapped_aligned = build_time_mapping(raw_data, align_to_base_range=True)
    # 中文注释：显式开启对齐后，source 会被裁到 [base_start, base_end] 并保留一根前置（9）。
    assert mapped_aligned.source["ohlcv_5m"]["time"].to_list() == [9, 10, 11, 12]
    assert mapped_aligned.mapping["ohlcv_5m"].to_list() == [1, 2, 3]


def test_build_time_mapping_can_disable_align_to_base_range():
    # 中文注释：显式关闭对齐时，保留 source 原始时间范围。
    base_df = _build_source_df([10, 11, 12], [10, 11, 12])
    src_df = _build_source_df([8, 9, 10, 11, 12, 13], [1, 2, 3, 4, 5, 6])
    raw_data = DataContainer(
        mapping=pl.DataFrame({}),
        skip_mask=None,
        source={"ohlcv_1m": base_df, "ohlcv_5m": src_df},
        base_data_key="ohlcv_1m",
    )

    mapped_no_align = build_time_mapping(raw_data, align_to_base_range=False)
    assert mapped_no_align.source["ohlcv_5m"]["time"].to_list() == [
        8,
        9,
        10,
        11,
        12,
        13,
    ]
    assert mapped_no_align.mapping["ohlcv_5m"].to_list() == [2, 3, 4]
