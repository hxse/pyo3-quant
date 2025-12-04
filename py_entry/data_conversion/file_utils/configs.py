"""结果导出相关的配置数据结构"""

import io
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from .types import RequestConfig


@dataclass
class ResultBuffersCache:
    """缓存不同格式和索引设置的结果buffers"""

    csv: List[Tuple[Path, io.BytesIO]] | None = None
    parquet: List[Tuple[Path, io.BytesIO]] | None = None
    csv_no_index: List[Tuple[Path, io.BytesIO]] | None = None
    parquet_no_index: List[Tuple[Path, io.BytesIO]] | None = None

    def get(self, format: str, keep_index: bool = True) -> List[Tuple[Path, io.BytesIO]] | None:
        """获取指定格式和索引设置的缓存"""
        if format == "csv":
            return self.csv if keep_index else self.csv_no_index
        elif format == "parquet":
            return self.parquet if keep_index else self.parquet_no_index
        return None

    def set(self, format: str, buffers: List[Tuple[Path, io.BytesIO]], keep_index: bool = True) -> None:
        """设置指定格式和索引设置的缓存"""
        if format == "csv":
            if keep_index:
                self.csv = buffers
            else:
                self.csv_no_index = buffers
        elif format == "parquet":
            if keep_index:
                self.parquet = buffers
            else:
                self.parquet_no_index = buffers


@dataclass
class SaveConfig:
    """保存结果的配置"""

    output_dir: str | Path  # 相对于 data/output 的路径
    dataframe_format: str = "csv"  # "csv" 或 "parquet"
    keep_index: bool = True  # 是否在DataFrame的第一列添加整数索引


@dataclass
class UploadConfig:
    """上传结果的配置"""

    request_config: RequestConfig
    server_dir: str | None = None
    zip_name: str | None = None
    dataframe_format: str = "csv"
    compress_level: int = 1
    keep_index: bool = True  # 是否在DataFrame的第一列添加整数索引
