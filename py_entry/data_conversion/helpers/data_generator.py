"""
模拟交易数据生成模块
使用 numpy 进行矢量化随机数生成,polars 进行数据处理
"""

import polars as pl
import numpy as np
from datetime import datetime
import math

from ..input import DataContainer

time_format = "%Y-%m-%dT%H:%M:%S%.3f%Z"
fixed_cols = ["time", "date"]


def parse_timeframe(tf: str) -> int:
    """
    将时间周期字符串转换为毫秒数

    Args:
        tf: 时间周期字符串,如 "15m", "1h", "4h", "1d"

    Returns:
        毫秒数
    """
    unit = tf[-1]
    value = int(tf[:-1])

    if unit == "m":
        return value * 60 * 1000
    elif unit == "h":
        return value * 60 * 60 * 1000
    elif unit == "d":
        return value * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"不支持的时间周期单位: {unit}")


def generate_ohlcv(
    timeframe: str,
    start_time: int,
    num_bars: int,
    initial_price: float = 100.0,
    volatility: float = 0.02,
    gap_factor: float = 0.5,  # 新增参数: 控制 Open 价格相对于前一 Close 的波动性
) -> pl.DataFrame:
    """
    生成单周期OHLCV模拟数据，引入随机跳空，更接近真实K线市场。
    """
    # 假设 parse_timeframe, time_format, fixed_cols, pl, np 已在上下文导入或定义
    # 这是一个 Python 函数，但根据用户要求，我们将返回中文回复。
    interval_ms = parse_timeframe(timeframe)

    # 1. 使用 numpy 生成所有随机数
    np.random.seed(42)
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
    timeframes: list[str], start_time: int, num_bars: int
) -> list[pl.DataFrame]:
    """
    生成多周期OHLCV数据

    Args:
        timeframes: 时间周期列表,按从小到大排序
        start_time: 起始时间
        num_bars: 最小周期的k线数量

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
            num_bars=int(math.ceil(num_bars * base_interval / parse_timeframe(tf))),
            initial_price=100.0,
            volatility=0.02,
        )
        for tf in timeframes
    ]


def calculate_heikin_ashi(df: pl.DataFrame) -> pl.DataFrame:
    """
    计算 Heikin-Ashi (平均K线),返回标准OHLCV格式

    Args:
        df: 包含 OHLC 数据的 DataFrame

    Returns:
        包含 time, date, open, high, low, close, volume 列的 DataFrame
    """
    # 提取 OHLC 数据为 numpy 数组(矢量化)
    open_arr = df["open"].to_numpy()
    high_arr = df["high"].to_numpy()
    low_arr = df["low"].to_numpy()
    close_arr = df["close"].to_numpy()

    # 计算 HA_Close(完全矢量化)
    ha_close = (open_arr + high_arr + low_arr + close_arr) / 4.0

    # 计算 HA_Open(递归关系,算法固有特性)
    # 初始化 HA_Open 数组
    ha_open = np.empty(len(df))
    ha_open[0] = (open_arr[0] + close_arr[0]) / 2.0

    # 使用 numpy 批量计算递归关系(最优化的算法实现)
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0

    # 计算 HA_High 和 HA_Low(完全矢量化)
    ha_high = np.maximum(np.maximum(high_arr, ha_open), ha_close)
    ha_low = np.minimum(np.minimum(low_arr, ha_open), ha_close)

    # 构建并返回标准OHLCV格式的 DataFrame
    result = pl.DataFrame(
        {
            "time": df["time"],
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
            "volume": df["volume"] if "volume" in df.columns else np.zeros(len(df)),
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


def generate_ha(ohlcv_dfs: list[pl.DataFrame]) -> list[pl.DataFrame]:
    """
    生成Heikin-Ashi数据,返回标准OHLCV格式

    Args:
        ohlcv_dfs: OHLCV DataFrame列表

    Returns:
        HA DataFrame列表,字段为: time, date, open, high, low, close, volume
    """
    return [calculate_heikin_ashi(df) for df in ohlcv_dfs]


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


def generate_time_mapping(
    ohlcv_dfs: list[pl.DataFrame],
    ha_dfs: list[pl.DataFrame],
    renko_dfs: list[pl.DataFrame],
) -> pl.DataFrame:
    """
    生成时间映射,将ohlcv[0]的time映射到所有其他DataFrame的索引

    Args:
        ohlcv_dfs: OHLCV DataFrame列表
        ha_dfs: HA DataFrame列表
        renko_dfs: Renko DataFrame列表

    Returns:
        单个DataFrame,包含列:
        - ohlcv_0: ohlcv[0]的行索引 [0, 1, 2, ..., n-1]
        - ohlcv_1: ohlcv[0].time -> ohlcv[1]的索引映射
        - ha_0: ohlcv[0].time -> ha[0]的索引映射
        - ha_1: ohlcv[0].time -> ha[1]的索引映射
        - renko_0: ohlcv[0].time -> renko[0]的索引映射
        - renko_1: ohlcv[0].time -> renko[1]的索引映射
    """
    if not ohlcv_dfs:
        return pl.DataFrame()

    base_df = ohlcv_dfs[0]

    # ohlcv_0: 基准索引
    result = pl.DataFrame({"ohlcv_0": np.arange(len(base_df))})

    # 映射其他ohlcv DataFrame
    for i, df in enumerate(ohlcv_dfs[1:], 1):
        df_with_idx = df.select("time").with_columns(
            [pl.Series(f"idx_ohlcv_{i}", np.arange(len(df)))]
        )
        mapping = (
            base_df.select("time")
            .join_asof(df_with_idx, on="time", strategy="backward")
            .select(pl.col(f"idx_ohlcv_{i}"))
        )
        result = result.with_columns([mapping.to_series().alias(f"ohlcv_{i}")])

    # 映射ha DataFrame
    for i, df in enumerate(ha_dfs):
        df_with_idx = df.select("time").with_columns(
            [pl.Series(f"idx_ha_{i}", np.arange(len(df)))]
        )
        mapping = (
            base_df.select("time")
            .join_asof(df_with_idx, on="time", strategy="backward")
            .select(pl.col(f"idx_ha_{i}"))
        )
        result = result.with_columns([mapping.to_series().alias(f"ha_{i}")])

    # 映射renko DataFrame
    for i, df in enumerate(renko_dfs):
        df_with_idx = df.select("time").with_columns(
            [pl.Series(f"idx_renko_{i}", np.arange(len(df)))]
        )
        mapping = (
            base_df.select("time")
            .join_asof(df_with_idx, on="time", strategy="backward")
            .select(pl.col(f"idx_renko_{i}"))
        )
        result = result.with_columns([mapping.to_series().alias(f"renko_{i}")])

    return result


def generate_data_dict(
    timeframes: list[str],
    start_time: int,
    num_bars: int = 1000,
    brick_size: float = 2.0,
) -> DataContainer:
    """
    生成完整的数据字典

    Args:
        timeframes: 时间周期列表,默认 ["15m", "1h", "4h"]
        start_time: 起始时间(毫秒级时间戳),如果为 None 则使用当前时间减去合理偏移
        num_bars: 最小周期的k线数量,默认1000
        brick_size: Renko砖块大小,默认2.0

    Returns:
        包含以下键的字典:
    """
    if start_time is None:
        # 默认从当前时间往前推 num_bars * 最小时间周期
        min_timeframe_ms = parse_timeframe(timeframes[0])
        start_time = (
            int(datetime.now().timestamp() * 1000) - num_bars * min_timeframe_ms
        )

    ohlcv_dfs = generate_multi_timeframe_ohlcv(timeframes, start_time, num_bars)
    ha_dfs = generate_ha(ohlcv_dfs)
    renko_dfs = generate_renko(ohlcv_dfs, brick_size)

    mapping_df = generate_time_mapping(ohlcv_dfs, ha_dfs, renko_dfs)

    # skip_mask 占位,暂时全为 False
    skip_mask_df = pl.DataFrame(
        {"skip": [False] * len(ohlcv_dfs[0])}, schema={"skip": pl.Boolean}
    )

    return DataContainer(
        mapping=mapping_df,
        skip_mask=skip_mask_df,
        source={
            "ohlcv": ohlcv_dfs,
            "ha": ha_dfs,
            "renko": renko_dfs,
        },
    )
