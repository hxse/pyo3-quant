"""结果导出相关的配置数据结构"""

from numba.core.compiler import DefaultPassBuilder

import io
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass, field
from .types import RequestConfig

from typing import Literal

ParquetCompression = Literal[
    "lz4", "uncompressed", "snappy", "gzip", "lzo", "brotli", "zstd"
]
default_parquet_compression = "snappy"


@dataclass
class ResultBuffersCache:
    """缓存不同格式的结果buffers"""

    csv: List[Tuple[Path, io.BytesIO]] | None = None
    parquet: List[Tuple[Path, io.BytesIO]] | None = None

    def get(self, format: str) -> List[Tuple[Path, io.BytesIO]] | None:
        """获取指定格式的缓存"""
        if format == "csv":
            return self.csv
        elif format == "parquet":
            return self.parquet
        return None

    def set(self, format: str, buffers: List[Tuple[Path, io.BytesIO]]) -> None:
        """设置指定格式的缓存"""
        if format == "csv":
            self.csv = buffers
        elif format == "parquet":
            self.parquet = buffers


@dataclass
class SaveConfig:
    """保存结果的配置"""

    output_dir: str | Path  # 相对于 data/output 的路径
    dataframe_format: str = "csv"  # "csv" 或 "parquet"
    parquet_compression: ParquetCompression = default_parquet_compression


@dataclass
class UploadConfig:
    """上传结果的配置"""

    request_config: RequestConfig
    server_dir: str | None = None
    zip_name: str | None = None
    dataframe_format: str = "csv"
    compress_level: int = 1
    parquet_compression: ParquetCompression = default_parquet_compression


@dataclass
class DisplayConfig:
    """显示仪表盘的配置"""

    chart_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "template": "HORIZONTAL_1x1",
            "showBottomRow": True,
            "viewMode": "chart",
        }
    )

    chart_config: Dict[str, Any] = chart_config  # ChartDashboard 的配置字典
    dataframe_format: str = "csv"  # DataFrame格式，"csv" 或 "parquet"
    compress_level: int = 1  # 压缩级别，0-9
    parquet_compression: ParquetCompression = default_parquet_compression
    lib_path: str = "../lwchart/chart-dashboard.umd.js"  # UMD JavaScript 库文件的路径
    css_path: str = "../lwchart/lwchart_demo3.css"  # CSS 文件的路径
    embed_files: bool = True  # 是否将 JS/CSS 文件内容读取并嵌入到 HTML 中（自包含）
    container_id: Optional[str] = None  # 用于渲染图表的 HTML 容器 ID
    width: str = "100%"  # 图表容器的宽度，例如 "100%" 或 "800px"
    aspect_ratio: str = "16/9"  # 图表容器的宽高比，例如 "16/9" 或 "4/3"
