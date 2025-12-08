"""结果导出工具函数

提供将回测结果保存到磁盘和上传到服务器的高级函数。
"""

from pathlib import Path
from py_entry.data_conversion.types import BacktestSummary
from .configs import ResultBuffersCache, SaveConfig, UploadConfig
from .path_utils import validate_output_path, clear_directory
from .savers import save_buffers_to_disk
from .upload import upload_to_server
import time


def save_backtest_results(
    results: list[BacktestSummary],
    config: SaveConfig,
    cache: ResultBuffersCache,
) -> None:
    """保存所有回测数据（包括配置和结果）到本地文件。

    注意：
    1. 调用者应确保 cache 中已存在对应格式的buffers。
    2. 保存前会自动清空目录。
    3. 输出目录必须在项目根目录的 data/output 文件夹下。
    4. 缓存中的buffers应包含所有回测数据（data_dict, param_set, template_config, engine_settings, results）。

    Args:
        results: 回测结果列表（保留参数以保持向后兼容性）
        config: 保存配置
        cache: 缓存对象，必须已包含对应格式的buffers
    """
    # 从缓存获取buffers
    buffers = cache.get(config.dataframe_format)
    assert buffers is not None, (
        f"缓存中未找到 {config.dataframe_format} 格式的buffers。"
        "请确保在调用此函数前已调用 convert_all_backtest_data_to_buffers()。"
    )

    # 验证并获取完整路径
    validated_path = validate_output_path(config.output_dir)

    # 清空目录（总是执行）
    if validated_path.exists():
        print(f"清空目录: {validated_path}")
        clear_directory(validated_path, keep_dir=True)

    # 保存
    save_buffers_to_disk(buffers, validated_path)


def upload_backtest_results(
    results: list[BacktestSummary],
    config: UploadConfig,
    cache: ResultBuffersCache,
    zip_data: bytes,
) -> None:
    """上传所有回测数据（包括配置和结果）到服务器。

    Args:
        results: 回测结果列表（保留参数以保持向后兼容性）
        config: 上传配置
        cache: 缓存对象，必须已包含对应格式的buffers
        zip_data: ZIP字节数据，必须提供
    """

    # 保存到本地用于调试

    timestamp = int(time.time())
    final_zip_name = config.zip_name or f"backtest_results_{timestamp}.zip"

    upload_to_server(
        config=config.request_config,
        zip_data=zip_data,
        server_dir=Path(config.server_dir) if config.server_dir else None,
        zip_name=final_zip_name,
    )
