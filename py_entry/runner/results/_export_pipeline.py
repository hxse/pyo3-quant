from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from pyo3_quant.backtest_engine.data_ops import (
    build_data_pack,
    build_result_pack,
    strip_indicator_time_columns,
)
from py_entry.charts.generation import generate_default_chart_config
from py_entry.io._converters_serialization import convert_to_serializable
from py_entry.io._converters_serialization import dumps_json_bytes
from py_entry.io.zip_utils import create_zip_buffer
from py_entry.io.dataframe_utils import add_contextual_columns_to_dataframes
from py_entry.runner.params import FormatResultsConfig
from py_entry.runner.results.prepared_export_bundle import PreparedExportBundle
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.types import ResultPack, SingleParamSet

if TYPE_CHECKING:
    import polars as pl

    from py_entry.io import ParquetCompression
    from py_entry.types import ChartConfig, DataPack


@dataclass(slots=True)
class ExportPayload:
    """标准化导出负载。"""

    data_frames: dict[str, Any]
    json_dicts: dict[str, dict | list]
    chart_config: "ChartConfig | None" = None


def _clone_optional_df(df: "pl.DataFrame | None") -> "pl.DataFrame | None":
    """克隆可选 DataFrame。"""
    if df is None:
        return None
    return df.clone()


def copy_data_pack_for_export(pack: "DataPack") -> "DataPack":
    """通过正式 producer 深拷贝 DataPack。"""
    ranges = {k: v for k, v in pack.ranges.items()}
    skip_mask = _clone_optional_df(pack.skip_mask)
    source = {k: v.clone() for k, v in pack.source.items()}
    return build_data_pack(
        source=source,
        base_data_key=pack.base_data_key,
        ranges=ranges,
        skip_mask=skip_mask,
    )


def copy_result_pack_for_export(
    data_pack: "DataPack", result: ResultPack
) -> ResultPack:
    """通过正式 producer 深拷贝 ResultPack。"""
    indicators = None
    if result.indicators is not None:
        indicators = strip_indicator_time_columns(
            {k: v.clone() for k, v in result.indicators.items()}
        )
    signals = _clone_optional_df(result.signals)
    backtest_result = _clone_optional_df(result.backtest_result)
    performance = dict(result.performance) if result.performance is not None else None
    return build_result_pack(
        data=data_pack,
        performance=performance,
        indicators=indicators,
        signals=signals,
        backtest_result=backtest_result,
    )


def _build_chart_config(
    export_data_snapshot: Any,
    export_result_snapshot: Any,
    *,
    params: SingleParamSet | None,
    backtest_schedule: list[Any] | None,
    config: FormatResultsConfig,
) -> "ChartConfig | None":
    """按统一规则生成导出 chart config。"""
    if config.chart_config is not None:
        return config.chart_config
    chart_params = None if backtest_schedule is not None else params
    return generate_default_chart_config(
        export_data_snapshot,
        export_result_snapshot,
        chart_params,
        config.dataframe_format,
        config.indicator_layout,
    )


def _dataframe_to_buffer(
    df: Any,
    dataframe_format: str,
    parquet_compression: "ParquetCompression",
) -> io.BytesIO:
    """统一把 DataFrame 写入 buffer。"""
    buf = io.BytesIO()
    if dataframe_format == "csv":
        df.write_csv(buf)
    else:
        df.write_parquet(buf, compression=parquet_compression)
    return buf


def package_export_payload(
    payload: ExportPayload,
    *,
    dataframe_format: str,
    parquet_compression: "ParquetCompression",
    compress_level: int,
    enable_timing: bool = False,
) -> PreparedExportBundle:
    """将导出负载打成正式 bundle。"""
    start_time = time.perf_counter() if enable_timing else None
    buffers: list[tuple[Path, io.BytesIO]] = []
    for path, df in payload.data_frames.items():
        buffers.append(
            (
                Path(path),
                _dataframe_to_buffer(df, dataframe_format, parquet_compression),
            )
        )
    for path, obj in payload.json_dicts.items():
        buffers.append((Path(path), io.BytesIO(dumps_json_bytes(obj))))
    if payload.chart_config is not None:
        buffers.append(
            (
                Path("chartConfig.json"),
                io.BytesIO(
                    dumps_json_bytes(convert_to_serializable(payload.chart_config))
                ),
            )
        )
    zip_buffer = create_zip_buffer(buffers, compress_level=compress_level)
    if enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"package_export_payload() 耗时: {elapsed:.4f}秒")
    return PreparedExportBundle(
        buffers=buffers,
        zip_buffer=zip_buffer,
        chart_config=payload.chart_config,
        enable_timing=enable_timing,
    )


