"""
OHLCV 数据生成模块
"""

import polars as pl
import numpy as np
from math import ceil
from typing import Optional
from contextlib import contextmanager

from .time_utils import parse_timeframe, time_format, fixed_cols


@contextmanager
def temporary_numpy_seed(seed: Optional[int]):
    """
    临时设置 NumPy 随机种子的上下文管理器

    Args:
        seed: 要设置的种子，如果为 None 则不设置
    """
    # 保存当前状态
    state = np.random.get_state()
    try:
        if seed is not None:
            np.random.seed(seed)
        yield
    finally:
        # 恢复原始状态
        np.random.set_state(state)


def generate_ohlcv(
    timeframe: str,
    start_time: int,
    num_bars: int,
    initial_price: float = 100.0,
    volatility: float = 0.02,
    gap_factor: float = 0.5,  # 新增参数: 控制 Open 价格相对于前一 Close 的波动性
    fixed_seed: Optional[int] = None,
) -> pl.DataFrame:
    """
    生成单周期OHLCV模拟数据，引入随机跳空，更接近真实K线市场。

    Args:
        timeframe: 时间周期
        start_time: 起始时间
        num_bars: K线数量
        initial_price: 初始价格,默认100.0
        volatility: 波动率,默认0.02
        gap_factor: 跳空因子,控制Open价格相对于前一Close的波动性,默认0.5
        fixed_seed: 是否使用固定种子,如果为None则使用随机种子,如果是正整数则使用该种子,默认None
    """
    interval_ms = parse_timeframe(timeframe)

    # 使用上下文管理器临时设置随机种子，确保不影响全局状态
    with temporary_numpy_seed(fixed_seed):
        # 1. 使用 numpy 生成所有随机数
        # 随机收益率 (用于计算 Close)
        returns = np.random.normal(0, volatility, num_bars)
        # 随机 Open 价格跳空 (相对于前一 Close)
        open_returns = np.random.normal(0, volatility * gap_factor, num_bars)
        # High/Low 的波动因子 (相对于 OHLC 范围)
        range_factors = np.abs(np.random.normal(0, volatility / 3, num_bars))

        volumes = np.abs(np.random.normal(1000000, 200000, num_bars))

        # 2. 计算 Close 价格 (随机游走: 使用累积乘积)
        price_multipliers = 1.0 + returns
        close_prices = initial_price * np.cumprod(price_multipliers)

        # 3. 计算 Open 价格 (引入跳空)
        # 使用前一根的 close 作为基准
        prev_close = np.concatenate([[initial_price], close_prices[:-1]])

        # Open 价格 = 前一 Close * (1 + 随机跳空收益率)
        # 这使得 Open 价格可能高于或低于前一 Close，从而产生跳空。
        open_prices = prev_close * (1.0 + open_returns)

        # 4. 计算 High 和 Low (确保 H/L 包含 O/C)
        # 确定 O, H, L, C 四个价格中的最大和最小范围
        # H/L 需要以 O, C 和 C_prev (即 O_t) 为基准扩展，
        # 但简单起见，我们确保 H/L 价格包含 O 和 C 即可。

        # 新的 High 和 Low 基准 (确保 Open 和 Close 在 H/L 范围内)
        max_oc = np.maximum(open_prices, close_prices)
        min_oc = np.minimum(open_prices, close_prices)

        # High = max(O, C) + 额外的波动 (range_factors)
        # 确保 High 价格在 O 和 C 的基础上有一个随机的上涨幅度
        high_prices = max_oc + range_factors * max_oc

        # Low = min(O, C) - 额外的波动 (range_factors)
        # 确保 Low 价格在 O 和 C 的基础上有一个随机的下跌幅度
        low_prices = min_oc - range_factors * min_oc

        # 5. 生成时间序列
        times = start_time + np.arange(num_bars) * interval_ms

        # 6. 构建 DataFrame
        df = pl.DataFrame(
            {
                "time": times,
                "open": open_prices.astype(np.float64),  # 确保类型一致
                "high": high_prices.astype(np.float64),
                "low": low_prices.astype(np.float64),
                "close": close_prices.astype(np.float64),
                "volume": volumes.astype(np.float64),
            }
        )

        # 7. 添加 date 列 (保持不变)
        df = df.with_columns(
            [
                pl.from_epoch(pl.col("time"), time_unit="ms")
                .dt.replace_time_zone("UTC")
                .dt.strftime(time_format)
                .alias("date")
            ]
        )

        df = df.select(
            [
                pl.col(fixed_cols),
                pl.col("*").exclude(fixed_cols),
            ]
        )
        return df


def generate_multi_timeframe_ohlcv(
    timeframes: list[str],
    start_time: int,
    num_bars: int,
    fixed_seed: Optional[int] = None,
) -> list[pl.DataFrame]:
    """
    生成多周期OHLCV数据

    Args:
        timeframes: 时间周期列表,按从小到大排序
        start_time: 起始时间
        num_bars: 最小周期的k线数量
        fixed_seed: 是否使用固定种子,如果为None则使用随机种子,如果是正整数则使用该种子,默认None

    Returns:
        按时间周期从小到大排列的 DataFrame 列表
    """
    if not timeframes:
        return []

    base_interval = parse_timeframe(timeframes[0])

    return [
        generate_ohlcv(
            timeframe=tf,
            start_time=start_time,
            num_bars=int(ceil(num_bars * base_interval / parse_timeframe(tf))),
            initial_price=100.0,
            volatility=0.02,
            fixed_seed=fixed_seed,  # 每个调用都使用相同的种子
        )
        for tf in timeframes
    ]
