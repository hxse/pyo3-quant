from abc import ABC, abstractmethod

from py_entry.data_conversion.input import DataContainer
from py_entry.data_conversion.helpers import generate_data_dict
from py_entry.data_conversion.helpers.data_generator import (
    DataGenerationParams,
    OtherParams,
    OhlcvDataFetchConfig,
)
import polars as pl


class BaseDataBuilder(ABC):
    """数据构建器基类"""

    @abstractmethod
    def build_data_dict(
        self,
        simulated_data_config: DataGenerationParams | None = None,
        ohlcv_data_config: OhlcvDataFetchConfig | None = None,
        predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
        other_params: OtherParams | None = None,
    ) -> DataContainer:
        """构建数据字典

        Args:
            simulated_data_config: 模拟数据生成参数配置对象
            ohlcv_data_config: OHLCV数据获取配置对象
            predefined_ohlcv_dfs: 预定义的OHLCV DataFrame列表
            other_params: 其他参数配置对象

        Returns:
            DataDict 数据字典
        """
        pass


class DefaultDataBuilder(BaseDataBuilder):
    """默认数据构建器"""

    def build_data_dict(
        self,
        simulated_data_config: DataGenerationParams | None = None,
        ohlcv_data_config: OhlcvDataFetchConfig | None = None,
        predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
        other_params: OtherParams | None = None,
    ) -> DataContainer:
        """构建数据字典

        Args:
            simulated_data_config: 模拟数据生成参数配置对象
            ohlcv_data_config: OHLCV数据获取配置对象
            predefined_ohlcv_dfs: 预定义的OHLCV DataFrame列表
            other_params: 其他参数配置对象

        Returns:
            DataDict 数据字典
        """
        # generate_data_dict 应该已经返回新的 DataDict 结构，其中包含 source 字段
        # ohlcv 和 extra_data 会被合并到 source 字典中
        return generate_data_dict(
            simulated_data_config=simulated_data_config,
            ohlcv_data_config=ohlcv_data_config,
            predefined_ohlcv_dfs=predefined_ohlcv_dfs,
            other_params=other_params,
        )