def _build_single_export_payload(
    *,
    session: RunnerSession,
    result: ResultPack,
    params: SingleParamSet,
    config: FormatResultsConfig,
) -> ExportPayload:
    """构造 single export payload。"""
    export_data = copy_data_pack_for_export(session.data_pack)
    export_result = copy_result_pack_for_export(export_data, result)
    export_data_snapshot, export_result_snapshot = add_contextual_columns_to_dataframes(
        export_data,
        export_result,
        config.add_index,
        config.add_time,
        config.add_date,
    )
    if export_data_snapshot is None:
        raise ValueError("single export 失败：export_data_snapshot 不能为空")
    chart_config = _build_chart_config(
        export_data_snapshot,
        export_result_snapshot,
        params=params,
        backtest_schedule=None,
        config=config,
    )
    data_frames: dict[str, Any] = {}
    json_dicts: dict[str, dict | list] = {}
    if export_result_snapshot.indicators is not None:
        for key, df in export_result_snapshot.indicators.items():
            data_frames[
                f"backtest_results/indicators_{key}.{config.dataframe_format}"
            ] = df
    if export_result_snapshot.signals is not None:
        data_frames[f"backtest_results/signals.{config.dataframe_format}"] = (
            export_result_snapshot.signals
        )
    if export_result_snapshot.backtest_result is not None:
        data_frames[f"backtest_results/backtest_result.{config.dataframe_format}"] = (
            export_result_snapshot.backtest_result
        )
    if export_result_snapshot.performance is not None:
        json_dicts["backtest_results/performance.json"] = (
            export_result_snapshot.performance
        )
    data_frames[f"data_pack/mapping.{config.dataframe_format}"] = (
        export_data_snapshot.mapping
    )
    if export_data_snapshot.skip_mask is not None:
        data_frames[f"data_pack/skip_mask.{config.dataframe_format}"] = (
            export_data_snapshot.skip_mask
        )
    for key, df in export_data_snapshot.source.items():
        data_frames[f"data_pack/source_{key}.{config.dataframe_format}"] = df
    json_dicts["data_pack/base_data_key.json"] = {
        "base_data_key": export_data_snapshot.base_data_key
    }
    json_dicts["param_set/param.json"] = {
        "indicators": convert_to_serializable(params.indicators),
        "signal": convert_to_serializable(params.signal),
        "backtest": convert_to_serializable(params.backtest),
        "performance": {
            "metrics": [str(metric) for metric in params.performance.metrics]
        },
    }
    json_dicts["template_config/template_config.json"] = {
        "entry_long": convert_to_serializable(
            session.template_config.signal.entry_long
        ),
        "exit_long": convert_to_serializable(session.template_config.signal.exit_long),
        "entry_short": convert_to_serializable(
            session.template_config.signal.entry_short
        ),
        "exit_short": convert_to_serializable(
            session.template_config.signal.exit_short
        ),
    }
    json_dicts["engine_settings/engine_settings.json"] = {
        "stop_stage": convert_to_serializable(session.engine_settings.stop_stage),
        "artifact_retention": convert_to_serializable(
            session.engine_settings.artifact_retention
        ),
    }
    return ExportPayload(
        data_frames=data_frames,
        json_dicts=json_dicts,
        chart_config=chart_config,
    )


