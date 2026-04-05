import polars as pl
import pytest

import pyo3_quant
from py_entry.types import (
    DataPack,
    ExecutionStage,
    SettingContainer,
    SignalTemplate,
    SingleParamSet,
    SourceRange,
    TemplateContainer,
)


def _build_source_df(times: list[int]) -> pl.DataFrame:
    # 中文注释：构造最小 OHLCV 结构，确保入口校验可直接读取 time 列并判定周期。
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


def _build_invalid_data_base_not_smallest() -> DataPack:
    # 中文注释：base=5m，source 含 1m，故 base 不是最小周期，应被 top-level API 拦截。
    base_df = _build_source_df([0, 300_000, 600_000])
    finer_df = _build_source_df([0, 60_000, 120_000, 180_000])
    return DataPack(
        mapping=pl.DataFrame({}),
        skip_mask=None,
        source={"ohlcv_5m": base_df, "ohlcv_1m": finer_df},
        base_data_key="ohlcv_5m",
        ranges={
            "ohlcv_5m": SourceRange(0, base_df.height, base_df.height),
            "ohlcv_1m": SourceRange(0, finer_df.height, finer_df.height),
        },
    )


def _build_template_and_settings() -> tuple[TemplateContainer, SettingContainer]:
    # 中文注释：本测试只验证入口数据约束，模板与设置使用最小可构造对象即可。
    template = TemplateContainer(SignalTemplate())
    settings = SettingContainer(
        execution_stage=ExecutionStage.Indicator,
        return_only_final=False,
    )
    return template, settings


def test_run_backtest_engine_validates_base_smallest_interval_on_entry():
    data = _build_invalid_data_base_not_smallest()
    template, settings = _build_template_and_settings()

    with pytest.raises(ValueError, match="base_data_key 必须是最小周期"):
        pyo3_quant.backtest_engine.run_backtest_engine(
            data=data,
            params=[],
            template=template,
            engine_settings=settings,
        )


def test_run_single_backtest_validates_base_smallest_interval_on_entry():
    data = _build_invalid_data_base_not_smallest()
    template, settings = _build_template_and_settings()

    with pytest.raises(ValueError, match="base_data_key 必须是最小周期"):
        pyo3_quant.backtest_engine.run_single_backtest(
            data=data,
            param=SingleParamSet(),
            template=template,
            engine_settings=settings,
        )
