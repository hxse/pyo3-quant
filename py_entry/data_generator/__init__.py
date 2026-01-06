"""
数据生成器模块
"""

# 导入配置类
from .config import (
    DataGenerationParams,
    OtherParams,
    OhlcvDataFetchConfig,
    OhlcvRequestParams,
    DirectDataConfig,
)

# 导入类型守卫函数和类型别名
from .type_guards import (
    DataSourceConfig,
    is_simulated_data,
    is_fetched_data,
    is_predefined_data,
)

# 导入核心数据生成函数
from .data_generator import generate_data_dict

# 导入时间工具函数
from .time_utils import parse_timeframe, time_format, fixed_cols

# 导入OHLCV生成器
from .ohlcv_generator import generate_multi_timeframe_ohlcv, generate_ohlcv

# 导入Heikin-Ashi生成器
from .heikin_ashi_generator import generate_ha, calculate_heikin_ashi

# 导入Renko生成器
from .renko_generator import generate_renko, calculate_renko

# 导入时间映射相关函数
from .time_mapping import (
    generate_time_mapping,
    is_natural_sequence,
    process_dataframe_mapping,
)

# 导出所有主要函数，以便兼容原有导入方式
__all__ = [
    "DataGenerationParams",
    "OtherParams",
    "OhlcvDataFetchConfig",
    "OhlcvRequestParams",
    "DirectDataConfig",
    "DataSourceConfig",
    "is_simulated_data",
    "is_fetched_data",
    "is_predefined_data",
    "parse_timeframe",
    "generate_data_dict",
    "generate_ohlcv",
    "generate_multi_timeframe_ohlcv",
    "generate_ha",
    "calculate_heikin_ashi",
    "generate_renko",
    "calculate_renko",
    "generate_time_mapping",
    "process_dataframe_mapping",
    "is_natural_sequence",
    "time_format",
    "fixed_cols",
]
