"""
数据生成器类型守卫函数
"""

from typing import Union, TypeGuard

from .config import DataGenerationParams, OhlcvDataFetchConfig, DirectDataConfig


# 类型别名：数据源配置的联合类型
DataSourceConfig = Union[DataGenerationParams, OhlcvDataFetchConfig, DirectDataConfig]


def is_simulated_data(config: DataSourceConfig) -> bool:
    """判断是否为模拟数据配置"""
    return isinstance(config, DataGenerationParams)


def is_fetched_data(config: DataSourceConfig) -> bool:
    """判断是否为获取数据配置"""
    return isinstance(config, OhlcvDataFetchConfig)


def is_predefined_data(data_source: DataSourceConfig) -> TypeGuard[DirectDataConfig]:
    """判断是否为预定义数据配置"""
    return isinstance(data_source, DirectDataConfig)
