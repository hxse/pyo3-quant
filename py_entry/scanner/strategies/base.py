from typing import Literal, Protocol, Any, TypedDict, NotRequired
from pydantic import BaseModel
import pandas as pd
import polars as pl
from py_entry.types import DataContainer
from py_entry.data_generator import generate_data_dict, DirectDataConfig


class StrategySignal(BaseModel):
    """策略信号 - 策略函数的统一返回值"""

    # === 核心信号 ===
    strategy_name: str  # 策略名称（如 "trend", "reversal", "momentum"）
    symbol: str  # 品种代码
    direction: Literal["long", "short", "none"]  # 方向

    # === 信号详情 ===
    trigger: str  # 触发信号简述（如 "5m close x> EMA"）

    # === 可展示信息 (给人看的) ===
    summary: str  # 一句话总结（如 "甲醇 做空 | 四周期共振"）
    detail_lines: list[str]  # 详细信息（每行一个字符串）

    # === 警告/提示 (可选) ===
    warnings: list[str] = []  # 警告信息列表

    # === 附加数据 (机读用) ===
    metadata: dict[str, Any] = {}  # 附加数据，供程序化处理

    def to_console_message(self) -> str:
        """生成控制台日志消息"""
        lines = [self.summary]
        lines.extend([f"  {line}" for line in self.detail_lines])
        if self.warnings:
            lines.extend([f"  {w}" for w in self.warnings])
        return "\n".join(lines)

    def to_notify_message(self) -> str:
        """生成通知消息（如 TG）"""
        return self.to_console_message()


class StrategyCheckResult(TypedDict):
    """策略内部检查结果的标准返回结构"""

    is_bullish: bool
    is_bearish: bool
    detail: str
    price: float
    # 可选字段
    trigger: NotRequired[str]
    details: NotRequired[list[str]]
    extra_info: str  # 必须有，默认为空串


class ScanContext:
    """扫描上下文 - 策略输入"""

    def __init__(self, symbol: str, klines: dict[str, pd.DataFrame]):
        self.symbol = symbol
        self.klines = klines  # key: "5m", "1h", "D", "W" etc.

    def get_klines(self, tf_name: str) -> pd.DataFrame | None:
        return self.klines.get(tf_name)

    def validate_klines_existence(self, required_timeframes: list[str]) -> None:
        """检查必要周期数据是否存在且不为空，否则抛出 ValueError"""
        missing = []
        for tf in required_timeframes:
            df = self.klines.get(tf)
            if df is None or df.empty:
                missing.append(tf)

        if missing:
            raise ValueError(f"缺少必要周期数据: {missing}")

    def to_data_container(
        self, base_tf: str = "ohlcv_15m", lookback: int | None = None
    ) -> DataContainer:
        """
        将当前 K 线上下文转换为 BacktestEngine 所需的 DataContainer

        Args:
            base_tf: 基准数据键名 (如 "ohlcv_15m")
            lookback: 可选的回溯长度，仅取最近的 N 根 K 线以提升性能

        Returns:
            DataContainer 对象
        """
        source_dict = {}

        for tf_name, pdf in self.klines.items():
            # 统一键名格式: 5m -> ohlcv_5m (如果 key 已经是 ohlcv_ 开头则不动)
            key = tf_name if tf_name.startswith("ohlcv_") else f"ohlcv_{tf_name}"

            # 数据切片 (优化性能)
            target_df = pdf if lookback is None else pdf.iloc[-lookback:]

            # 转换为 Polars DataFrame
            # 注意: 这里假设 pdf 已经包含了 time (int64 ms) 列
            # 如果是 scanner 传进来的，通常是 pandas DataFrame
            pl_df = pl.from_pandas(target_df)

            # 转换为 Polars DataFrame 并标准化时间列
            # 统一路径：无论输入是 Datetime 还是 Int64，先转为 Int64 (物理纳秒值)，再整除 1M 转毫秒
            pl_df = (
                pl.from_pandas(target_df)
                .rename({"datetime": "time"})
                .with_columns(
                    (pl.col("time").cast(pl.Int64) // 1_000_000).alias("time")
                )
            )

            assert pl_df["time"].dtype == pl.Int64, (
                f"时间列类型错误: 期望 Int64, 实际 {pl_df['time'].dtype}"
            )

            if not pl_df.is_empty():
                first_ts = pl_df["time"][0]
                # 语义化校验：将时间戳转为年份，检查是否在合理区间 (1990~2100)
                # 这比检查 Int64 数值本身更直观且健壮
                sample_year = pl.select(
                    pl.lit(first_ts).cast(pl.Datetime("ms")).dt.year()
                ).item()
                # 动态语义化校验：检查年份是否在 (1970, 当前年份+10) 之间
                # 这种动态上限彻底解决了固定年份带来的“千年虫”问题
                from datetime import datetime

                current_year = datetime.now().year
                assert 1970 <= sample_year <= current_year + 10, (
                    f"时间戳异常: 解析年份 {sample_year} 超出合理范围 "
                    f"(1970 ~ {current_year + 10})。期望毫秒级时间戳。"
                )

            source_dict[key] = pl_df

        # 验证基准数据是否存在
        if base_tf not in source_dict:
            # 尝试找一个默认的
            if source_dict:
                base_tf = next(iter(source_dict.keys()))
            else:
                raise ValueError("ScanContext 为空，无法转换")

        # 构造 DirectDataConfig
        config = DirectDataConfig(data=source_dict, base_data_key=base_tf)

        # 委托给标准生成器处理 (它会处理 time mapping, skip mask 等)
        return generate_data_dict(config)


class StrategyProtocol(Protocol):
    """策略协议"""

    @property
    def name(self) -> str:
        """策略名称"""
        ...

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        """执行扫描"""
        ...
