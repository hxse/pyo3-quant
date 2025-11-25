"""结果导出工具函数

提供将回测结果保存到磁盘和上传到服务器的高级函数。
"""

from py_entry.data_conversion.types import BacktestSummary
from .configs import ResultBuffersCache, SaveConfig, UploadConfig
from .path_utils import validate_output_path, clear_directory
from .savers import save_buffers_to_disk
from .uploaders import upload_buffers_to_server


def save_backtest_results(
    results: list[BacktestSummary],
    config: SaveConfig,
    cache: ResultBuffersCache,
) -> None:
    """保存回测结果到本地文件。

    注意：
    1. 调用者应确保 cache 中已存在对应格式的buffers。
    2. 保存前会自动清空目录。
    3. 输出目录必须在项目根目录的 data/output 文件夹下。

    Args:
        results: 回测结果列表
        config: 保存配置
        cache: 缓存对象，必须已包含对应格式的buffers
    """
    # 从缓存获取buffers
    buffers = cache.get(config.dataframe_format)
    assert buffers is not None, (
        f"缓存中未找到 {config.dataframe_format} 格式的buffers。"
        "请确保在调用此函数前已调用 convert_backtest_results_to_buffers()。"
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
) -> None:
    """上传回测结果到服务器。

    注意：调用者应确保 cache 中已存在对应格式的buffers。

    Args:
        results: 回测结果列表
        config: 上传配置
        cache: 缓存对象，必须已包含对应格式的buffers
    """
    # 从缓存获取buffers
    buffers = cache.get(config.dataframe_format)
    assert buffers is not None, (
        f"缓存中未找到 {config.dataframe_format} 格式的buffers。"
        "请确保在调用此函数前已调用 convert_backtest_results_to_buffers()。"
    )

    upload_buffers_to_server(
        buffers,
        config=config.request_config,
        server_dir=config.server_dir,
        zip_name=config.zip_name,
        compress_level=config.compress_level,
    )
