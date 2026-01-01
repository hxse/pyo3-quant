from enum import Enum
from typing import List, Optional, Union, Literal
from pydantic import BaseModel


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
    color: str
    value: float
    label: Optional[str] = None
    showLabel: bool = False


class VerticalLineOption(BaseModel):
    color: str
    value: Union[float, str]
    label: Optional[str] = None
    showLabel: bool = False


# Aliases
HorizontalLine = HorizontalLineOption
VerticalLine = VerticalLineOption


class IndicatorLayoutItem(BaseModel):
    indicator: str
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
    showLabel: bool = False

    candleOptions: Optional[List[CandleOption]] = None
    histogramOptions: Optional[List[HistogramOption]] = None
    volumeOptions: Optional[List[VolumeOption]] = None
    lineOptions: Optional[List[LineOption]] = None
    areaOptions: Optional[List[AreaOption]] = None
    baselineOptions: Optional[List[BaselineOption]] = None
    barOptions: Optional[List[BarOption]] = None

    hLineOpt: Optional[HorizontalLineOption] = None
    vLineOpt: Optional[VerticalLineOption] = None

    value: Optional[float] = None


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
