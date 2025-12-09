import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner

from py_entry.data_conversion.file_utils import (
    SaveConfig,
    UploadConfig,
    convert_all_backtest_data_to_buffers,
    save_backtest_results,
    upload_backtest_results,
    ParquetCompression,
)
from py_entry.data_conversion.file_utils.dataframe_utils import (
    add_contextual_columns_to_all_dataframes,
)
from py_entry.data_conversion.file_utils.zip_utils import create_zip_buffer


def _ensure_buffers_cache(
    self: "BacktestRunner",
    dataframe_format: str,
    parquet_compression: ParquetCompression,
) -> None:
    """
    确保指定格式的buffers已缓存。

    Args:
        self: BacktestRunner 实例。
        dataframe_format: 需要的格式 ("csv" 或 "parquet")
        parquet_compression: Parquet 压缩算法
    """
    # 检查是否已缓存
    if self._buffers_cache.get(dataframe_format) is None:
        # 转换并缓存
        assert self.results is not None, (
            "_ensure_buffers_cache 方法要求 self.results 非空，"
            "但当前为 None。请确保在调用此方法前已执行 run() 方法。"
        )
        buffers = convert_all_backtest_data_to_buffers(
            self.data_dict,
            self.param_set,
            self.template_config,
            self.engine_settings,
            self.results,
            dataframe_format,
            parquet_compression=parquet_compression,
        )
        self._buffers_cache.set(dataframe_format, buffers)


def save_results(self: "BacktestRunner", config: SaveConfig) -> None:
    """
    保存所有回测数据（包括配置和结果）到本地文件。

    Args:
        self: BacktestRunner 实例。
        config: 保存配置对象
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.results is None:
        raise ValueError("必须先调用 run() 执行回测")

    # 确保缓存
    _ensure_buffers_cache(self, config.dataframe_format, config.parquet_compression)

    # 调用工具函数保存结果
    save_backtest_results(
        results=self.results,
        config=config,
        cache=self._buffers_cache,
    )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.save_results() 耗时: {elapsed:.4f}秒")


def upload_results(self: "BacktestRunner", config: UploadConfig) -> None:
    """
    将所有回测数据（包括配置和结果）打包并上传到服务器。

    Args:
        self: BacktestRunner 实例。
        config: 上传配置对象
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.results is None:
        raise ValueError("必须先调用 run() 执行回测")

    # 获取ZIP buffer并上传结果
    zip_data = get_zip_buffer(
        self,
        dataframe_format=config.dataframe_format,
        compress_level=config.compress_level,
        parquet_compression=config.parquet_compression,
    )

    upload_backtest_results(
        results=self.results,
        config=config,
        cache=self._buffers_cache,
        zip_data=zip_data,
    )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.upload_results() 耗时: {elapsed:.4f}秒")


def get_zip_buffer(
    self: "BacktestRunner",
    dataframe_format: str,
    compress_level: int,
    parquet_compression: ParquetCompression,
) -> bytes:
    """
    获取回测结果的ZIP压缩包字节数据。

    Args:
        self: BacktestRunner 实例。
        dataframe_format: DataFrame格式，"csv" 或 "parquet"
        compress_level: 压缩级别，0-9
        parquet_compression: Parquet 压缩算法，默认 "snappy"

    Returns:
        bytes: ZIP压缩包的字节数据
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.results is None:
        raise ValueError("必须先调用 run() 执行回测")

    # 确保缓存
    _ensure_buffers_cache(self, dataframe_format, parquet_compression)

    # 从缓存获取buffers
    buffers = self._buffers_cache.get(dataframe_format)
    assert buffers is not None, (
        f"缓存中未找到 {dataframe_format} 格式的buffers。"
        "请确保在调用此方法前已执行 run() 方法。"
    )

    # 创建ZIP buffer
    zip_data = create_zip_buffer(buffers, compress_level=compress_level)

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.get_zip_buffer() 耗时: {elapsed:.4f}秒")

    return zip_data


def format_results_for_export(
    self: "BacktestRunner",
    add_index: bool,
    add_time: bool,
    add_date: bool,
) -> None:
    """
    为所有 DataFrame 添加列。

    Args:
        self: BacktestRunner 实例。
        add_index: 是否添加索引列
        add_time: 是否添加时间列
        add_date: 是否添加日期列（ISO格式）
    """
    start_time = time.perf_counter() if self.enable_timing else None

    # 使用工具函数处理所有 DataFrame
    add_contextual_columns_to_all_dataframes(
        self.data_dict, self.results, add_index, add_time, add_date
    )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.format_results_for_export() 耗时: {elapsed:.4f}秒")
