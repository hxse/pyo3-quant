"""结果导出工具函数

提供将回测结果保存到磁盘和上传到服务器的高级函数。
"""

from pathlib import Path
import io
from typing import List, Tuple
from .configs import SaveConfig, UploadConfig
from .path_utils import validate_output_path, clear_directory
from .savers import save_buffers_to_disk
from .upload import upload_to_server
import time


def save_backtest_results(
    buffers: List[Tuple[Path, io.BytesIO]],
    config: SaveConfig,
) -> None:
    """保存所有回测数据（包括配置和结果）到本地文件。

    注意：
    1. 保存前会自动清空目录。
    2. 输出目录必须在项目根目录的 data/output 文件夹下。

    Args:
        buffers: 要保存的文件 Buffer 列表
        config: 保存配置
    """
    # 验证并获取完整路径
    validated_path = validate_output_path(config.output_dir)

    # 清空目录（总是执行）
    if validated_path.exists():
        print(f"清空目录: {validated_path}")
        clear_directory(validated_path, keep_dir=True)

    # 保存
    save_buffers_to_disk(buffers, validated_path)


def upload_backtest_results(
    zip_data: bytes,
    config: UploadConfig,
) -> None:
    """上传所有回测数据（包括配置和结果）到服务器。

    Args:
        zip_data: ZIP字节数据
        config: 上传配置
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
