from datetime import datetime
from typing import Literal, Protocol, Any, TypedDict, NotRequired
from pydantic import BaseModel
import pandas as pd
import polars as pl
from py_entry.types import (
    DataContainer,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
    BacktestParams,
    PerformanceParams,
)
from py_entry.data_generator import generate_data_dict, DirectDataConfig
from py_entry.runner import Backtest


class StrategySignal(BaseModel):
    """策略信号 - 策略函数的统一返回值"""

    # === 核心信号 ===
    strategy_name: str  # 策略名称（如 "trend", "reversal", "momentum"）
    symbol: str  # 扫描品种代码 (如 KQ.m@DCE.l)
    real_symbol: str = ""  # 实际主力合约代码 (如 DCE.i2505)，如果为空则未定义
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

    def to_display_string(self, index: int | None = None) -> str:
        """
        生成展示用的多行字符串 (Console/Telegram 通用)
        Args:
            index: 如果提供，会在第一行前加序号 (如 "1. ")
        """
        # 1. 处理 Symbol (拼接 real_symbol)
        symbol_display = self.symbol
        if self.real_symbol and self.real_symbol != self.symbol:
            symbol_display = f"{self.symbol} | {self.real_symbol}"

        # 2. 处理方向中文映射
        direction_map = {"long": "做多", "short": "做空", "none": "观察"}
        dir_str = direction_map.get(self.direction, self.direction)

        # 3. 拼接标题行
        prefix = f"{index}. " if index is not None else ""
        # 格式: 1. KQ.m@DCE.l | DCE.i2505 | trend | 做多
        header = f"{prefix}{symbol_display} | {self.strategy_name} | {dir_str}"

        # 4. 拼接详情与警告
        lines = [header]
        lines.append(f"  - 触发: {self.trigger}")

        if self.detail_lines:
            # 详情如果是一行，直接拼；如果是多行，空格连接
            details_text = " ".join(self.detail_lines)
            lines.append(f"  - 详情: {details_text}")

        if self.warnings:
            lines.append(f"  - ⚠️ {' '.join(self.warnings)}")

        return "\n".join(lines)


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


def run_scan_backtest(
    ctx: ScanContext,
    indicators: dict,
    signal_template: SignalTemplate,
    base_tf: str = "ohlcv_5m",
) -> tuple[dict[str, float], float, int] | None:
    """
    通用回测执行器 helper。
    功能：
    1. 将 ctx 转换为回测引擎所需的 data
    2. 创建 Backtest 实例并运行
    3. 获取并返回【已完成】的信号（倒数第二根 K 线）

    Args:
        ctx: 扫描上下文
        indicators: 指标配置
        signal_template: 信号模板
        base_tf: 基准周期 key (默认 ohlcv_5m)

    Returns:
        (signal_dict, close_price, timestamp) | None
        如果运行失败、结果为空或不足 2 根 K 线，返回 None。
        signal_dict 例如: {'entry_long': 1.0, 'entry_short': 0.0}
        timestamp: K 线时间戳 (毫秒)
    """
    # 1. 转换数据
    data = ctx.to_data_container(base_tf=base_tf)

    # 2. 准备回测配置
    settings = SettingContainer(
        execution_stage=ExecutionStage.SIGNALS,
        return_only_final=False,
    )
    bt = Backtest(
        data_source=DirectDataConfig(
            data=data.source, base_data_key=data.base_data_key
        ),
        indicators=indicators,
        signal_template=signal_template,
        engine_settings=settings,
        backtest=BacktestParams(
            initial_capital=10000.0,
            fee_fixed=1.0,
            fee_pct=0.0005,
        ),
        performance=PerformanceParams(metrics=[]),
    )

    # 3. 运行回测
    result = bt.run()
    if not result.results:
        return None
    res_0 = result.results[0]
    if res_0.signals is None or res_0.signals.height < 2:
        return None

    # 4. 提取【已完成】K线的信号（倒数第二行）
    last_row = res_0.signals.tail(2).head(1).to_dict(as_series=False)
    # last_row 是 {'key': [val], ...} 格式，需要解包
    signal_dict = {k: v[0] for k, v in last_row.items()}

    # 5. 提取对应价格和时间
    last_candle = data.source[base_tf].select(["close", "time"]).tail(2).head(1)
    price = last_candle.select(pl.col("close")).item()
    timestamp = last_candle.select(pl.col("time")).item()

    return signal_dict, price, timestamp


def format_timestamp(ts_ms: int) -> str:
    """将毫秒级时间戳转换为本地时间字符串 (YYYY-MM-DD HH:MM:SS)"""
    dt = datetime.fromtimestamp(ts_ms / 1000.0)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
