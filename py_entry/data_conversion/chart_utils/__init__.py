"""
图表工具模块

提供图表配置生成和管理的核心功能。

主要模块:
- options: 所有图表类型的详细选项定义
- helpers: 便捷的配置创建函数
- generation: 自动化配置生成逻辑
- settings: 全局配置和布局定义
- utils: 工具函数
"""

# 导出核心选项类型
from .options import (
    CandleOption,
    LineOption,
    HistogramOption,
    AreaOption,
    BaselineOption,
    BarOption,
    HorizontalLineOption,
    VerticalLineOption,
    LineStyle,
    LineType,
    ColorSchemes,
)

# 导出辅助函数
from .helpers import (
    create_candle_series,
    create_line_series,
    create_histogram_series,
    create_area_series,
    create_baseline_series,
    create_bar_series,
    create_hline,
    create_vline,
    get_color_for_index,
    remove_none_values,
)

# 导出生成函数
from .generation import generate_default_chart_config

# 导出设置
from .settings import IGNORE_COLS, INDICATOR_LAYOUT

__all__ = [
    # 选项类
    "CandleOption",
    "LineOption",
    "HistogramOption",
    "AreaOption",
    "BaselineOption",
    "BarOption",
    "HorizontalLineOption",
    "VerticalLineOption",
    # 枚举
    "LineStyle",
    "LineType",
    "ColorSchemes",
    # 辅助函数
    "create_candle_series",
    "create_line_series",
    "create_histogram_series",
    "create_area_series",
    "create_baseline_series",
    "create_bar_series",
    "create_hline",
    "create_vline",
    "get_color_for_index",
    "remove_none_values",
    # 生成函数
    "generate_default_chart_config",
    # 设置
    "IGNORE_COLS",
    "INDICATOR_LAYOUT",
]
