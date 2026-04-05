from datetime import datetime

import polars as pl

from py_entry.runner import Backtest
from py_entry.scanner.config import ScanLevel
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    PerformanceParams,
    SettingContainer,
    SignalTemplate,
)
from py_entry.data_generator import DirectDataConfig

from ._scan_context import ScanContext


def run_scan_backtest(
    ctx: ScanContext,
    indicators: dict,
    signal_template: SignalTemplate,
    base_level: ScanLevel = ScanLevel.TRIGGER,
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
        base_level: 基准级别 key (默认 trigger_level)

    Returns:
        (signal_dict, close_price, timestamp) | None
        如果运行失败、结果为空或不足 2 根 K 线，返回 None。
        signal_dict 例如: {'entry_long': 1.0, 'entry_short': 0.0}
        timestamp: K 线时间戳 (毫秒)
    """
    data = ctx.to_data_pack(base_level=base_level)
    base_dk = ctx.get_level_dk(base_level)

    settings = SettingContainer(
        execution_stage=ExecutionStage.Signals,
        return_only_final=False,
    )
    bt = Backtest(
        data_source=DirectDataConfig(
            data=data.source,
            base_data_key=base_dk,
            align_to_base_range=False,
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

    result = bt.run()
    res_0 = result.result
    if res_0.signals is None or res_0.signals.height < 2:
        return None

    last_row = res_0.signals.tail(2).head(1).to_dict(as_series=False)
    signal_dict = {k: v[0] for k, v in last_row.items()}

    last_candle = data.source[base_dk].select(["close", "time"]).tail(2).head(1)
    price = last_candle.select(pl.col("close")).item()
    timestamp = last_candle.select(pl.col("time")).item()

    return signal_dict, price, timestamp


def format_timestamp(ts_ms: int) -> str:
    """将毫秒级时间戳转换为本地时间字符串 (YYYY-MM-DD HH:MM:SS)"""
    dt = datetime.fromtimestamp(ts_ms / 1000.0)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
