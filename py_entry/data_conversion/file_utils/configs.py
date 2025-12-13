"""结果导出相关的配置数据结构"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from .types import RequestConfig
from ..types.chart_config import DashboardOverride

from typing import Literal

ParquetCompression = Literal[
    "lz4", "uncompressed", "snappy", "gzip", "lzo", "brotli", "zstd"
]
default_parquet_compression = "snappy"


@dataclass
class SaveConfig:
    """保存结果的配置"""

    output_dir: str | Path  # 相对于 data/output 的路径


@dataclass
class UploadConfig:
    """上传结果的配置"""

    request_config: RequestConfig
    server_dir: str | None = None
    zip_name: str | None = None


@dataclass
class DisplayConfig:
    """显示仪表盘的配置"""

    # 仪表盘覆盖配置
    override: Optional[DashboardOverride] = None
    # UMD JavaScript 库文件的路径
    lib_path: str = "../lwchart/chart-dashboard.umd.js"
    # CSS 文件的路径
    css_path: str = "../lwchart/lwchart_demo3.css"
    # 是否将 JS/CSS 文件内容读取并嵌入到 HTML 中（自包含）
    embed_files: bool = True
    # 用于渲染图表的 HTML 容器 ID
    container_id: Optional[str] = None
    # 图表容器的宽度，例如 "100%" 或 "800px"
    width: str = "100%"
    # 图表容器的宽高比，例如 "16/9" 或 "4/3"
    aspect_ratio: str = "16/9"
