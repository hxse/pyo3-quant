from enum import Enum
from typing import List, Optional, Union, Literal
from pydantic import BaseModel, model_validator


class CandleOption(BaseModel):
    upColor: Optional[str] = None
    downColor: Optional[str] = None
    borderVisible: Optional[bool] = None
    borderUpColor: Optional[str] = None
    borderDownColor: Optional[str] = None
    wickUpColor: Optional[str] = None
    wickDownColor: Optional[str] = None


class HistogramOption(BaseModel):
    color: Optional[str] = None
    base: Optional[float] = None


class VolumeOption(BaseModel):
    priceScaleMarginTop: Optional[float] = None
    adjustMainSeries: Optional[bool] = None


class LineOption(BaseModel):
    color: Optional[str] = None
    lineWidth: Optional[int] = None
    lineStyle: Optional[int] = None


class AreaOption(BaseModel):
    topColor: Optional[str] = None
    bottomColor: Optional[str] = None
    lineColor: Optional[str] = None
    lineWidth: Optional[int] = None
    lineStyle: Optional[int] = None


class BaselineOption(BaseModel):
    baseValue: Optional[float] = None
    topLineColor: Optional[str] = None
    bottomLineColor: Optional[str] = None


class BarOption(BaseModel):
    upColor: Optional[str] = None
    downColor: Optional[str] = None
    thinBars: Optional[bool] = None


class HorizontalLineOption(BaseModel):
    # 中文注释：基础字段，兼容历史配置。
    color: str
    value: Optional[float] = None
    label: Optional[str] = None
    showLabel: bool = False
    # 中文注释：以下字段用于透传 PriceLineOptions，未传则由前端默认值兜底。
    lineWidth: Optional[Literal[1, 2, 3, 4]] = None
    lineStyle: Optional[Literal[0, 1, 2, 3, 4]] = None
    lineVisible: Optional[bool] = None
    axisLabelVisible: Optional[bool] = None
    axisLabelColor: Optional[str] = None
    axisLabelTextColor: Optional[str] = None


class VerticalLineOption(BaseModel):
    # 中文注释：基础字段，兼容历史配置。
    color: str
    value: Union[float, str]
    label: Optional[str] = None
    showLabel: bool = False
    # 中文注释：以下字段用于透传 SeriesMarker，未传则由前端默认值兜底。
    shape: Optional[Literal["arrowUp", "arrowDown", "circle", "square"]] = None
    size: Optional[int] = None
    position: Optional[Literal["aboveBar", "belowBar", "inBar"]] = None


# Aliases
HorizontalLine = HorizontalLineOption
VerticalLine = VerticalLineOption


class IndicatorLayoutItem(BaseModel):
    indicator: str
    type: Literal["candle", "histogram", "volume", "line", "area", "baseline", "bar"]
    show: bool = True
    showInLegend: bool = False
    showLabel: bool = False

    candleOptions: Optional[List[CandleOption]] = None
    histogramOptions: Optional[List[HistogramOption]] = None
    volumeOptions: Optional[List[VolumeOption]] = None
    lineOptions: Optional[List[LineOption]] = None
    areaOptions: Optional[List[AreaOption]] = None
    baselineOptions: Optional[List[BaselineOption]] = None
    barOptions: Optional[List[BarOption]] = None


class HorizontalLineLayoutItem(BaseModel):
    # 中文注释：hline 使用独立类型，避免复用通用指标项导致语义混乱。
    indicator: str
    type: Literal["hline"] = "hline"
    show: bool = True
    showInLegend: bool = False
    showLabel: bool = False
    # 中文注释：优先使用 value，缺失时再尝试从 paramKey 对应的 signal 参数取值。
    value: Optional[float] = None
    paramKey: Optional[str] = None
    # 中文注释：仅当锚点指标在当前周期存在时才绘制，避免在无关周期出现阈值线。
    anchorIndicator: Optional[str] = None
    hLineOpt: Optional[HorizontalLineOption] = None

    @model_validator(mode="after")
    def validate_value_or_param_key(self) -> "HorizontalLineLayoutItem":
        # 中文注释：强约束至少提供一种取值来源，避免出现无法落地的 hline 配置。
        if self.value is None and self.paramKey is None:
            raise ValueError(
                "HorizontalLineLayoutItem requires at least one of value or paramKey"
            )
        return self


class VerticalLineLayoutItem(BaseModel):
    # 中文注释：vline 使用独立类型，语义上与指标列匹配解耦。
    indicator: str
    type: Literal["vline"] = "vline"
    show: bool = True
    showInLegend: bool = False
    showLabel: bool = False
    vLineOpt: Optional[VerticalLineOption] = None


PanelLayoutItem = Union[
    IndicatorLayoutItem,
    HorizontalLineLayoutItem,
    VerticalLineLayoutItem,
]


class SeriesItemConfig(BaseModel):
    type: Literal[
        "candle",
        "histogram",
        "volume",
        "line",
        "area",
        "baseline",
        "bar",
        "hline",
        "vline",
    ]
    show: bool = True
    showInLegend: bool = False

    fileName: Optional[str] = None
    dataName: Optional[Union[str, List[str]]] = None

    candleOpt: Optional[CandleOption] = None
    histogramOpt: Optional[HistogramOption] = None
    volumeOpt: Optional[VolumeOption] = None
    lineOpt: Optional[LineOption] = None
    areaOpt: Optional[AreaOption] = None
    baselineOpt: Optional[BaselineOption] = None
    barOpt: Optional[BarOption] = None
    hLineOpt: Optional[HorizontalLineOption] = None
    vLineOpt: Optional[VerticalLineOption] = None


class ChartConfig(BaseModel):
    template: str
    chart: List[List[List[SeriesItemConfig]]]
    showBottomRow: bool = True
    bottomRowChart: Optional[List[List[List[SeriesItemConfig]]]] = None
    viewMode: Literal["chart", "table"] = "chart"
    selectedInternalFileName: str = ""
    showLegendInAll: bool = True


class DashboardOverride(BaseModel):
    template: Optional[str] = None
    showBottomRow: Optional[bool] = None
    viewMode: Optional[Literal["chart", "table"]] = None
    selectedInternalFileName: Optional[str] = None
    selectedZipFileName: Optional[str] = None
    show: Optional[List[str]] = None
    showInLegend: Optional[List[str]] = None
    showRiskLegend: Optional[str] = None
    showLegendInAll: bool = True

    def to_dict(self):
        return self.model_dump(exclude_none=True)
