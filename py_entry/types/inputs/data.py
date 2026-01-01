from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict
import polars as pl

DataSource = Dict[str, pl.DataFrame]


class DataContainer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mapping: pl.DataFrame
    skip_mask: Optional[pl.DataFrame] = None
    skip_mapping: Dict[str, bool]
    source: DataSource
    base_data_key: str
