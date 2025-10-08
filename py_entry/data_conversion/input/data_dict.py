"""数据字典定义"""

from dataclasses import dataclass
from typing import Dict, List
import polars as pl


@dataclass
class DataDict:
    """回测数据字典 - 对应 Rust ProcessedDataDict"""

    mapping: pl.DataFrame
    skip_mask: pl.DataFrame
    ohlcv: List[pl.DataFrame]
    extra_data: Dict[str, List[pl.DataFrame]]
