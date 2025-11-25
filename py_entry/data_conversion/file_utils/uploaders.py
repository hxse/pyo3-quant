"""将buffer上传到服务器的工具函数"""

import io
import time
from pathlib import Path
from typing import List, Tuple

from .types import RequestConfig
from .zip_utils import create_zip_buffer
from .upload import upload_to_server


def upload_buffers_to_server(
    buffer_list: List[Tuple[Path, io.BytesIO]],
    config: RequestConfig,
    server_dir: str | None = None,
    zip_name: str | None = None,
    compress_level: int = 1,
) -> None:
    """将buffer列表打包并上传到服务器。

    Args:
        buffer_list: 包含(相对路径, BytesIO)元组的列表
        config: 请求配置
        server_dir: 服务器目标目录
        zip_name: ZIP文件名
        compress_level: 压缩级别(0-9)
    """
    if not buffer_list:
        print("警告: 没有数据可打包上传")
        return

    # 创建ZIP
    print("正在打包结果...")
    zip_data = create_zip_buffer(buffer_list, compress_level=compress_level)

    # 上传
    timestamp = int(time.time())
    final_zip_name = zip_name or f"backtest_results_{timestamp}.zip"
    print(f"正在上传 {final_zip_name} ...")

    upload_to_server(
        config=config,
        zip_data=zip_data,
        server_dir=Path(server_dir) if server_dir else None,
        zip_name=final_zip_name,
    )
