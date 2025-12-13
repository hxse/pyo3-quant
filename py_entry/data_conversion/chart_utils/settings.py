from py_entry.data_conversion.types.chart_config import (
    IndicatorLayoutItem,
    LineOption,
)
from .options import VolumeOption

# 需要过滤的列名
IGNORE_COLS = {"index", "time", "date"}

# INDICATOR_LAYOUT 类型定义
# 每个外层列表元素代表一个图表面板（主图或副图）
# 每个内层列表包含该面板的所有指标配置项
IndicatorLayout = list[list[IndicatorLayoutItem]]


# 图表布局配置
# 每个外层数组元素代表一个图表面板（主图或副图）
# 主图在第一个位置 (index 0)，副图按顺序排列 (index 1, 2, 3...)

INDICATOR_LAYOUT: IndicatorLayout = [
    [  # position 0: 主图
        IndicatorLayoutItem(indicator="ohlc", type="candle", show=True),
        # Volume 作为独立类型，前端会自动处理涨跌颜色和叠加层配置
        # 参考文档: https://tradingview.github.io/lightweight-charts/docs/api/interfaces/VolumeSeriesOptions
        IndicatorLayoutItem(
            indicator="volume",
            type="volume",
            show=False,
            volumeOptions=[
                VolumeOption(
                    priceScaleMarginTop=0.9,  # volume占据底部20%
                    adjustMainSeries=True,  # 自动调整主系列避免重叠
                )
            ],
        ),
        IndicatorLayoutItem(
            indicator="sma",
            type="line",
            show=True,
            lineOptions=[
                LineOption(color="#1f77b4", lineWidth=2),  # 第一个 sma 蓝色
                LineOption(color="#ff7f0e", lineWidth=2),  # 第二个 sma 橙色
                LineOption(color="#2ca02c", lineWidth=2),  # 第三个 sma 绿色
            ],
        ),
        IndicatorLayoutItem(indicator="ema", type="line", show=True),
        IndicatorLayoutItem(indicator="bbands_upper", type="line", show=True),
        IndicatorLayoutItem(indicator="bbands_middle", type="line", show=True),
        IndicatorLayoutItem(indicator="bbands_lower", type="line", show=True),
    ],
    [  # position +1: RSI 副图
        IndicatorLayoutItem(indicator="rsi", type="line", show=True),
        IndicatorLayoutItem(indicator="rsi_upper", type="hline", show=True),
        IndicatorLayoutItem(indicator="rsi_center", type="hline", show=True),
        IndicatorLayoutItem(indicator="rsi_lower", type="hline", show=True),
    ],
    [  # position +2: BBands Bandwidth 副图
        IndicatorLayoutItem(indicator="bbands_bandwidth", type="line", show=False),
    ],
    [  # position +3: BBands Percent 副图
        IndicatorLayoutItem(indicator="bbands_percent", type="line", show=False),
    ],
    [  # position +4: MACD 副图
        IndicatorLayoutItem(indicator="macd_macd", type="line", show=True),
        IndicatorLayoutItem(indicator="macd_signal", type="line", show=True),
        IndicatorLayoutItem(indicator="macd_hist", type="line", show=True),
        IndicatorLayoutItem(indicator="macd_zero", type="hline", show=True, value=0),
    ],
]
