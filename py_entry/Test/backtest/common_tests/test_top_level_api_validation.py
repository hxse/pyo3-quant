import polars as pl
import pytest

import pyo3_quant
from py_entry.types import SourceRange


def _build_source_df(times: list[int]) -> pl.DataFrame:
    """构造最小 OHLCV 结构，确保 producer 可直接读取 time 列并判定周期。"""
    n = len(times)
    closes = [float(i + 1) for i in range(n)]
    return pl.DataFrame(
        {
            "time": times,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1.0] * n,
        }
    )


def test_build_data_pack_rejects_base_not_smallest_interval():
    """Stage 1 之后，非法 base 周期必须在 producer 层就失败。"""
    base_df = _build_source_df([0, 300_000, 600_000])
    finer_df = _build_source_df([0, 60_000, 120_000, 180_000])

    with pytest.raises(ValueError, match="base_data_key 必须是最小周期"):
        pyo3_quant.backtest_engine.data_ops.build_data_pack(
            source={"ohlcv_5m": base_df, "ohlcv_1m": finer_df},
            base_data_key="ohlcv_5m",
            ranges={
                "ohlcv_5m": SourceRange(0, base_df.height, base_df.height),
                "ohlcv_1m": SourceRange(0, finer_df.height, finer_df.height),
            },
            skip_mask=None,
        )


def test_build_time_mapping_rejects_base_not_smallest_interval():
    """不带显式 ranges 的 producer 入口也必须在构造时失败。"""
    base_df = _build_source_df([0, 300_000, 600_000])
    finer_df = _build_source_df([0, 60_000, 120_000, 180_000])

    with pytest.raises(ValueError, match="base_data_key 必须是最小周期"):
        pyo3_quant.backtest_engine.data_ops.build_time_mapping(
            source={"ohlcv_5m": base_df, "ohlcv_1m": finer_df},
            base_data_key="ohlcv_5m",
            skip_mask=None,
        )
