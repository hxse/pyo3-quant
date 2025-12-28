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
    trend: float = 0.0,  # 新增: 趋势系数
    gap_factor: float = 0.5,
    extreme_prob: float = 0.0,  # 新增: 极端行情概率
    extreme_mult: float = 3.0,  # 新增: 极端行情波动倍数
    allow_gaps: bool = True,  # 新增: 是否允许跳空
    fixed_seed: Optional[int] = None,
) -> pl.DataFrame:
    """
    生成单周期OHLCV模拟数据，支持趋势、跳空和极端行情。

    Args:
        timeframe: 时间周期
        start_time: 起始时间
        num_bars: K线数量
        initial_price: 初始价格,默认100.0
        volatility: 波动率,默认0.02
        trend: 趋势系数,正值上涨趋势,负值下跌趋势,默认0
        gap_factor: 跳空因子,控制Open价格相对于前一Close的波动性,默认0.5
        extreme_prob: 极端行情概率,范围0-1,默认0
        extreme_mult: 极端行情波动倍数,默认3.0
        allow_gaps: 是否允许跳空, 默认True. 如果False, Open[i] = Close[i-1]
        fixed_seed: 是否使用固定种子
    """
    interval_ms = parse_timeframe(timeframe)

    with temporary_numpy_seed(fixed_seed):
        # 1. 生成基础收益率 (带趋势)
        returns = np.random.normal(trend, volatility, num_bars)

        # 2. 添加极端行情 (随机选择一些 bar 放大波动)
        if extreme_prob > 0:
            is_extreme = np.random.random(num_bars) < extreme_prob
            # 极端行情时波动放大，且随机选择方向
            extreme_direction = np.random.choice([-1, 1], num_bars)
            extreme_returns = np.random.normal(0, volatility * extreme_mult, num_bars)
            returns = np.where(is_extreme, extreme_returns * extreme_direction, returns)

        # 3. 随机 Open 价格跳空
        if allow_gaps:
            open_returns = np.random.normal(0, volatility * gap_factor, num_bars)
            # 极端行情时跳空也放大
            if extreme_prob > 0:
                extreme_gaps = np.random.normal(
                    0, volatility * gap_factor * extreme_mult, num_bars
                )
                extreme_gap_direction = np.random.choice([-1, 1], num_bars)
                open_returns = np.where(
                    is_extreme, extreme_gaps * extreme_gap_direction, open_returns
                )
        else:
            open_returns = np.zeros(num_bars)

        # High/Low 的波动因子
        range_factors = np.abs(np.random.normal(0, volatility / 3, num_bars))
        # 极端行情时 High/Low 范围更大
        if extreme_prob > 0:
            extreme_range = np.abs(
                np.random.normal(0, volatility * extreme_mult / 3, num_bars)
            )
            range_factors = np.where(is_extreme, extreme_range, range_factors)

        volumes = np.abs(np.random.normal(1000000, 200000, num_bars))

        # 4. 计算 Close 价格 (随机游走)
        price_multipliers = 1.0 + returns
        close_prices = initial_price * np.cumprod(price_multipliers)

        # 5. 计算 Open 价格 (引入跳空)
        prev_close = np.concatenate([[initial_price], close_prices[:-1]])
        open_prices = prev_close * (1.0 + open_returns)

        # 6. 计算 High 和 Low
        max_oc = np.maximum(open_prices, close_prices)
        min_oc = np.minimum(open_prices, close_prices)
        high_prices = max_oc + range_factors * max_oc
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
    volatility: float = 0.02,
    trend: float = 0.0,
    gap_factor: float = 0.5,
    extreme_prob: float = 0.0,
    extreme_mult: float = 3.0,
    allow_gaps: bool = True,
) -> list[pl.DataFrame]:
    """
    生成多周期OHLCV数据

    Args:
        timeframes: 时间周期列表,按从小到大排序
        start_time: 起始时间
        num_bars: 最小周期的k线数量
        fixed_seed: 随机种子
        volatility: 波动率
        trend: 趋势系数
        gap_factor: 跳空因子
        extreme_prob: 极端行情概率
        extreme_mult: 极端行情波动倍数
        allow_gaps: 是否允许跳空

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
            volatility=volatility,
            trend=trend,
            gap_factor=gap_factor,
            extreme_prob=extreme_prob,
            extreme_mult=extreme_mult,
            allow_gaps=allow_gaps,
            fixed_seed=fixed_seed,
        )
        for tf in timeframes
    ]
