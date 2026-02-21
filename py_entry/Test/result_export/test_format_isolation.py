from py_entry.runner import FormatResultsConfig


def _snapshot_columns(runner_with_results) -> dict[str, object]:
    """采集导出前/后的关键列快照，验证是否污染原始计算态对象。"""
    data_source_cols = {
        key: tuple(df.columns)
        for key, df in runner_with_results.data_dict.source.items()
    }
    indicator_cols = (
        {
            key: tuple(df.columns)
            for key, df in (runner_with_results.summary.indicators or {}).items()
        }
        if runner_with_results.summary.indicators is not None
        else None
    )
    signal_cols = (
        tuple(runner_with_results.summary.signals.columns)
        if runner_with_results.summary.signals is not None
        else None
    )
    backtest_cols = (
        tuple(runner_with_results.summary.backtest_result.columns)
        if runner_with_results.summary.backtest_result is not None
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
    assert before == after, "format_for_export 不应污染原始 data_dict/summary 列结构"


def test_format_for_export_still_generates_export_artifacts(runner_with_results):
    """副本导出模式下仍应正常产出导出缓存和图表配置。"""
    runner_with_results.format_for_export(FormatResultsConfig(dataframe_format="csv"))
    assert runner_with_results.export_buffers is not None
    assert runner_with_results.export_zip_buffer is not None
    assert runner_with_results.chart_config is not None
