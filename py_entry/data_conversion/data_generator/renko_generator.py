"""
Renko 数据生成模块
"""

import polars as pl
import numpy as np

from .time_utils import time_format, fixed_cols


def calculate_renko(df: pl.DataFrame, brick_size: float = 2.0) -> pl.DataFrame:
    """
    计算Renko砖块

    Renko特点:
    - 固定砖块大小(brick_size)
    - 价格变化达到brick_size才形成新砖块
    - 只有上升砖和下降砖两种
    - 无影线(high=close或low=close)

    Args:
        df: OHLCV DataFrame
        brick_size: 砖块大小,默认2.0

    Returns:
        Renko DataFrame,字段为: time, date, open, high, low, close, volume
    """
    # 提取价格数据
    close_prices = df["close"].to_numpy()
    times = df["time"].to_numpy()
    volumes = df["volume"].to_numpy()

    # 初始化结果列表
    renko_times = []
    renko_opens = []
    renko_highs = []
    renko_lows = []
    renko_closes = []
    renko_volumes = []

    # 初始化第一个砖块
    current_brick_open = close_prices[0]
    current_direction = 0  # 0: 未确定, 1: 上升, -1: 下降
    volume_accumulator = 0.0

    for i in range(len(close_prices)):
        current_price = close_prices[i]
        volume_accumulator += volumes[i]

        if current_direction == 0:
            # 确定初始方向
            price_diff = current_price - current_brick_open
            if price_diff >= brick_size:
                # 上升砖
                current_direction = 1
                renko_times.append(times[i])
                renko_opens.append(current_brick_open)
                renko_closes.append(current_brick_open + brick_size)
                renko_highs.append(current_brick_open + brick_size)
                renko_lows.append(current_brick_open)
                renko_volumes.append(volume_accumulator)
                current_brick_open = current_brick_open + brick_size
                volume_accumulator = 0.0
            elif price_diff <= -brick_size:
                # 下降砖
                current_direction = -1
                renko_times.append(times[i])
                renko_opens.append(current_brick_open)
                renko_closes.append(current_brick_open - brick_size)
                renko_highs.append(current_brick_open)
                renko_lows.append(current_brick_open - brick_size)
                renko_volumes.append(volume_accumulator)
                current_brick_open = current_brick_open - brick_size
                volume_accumulator = 0.0
        else:
            # 已有方向,检查是否形成新砖块
            if current_direction == 1:
                # 当前是上升趋势
                price_diff = current_price - current_brick_open
                if price_diff >= brick_size:
                    # 继续上升砖
                    num_bricks = int(price_diff / brick_size)
                    for _ in range(num_bricks):
                        renko_times.append(times[i])
                        renko_opens.append(current_brick_open)
                        renko_closes.append(current_brick_open + brick_size)
                        renko_highs.append(current_brick_open + brick_size)
                        renko_lows.append(current_brick_open)
                        renko_volumes.append(volume_accumulator / num_bricks)
                        current_brick_open = current_brick_open + brick_size
                    volume_accumulator = 0.0
                elif price_diff <= -2 * brick_size:
                    # 反转为下降砖(需要至少2个砖块的反向移动)
                    current_direction = -1
                    num_bricks = int(abs(price_diff + brick_size) / brick_size)
                    for _ in range(num_bricks):
                        renko_times.append(times[i])
                        renko_opens.append(current_brick_open)
                        renko_closes.append(current_brick_open - brick_size)
                        renko_highs.append(current_brick_open)
                        renko_lows.append(current_brick_open - brick_size)
                        renko_volumes.append(volume_accumulator / num_bricks)
                        current_brick_open = current_brick_open - brick_size
                    volume_accumulator = 0.0
            else:
                # 当前是下降趋势
                price_diff = current_price - current_brick_open
                if price_diff <= -brick_size:
                    # 继续下降砖
                    num_bricks = int(abs(price_diff) / brick_size)
                    for _ in range(num_bricks):
                        renko_times.append(times[i])
                        renko_opens.append(current_brick_open)
                        renko_closes.append(current_brick_open - brick_size)
                        renko_highs.append(current_brick_open)
                        renko_lows.append(current_brick_open - brick_size)
                        renko_volumes.append(volume_accumulator / num_bricks)
                        current_brick_open = current_brick_open - brick_size
                    volume_accumulator = 0.0
                elif price_diff >= 2 * brick_size:
                    # 反转为上升砖(需要至少2个砖块的反向移动)
                    current_direction = 1
                    num_bricks = int((price_diff - brick_size) / brick_size)
                    for _ in range(num_bricks):
                        renko_times.append(times[i])
                        renko_opens.append(current_brick_open)
                        renko_closes.append(current_brick_open + brick_size)
                        renko_highs.append(current_brick_open + brick_size)
                        renko_lows.append(current_brick_open)
                        renko_volumes.append(volume_accumulator / num_bricks)
                        current_brick_open = current_brick_open + brick_size
                    volume_accumulator = 0.0

    # 如果没有生成任何砖块,返回空DataFrame但保持相同的列结构
    if not renko_times:
        result = pl.DataFrame(
            {
                "time": pl.Series([], dtype=pl.Int64),
                "open": pl.Series([], dtype=pl.Float64),
                "high": pl.Series([], dtype=pl.Float64),
                "low": pl.Series([], dtype=pl.Float64),
                "close": pl.Series([], dtype=pl.Float64),
                "volume": pl.Series([], dtype=pl.Float64),
            }
        )
        result = result.with_columns([pl.lit("").alias("date")])
        return result.select(
            [
                pl.col(fixed_cols),
                pl.col("*").exclude(fixed_cols),
            ]
        )

    # 构建DataFrame
    result = pl.DataFrame(
        {
            "time": renko_times,
            "open": renko_opens,
            "high": renko_highs,
            "low": renko_lows,
            "close": renko_closes,
            "volume": renko_volumes,
        }
    )

    # 添加 date 列
    result = result.with_columns(
        [
            pl.from_epoch(result["time"], time_unit="ms")
            .dt.replace_time_zone("UTC")
            .dt.strftime(time_format)
            .alias("date")
        ]
    )

    # 确保列顺序为: time, date, open, high, low, close, volume
    result = result.select(
        [
            pl.col(fixed_cols),  # time, date
            pl.col("*").exclude(fixed_cols),
        ]
    )

    return result


def generate_renko(
    ohlcv_dfs: list[pl.DataFrame], brick_size: float = 2.0
) -> list[pl.DataFrame]:
    """
    生成Renko数据,返回标准OHLCV格式

    Args:
        ohlcv_dfs: OHLCV DataFrame列表
        brick_size: 砖块大小

    Returns:
        Renko DataFrame列表,字段为: time, date, open, high, low, close, volume
    """
    return [calculate_renko(df, brick_size) for df in ohlcv_dfs]