def _build_walk_forward_export_payload(
    *,
    session: RunnerSession,
    stitched_data: Any,
    stitched_result: ResultPack,
    backtest_schedule: list[Any],
    config: FormatResultsConfig,
) -> ExportPayload:
    """构造 WF stitched export payload。"""
    export_data = copy_data_pack_for_export(stitched_data)
    export_result = copy_result_pack_for_export(export_data, stitched_result)
    export_data_snapshot, export_result_snapshot = add_contextual_columns_to_dataframes(
        export_data,
        export_result,
        config.add_index,
        config.add_time,
        config.add_date,
    )
    if export_data_snapshot is None:
        raise ValueError("WF export 失败：export_data_snapshot 不能为空")
    chart_config = _build_chart_config(
        export_data_snapshot,
        export_result_snapshot,
        params=None,
        backtest_schedule=backtest_schedule,
        config=config,
    )
    data_frames: dict[str, Any] = {}
    json_dicts: dict[str, dict | list] = {}
    if export_result_snapshot.indicators is not None:
        for key, df in export_result_snapshot.indicators.items():
            data_frames[
                f"backtest_results/indicators_{key}.{config.dataframe_format}"
            ] = df
    if export_result_snapshot.signals is not None:
        data_frames[f"backtest_results/signals.{config.dataframe_format}"] = (
            export_result_snapshot.signals
        )
    if export_result_snapshot.backtest_result is not None:
        data_frames[f"backtest_results/backtest_result.{config.dataframe_format}"] = (
            export_result_snapshot.backtest_result
        )
    if export_result_snapshot.performance is not None:
        json_dicts["backtest_results/performance.json"] = (
            export_result_snapshot.performance
        )
    data_frames[f"data_pack/mapping.{config.dataframe_format}"] = (
        export_data_snapshot.mapping
    )
    if export_data_snapshot.skip_mask is not None:
        data_frames[f"data_pack/skip_mask.{config.dataframe_format}"] = (
            export_data_snapshot.skip_mask
        )
    for key, df in export_data_snapshot.source.items():
        data_frames[f"data_pack/source_{key}.{config.dataframe_format}"] = df
    json_dicts["data_pack/base_data_key.json"] = {
        "base_data_key": export_data_snapshot.base_data_key
    }
    json_dicts["backtest_schedule/backtest_schedule.json"] = convert_to_serializable(
        backtest_schedule
    )
    json_dicts["template_config/template_config.json"] = {
        "entry_long": convert_to_serializable(
            session.template_config.signal.entry_long
        ),
        "exit_long": convert_to_serializable(session.template_config.signal.exit_long),
        "entry_short": convert_to_serializable(
            session.template_config.signal.entry_short
        ),
        "exit_short": convert_to_serializable(
            session.template_config.signal.exit_short
        ),
    }
    json_dicts["engine_settings/engine_settings.json"] = {
        "stop_stage": convert_to_serializable(session.engine_settings.stop_stage),
        "artifact_retention": convert_to_serializable(
            session.engine_settings.artifact_retention
        ),
    }
    return ExportPayload(
        data_frames=data_frames,
        json_dicts=json_dicts,
        chart_config=chart_config,
    )


def prepare_single_export_bundle(
    *,
    session: RunnerSession,
    result: ResultPack,
    params: SingleParamSet,
    config: FormatResultsConfig,
) -> PreparedExportBundle:
    """single view 的正式导出入口。"""
    payload = _build_single_export_payload(
        session=session,
        result=result,
        params=params,
        config=config,
    )
    return package_export_payload(
        payload,
        dataframe_format=config.dataframe_format,
        parquet_compression=config.parquet_compression,
        compress_level=config.compress_level,
        enable_timing=session.enable_timing,
    )


def prepare_walk_forward_export_bundle(
    *,
    session: RunnerSession,
    stitched_data: Any,
    stitched_result: ResultPack,
    backtest_schedule: list[Any],
    config: FormatResultsConfig,
) -> PreparedExportBundle:
    """WF view 的正式导出入口。"""
    payload = _build_walk_forward_export_payload(
        session=session,
        stitched_data=stitched_data,
        stitched_result=stitched_result,
        backtest_schedule=backtest_schedule,
        config=config,
    )
    return package_export_payload(
        payload,
        dataframe_format=config.dataframe_format,
        parquet_compression=config.parquet_compression,
        compress_level=config.compress_level,
        enable_timing=session.enable_timing,
    )
