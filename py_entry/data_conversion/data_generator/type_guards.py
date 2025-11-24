"""
数据生成器类型守卫函数
"""

from typing import Union, cast
import polars as pl

from .config import DataGenerationParams, OhlcvDataFetchConfig

# 类型别名：数据源配置的联合类型
DataSourceConfig = Union[DataGenerationParams, OhlcvDataFetchConfig, list[pl.DataFrame]]


def is_simulated_data(config: DataSourceConfig) -> bool:
    """判断是否为模拟数据配置"""
    return isinstance(config, DataGenerationParams)


def is_fetched_data(config: DataSourceConfig) -> bool:
    """判断是否为获取数据配置"""
    return isinstance(config, OhlcvDataFetchConfig)


def is_predefined_data(config: DataSourceConfig) -> bool:
    """判断是否为预定义数据配置"""
    if not isinstance(config, list):
        return False
    # 检查列表中的所有元素是否都是 pl.DataFrame 类型
    return all(isinstance(item, pl.DataFrame) for item in config)
