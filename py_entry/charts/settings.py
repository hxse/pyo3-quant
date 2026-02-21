from py_entry.types import (
    HorizontalLineLayoutItem,
    IndicatorLayoutItem,
    LineOption,
    PanelLayoutItem,
)
from .options import VolumeOption

# 需要过滤的列名
IGNORE_COLS = {"index", "time", "date"}

# INDICATOR_LAYOUT 类型定义
# 每个键代表一个具名面板；值为该面板的布局项列表
IndicatorLayout = dict[str, list[PanelLayoutItem]]


def base_layout() -> IndicatorLayout:
    """返回通用图表布局（策略可按 panel 名覆盖）。"""
    return {
        "main": [
            IndicatorLayoutItem(
                indicator="ohlc", type="candle", show=True, showInLegend=True
            ),
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
                showInLegend=False,
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
        # 中文注释：默认 RSI 只显示曲线，不内置阈值线，避免策略语义被全局强绑定。
        "rsi": [
            IndicatorLayoutItem(indicator="rsi", type="line", show=True),
        ],
        "bbands_bandwidth": [
            IndicatorLayoutItem(indicator="bbands_bandwidth", type="line", show=False),
        ],
        "bbands_percent": [
            IndicatorLayoutItem(indicator="bbands_percent", type="line", show=False),
        ],
        "macd": [
            IndicatorLayoutItem(indicator="macd_macd", type="line", show=True),
            IndicatorLayoutItem(indicator="macd_signal", type="line", show=True),
            IndicatorLayoutItem(indicator="macd_hist", type="histogram", show=True),
            HorizontalLineLayoutItem(
                indicator="macd_zero",
                show=True,
                value=0,
                anchorIndicator="macd_macd",
            ),
        ],
        # 中文注释：默认 ADX 只显示通用线，不绑定策略阈值参数。
        "adx": [
            IndicatorLayoutItem(
                indicator="adx_adx",
                type="line",
                show=True,
                lineOptions=[LineOption(color="#E65100", lineWidth=2)],
            ),  # 橙色 ADX
            IndicatorLayoutItem(
                indicator="adx_adxr",
                type="line",
                show=False,
                lineOptions=[LineOption(color="#1565C0", lineWidth=1)],
            ),  # 蓝色 ADXR (默认隐藏)
            IndicatorLayoutItem(
                indicator="adx_plus_dm",
                type="line",
                show=True,
                lineOptions=[LineOption(color="#2ca02c", lineWidth=1)],
            ),  # 绿色 +DI
            IndicatorLayoutItem(
                indicator="adx_minus_dm",
                type="line",
                show=True,
                lineOptions=[LineOption(color="#d62728", lineWidth=1)],
            ),  # 红色 -DI
        ],
    }


def merge_layout(overrides: IndicatorLayout | None = None) -> IndicatorLayout:
    """合并布局：策略同名 panel 覆盖默认 panel。"""
    merged = base_layout()
    if overrides is not None:
        merged |= overrides
    return merged


# 默认布局快照（兼容旧入口变量名）
INDICATOR_LAYOUT: IndicatorLayout = base_layout()


# 底栏图表配置 (Slot > Pane > Items)
# 与 chart 配置保持一致的三维结构
BOTTOM_PANEL_LAYOUT: list[list[list[IndicatorLayoutItem]]] = [
    [  # Slot 0
        [  # Pane 0
            IndicatorLayoutItem(
                indicator="balance",
                type="line",
                show=True,
                showInLegend=True,
                lineOptions=[LineOption(color="#2962FF", lineWidth=2)],
            ),
            IndicatorLayoutItem(
                indicator="equity",
                type="line",
                show=True,
                showInLegend=True,
                lineOptions=[LineOption(color="#FF6D00", lineWidth=2)],
            ),
            IndicatorLayoutItem(
                indicator="current_drawdown",
                type="line",
                show=False,
                showInLegend=True,
                lineOptions=[LineOption(color="#1D2021", lineWidth=2)],
            ),
            IndicatorLayoutItem(
                indicator="fee",
                type="line",
                show=False,
                showInLegend=True,
                lineOptions=[LineOption(color="#1D2021", lineWidth=2)],
            ),
            IndicatorLayoutItem(
                indicator="fee_cum",
                type="line",
                show=False,
                showInLegend=True,
                lineOptions=[LineOption(color="#1D2021", lineWidth=2)],
            ),
        ],
    ],
]
