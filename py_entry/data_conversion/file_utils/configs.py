"""结果导出相关的配置数据结构"""

import io
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from .types import RequestConfig


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


@dataclass
class UploadConfig:
    """上传结果的配置"""

    request_config: RequestConfig
    server_dir: str | None = None
    zip_name: str | None = None
    dataframe_format: str = "csv"
    compress_level: int = 1
