import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner
    from .params import FormatResultsConfig
    from py_entry.io import SaveConfig, UploadConfig

from py_entry.io import (
    convert_backtest_data_to_buffers,
    save_backtest_results,
    upload_backtest_results,
)
from py_entry.io.dataframe_utils import (
    add_contextual_columns_to_dataframes,
)
from py_entry.io.zip_utils import create_zip_buffer
from py_entry.charts.generation import (
    generate_default_chart_config,
)


def format_results_for_export(
    runner: "BacktestRunner",
    config: "FormatResultsConfig",
) -> None:
    """
    为导出准备单个回测结果的数据。
    """
    start_time = time.perf_counter() if runner.enable_timing else None

    # 1. 验证 results 和 param_set 不为空
    if not runner.results:
        raise ValueError("无回测结果可供导出。请先调用 run() 执行回测。")

    if not runner.param_set:
        raise ValueError("无参数集可供导出。请先调用 run() 执行回测。")

    # 2. 验证 export_index 有效性
    export_index = config.export_index
    if export_index < 0 or export_index >= len(runner.results):
        raise IndexError(
            f"export_index {export_index} 超出 results 范围。"
            f"有效范围: 0 到 {len(runner.results) - 1}"
        )

    if export_index >= len(runner.param_set):
        raise IndexError(
            f"export_index {export_index} 超出 param_set 范围。"
            f"有效范围: 0 到 {len(runner.param_set) - 1}"
        )

    # 3. 存储选中的索引
    runner.export_index = export_index

    # 4. 获取单个对象
    selected_result = runner.results[export_index]
    selected_param = runner.param_set[export_index]

    # 5. 为 DataFrame 添加上下文列
    add_contextual_columns_to_dataframes(
        runner.data_dict,
        selected_result,
        config.add_index,
        config.add_time,
        config.add_date,
    )

    # 6. ChartConfig
    if config.chart_config is not None:
        runner.chart_config = config.chart_config
    elif config.indicator_layout is not None:
        if runner.data_dict:
            runner.chart_config = generate_default_chart_config(
                runner.data_dict,
                selected_result,
                selected_param,
                config.dataframe_format,
                config.indicator_layout,
            )
    else:
        if runner.data_dict:
            runner.chart_config = generate_default_chart_config(
                runner.data_dict,
                selected_result,
                selected_param,
                config.dataframe_format,
            )

    # 7. Convert to buffers
    runner.export_buffers = convert_backtest_data_to_buffers(
        runner.data_dict,
        selected_param,
        runner.template_config,
        runner.engine_settings,
        selected_result,
        config.dataframe_format,
        config.parquet_compression,
        runner.chart_config,
    )

    # 8. Generate ZIP
    if runner.export_buffers:
        runner.export_zip_buffer = create_zip_buffer(
            runner.export_buffers, compress_level=config.compress_level
        )

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.format_results_for_export() 耗时: {elapsed:.4f}秒")


def save_results(runner: "BacktestRunner", config: "SaveConfig") -> None:
    """
    保存所有回测数据（包括配置和结果）到本地文件。
    """
    start_time = time.perf_counter() if runner.enable_timing else None

    if runner.export_buffers is None:
        raise ValueError(
            "未找到导出数据缓存。请先调用 format_results_for_export() 生成数据。"
        )

    # 调用工具函数保存结果
    save_backtest_results(
        buffers=runner.export_buffers,
        config=config,
    )

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.save_results() 耗时: {elapsed:.4f}秒")


def upload_results(runner: "BacktestRunner", config: "UploadConfig") -> None:
    """
    将所有回测数据（包括配置和结果）打包并上传到服务器。
    """
    start_time = time.perf_counter() if runner.enable_timing else None

    if runner.export_zip_buffer is None:
        raise ValueError(
            "未找到导出的ZIP数据。请先调用 format_results_for_export() 生成数据。"
        )

    upload_backtest_results(
        zip_data=runner.export_zip_buffer,
        config=config,
    )

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.upload_results() 耗时: {elapsed:.4f}秒")
