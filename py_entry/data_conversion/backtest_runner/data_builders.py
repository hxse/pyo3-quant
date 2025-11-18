from abc import ABC, abstractmethod
from typing import List

from py_entry.data_conversion.input import DataContainer
from py_entry.data_conversion.helpers import generate_data_dict
import polars as pl


class BaseDataBuilder(ABC):
    """数据构建器基类"""

    @abstractmethod
    def build_data_dict(
        self,
        timeframes: List[str],
        start_time: int,
        num_bars: int,
        brick_size: float,
    ) -> DataContainer:
        """构建数据字典

        Args:
            timeframes: 时间框架列表
            start_time: 数据开始时间戳(毫秒)
            num_bars: 要生成的数据条数
            brick_size: 砖块大小

        Returns:
            DataDict 数据字典
        """
        pass


class DefaultDataBuilder(BaseDataBuilder):
    """默认数据构建器"""

    def build_data_dict(
        self,
        timeframes: List[str] = ["15m", "1h"],
        start_time: int = 1735689600000,
        num_bars: int = 1000,
        brick_size: float = 2.0,
        predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
        fixed_seed: bool = False,
    ) -> DataContainer:
        """构建数据字典

        Args:
            timeframes: 时间框架列表(默认 ["15m", "1h"])
            start_time: 数据开始时间戳(默认使用合理的默认值)
            num_bars: 要生成的数据条数(默认 1000)
            brick_size: 砖块大小(默认 2.0)

        Returns:
            DataDict 数据字典
        """
        # generate_data_dict 应该已经返回新的 DataDict 结构，其中包含 source 字段
        # ohlcv 和 extra_data 会被合并到 source 字典中
        return generate_data_dict(
            timeframes=timeframes,
            start_time=start_time,
            num_bars=num_bars,
            brick_size=brick_size,
            predefined_ohlcv_dfs=predefined_ohlcv_dfs,
            fixed_seed=fixed_seed,
        )
