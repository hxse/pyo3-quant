"""数据字典定义"""

from dataclasses import dataclass
from typing import Dict, List
import polars as pl


@dataclass
class DataContainer:
    """回测数据字典 - 对应 Rust ProcessedDataDict"""

    mapping: pl.DataFrame
    skip_mask: pl.DataFrame
    skip_mapping: Dict[str, bool]
    source: Dict[str, List[pl.DataFrame]]
