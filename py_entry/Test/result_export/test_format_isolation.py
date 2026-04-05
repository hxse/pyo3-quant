import polars as pl

from py_entry.runner import FormatResultsConfig
from py_entry.runner.results.run_result import _copy_data_pack, _copy_result_pack


def _snapshot_columns(runner_with_results) -> dict[str, object]:
    """采集导出前/后的关键列快照，验证是否污染原始计算态对象。"""
    data_source_cols = {
        key: tuple(df.columns)
        for key, df in runner_with_results.data_pack.source.items()
    }
    indicator_cols = (
        {
            key: tuple(df.columns)
            for key, df in (runner_with_results.result.indicators or {}).items()
        }
        if runner_with_results.result.indicators is not None
        else None
    )
    signal_cols = (
        tuple(runner_with_results.result.signals.columns)
        if runner_with_results.result.signals is not None
        else None
    )
    backtest_cols = (
        tuple(runner_with_results.result.backtest_result.columns)
        if runner_with_results.result.backtest_result is not None
        else None
    )
    return {
        "data_source_cols": data_source_cols,
        "indicator_cols": indicator_cols,
        "signal_cols": signal_cols,
        "backtest_cols": backtest_cols,
    }


def test_format_for_export_does_not_mutate_original_dataframes(runner_with_results):
    """format_for_export 必须只操作导出副本，不得修改原始计算态 DataFrame 列结构。"""
    before = _snapshot_columns(runner_with_results)

    runner_with_results.format_for_export(FormatResultsConfig(dataframe_format="csv"))

    after = _snapshot_columns(runner_with_results)
    assert before == after, "format_for_export 不应污染原始 data_pack/result 列结构"


def test_format_for_export_still_generates_export_artifacts(runner_with_results):
    """副本导出模式下仍应正常产出导出缓存和图表配置。"""
    runner_with_results.format_for_export(FormatResultsConfig(dataframe_format="csv"))
    assert runner_with_results.export_buffers is not None
    assert runner_with_results.export_zip_buffer is not None
    assert runner_with_results.chart_config is not None


def test_copy_data_pack_returns_independent_dataframe_fields(runner_with_results):
    """_copy_data_pack(...) 返回的副本必须与原始 DataFrame 字段解耦。"""
    original = runner_with_results.data_pack
    copied = _copy_data_pack(original)

    copied.mapping = copied.mapping.with_columns(pl.lit(1).alias("__copy_only_mapping"))
    assert "__copy_only_mapping" not in original.mapping.columns

    if copied.skip_mask is not None:
        copied.skip_mask = copied.skip_mask.with_columns(
            pl.lit(False).alias("__copy_only_skip")
        )
        assert original.skip_mask is not None
        assert "__copy_only_skip" not in original.skip_mask.columns

    copied_source = copied.source
    base_key = copied.base_data_key
    copied_source[base_key] = copied_source[base_key].with_columns(
        pl.lit(1).alias("__copy_only_source")
    )
    copied.source = copied_source
    assert "__copy_only_source" not in original.source[base_key].columns


def test_copy_result_pack_returns_independent_payload_fields(runner_with_results):
    """_copy_result_pack(...) 返回的副本必须与原始结果 DataFrame / metrics 解耦。"""
    original = runner_with_results.result
    copied = _copy_result_pack(original)

    copied.mapping = copied.mapping.with_columns(pl.lit(1).alias("__copy_only_mapping"))
    assert "__copy_only_mapping" not in original.mapping.columns

    assert copied.signals is not None
    copied.signals = copied.signals.with_columns(pl.lit(1).alias("__copy_only_signal"))
    assert original.signals is not None
    assert "__copy_only_signal" not in original.signals.columns

    assert copied.backtest_result is not None
    copied.backtest_result = copied.backtest_result.with_columns(
        pl.lit(1.0).alias("__copy_only_backtest")
    )
    assert original.backtest_result is not None
    assert "__copy_only_backtest" not in original.backtest_result.columns

    if copied.indicators is not None:
        copied_indicators = copied.indicators
        first_key = next(iter(copied_indicators))
        copied_indicators[first_key] = copied_indicators[first_key].with_columns(
            pl.lit(1.0).alias("__copy_only_indicator")
        )
        copied.indicators = copied_indicators
        assert original.indicators is not None
        assert "__copy_only_indicator" not in original.indicators[first_key].columns

    copied_performance = copied.performance or {}
    copied_performance["__copy_only_metric"] = 123.0
    copied.performance = copied_performance
    assert "__copy_only_metric" not in (original.performance or {})
