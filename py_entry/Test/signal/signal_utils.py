"""
信号生成测试工具函数

提供信号生成测试所需的辅助函数，包括：
- 指标数据提取
- 信号计算
- 结果统计和比较
"""

import polars as pl


def extract_indicator_data(indicators_df, indicator_name):
    """从指标DataFrame中提取特定指标数据"""
    try:
        return indicators_df.select(indicator_name).to_series()
    except pl.exceptions.ColumnNotFoundError:
        raise ValueError(f"指标 {indicator_name} 未在DataFrame中找到")


def print_signal_statistics(signals_df, title):
    """打印信号统计信息"""
    print(f"\n{title}:")
    print(f"总行数: {len(signals_df)}")
    for col in signals_df.columns:
        true_count = signals_df[col].sum()
        percentage = true_count / len(signals_df) * 100
        print(f"  {col}: {true_count} 个True信号 ({percentage:.2f}%)")


def apply_mapping_if_needed(series, source_key, processed_data):
    """应用映射逻辑，与Rust端的apply_mapping_if_needed函数一致"""
    if processed_data is None:
        # 如果没有processed_data，直接返回原始Series
        return series

    # 统一处理：先获取映射状态和数据
    if not processed_data.skip_mapping.get(source_key, False):
        # 执行映射逻辑
        mapping_df = processed_data.mapping

        if source_key in mapping_df.columns:
            # 获取映射索引
            index_series = mapping_df[source_key]

            # 转换为UInt32类型，与Rust端一致
            index_series_u32 = index_series.cast(pl.UInt32)

            # 应用映射 - Python Polars使用gather而不是take
            mapped_series = series.gather(index_series_u32)
            return mapped_series
        else:
            raise ValueError(f"映射列 {source_key} 未找到")
    else:
        # 不需要映射，直接返回原始Series
        return series


def calculate_signals_manually(
    processed_data,
    signal_params,
    indicators_15m,
    indicators_1h,
    indicators_4h,
    source_data_15m,
    source_data_1h,
    source_data_4h,
):
    """
    手动计算信号，模拟Rust端的信号生成逻辑

    Args:
        indicators_15m: ohlcv_15m时间框架的指标DataFrame
        indicators_1h: ohlcv_1h时间框架的指标DataFrame
        indicators_4h: ohlcv_4h时间框架的指标DataFrame
        signal_params: 信号参数字典
        source_data_15m: ohlcv_15m时间框架的原始数据DataFrame（可选）
        source_data_1h: ohlcv_1h时间框架的原始数据DataFrame（可选）
        source_data_4h: ohlcv_4h时间框架的原始数据DataFrame（可选）
        processed_data: DataContainer对象，包含映射信息（可选）

    Returns:
        包含enter_long、exit_long、enter_short、exit_short的DataFrame
    """
    # 获取信号参数

    # 计算多时间框架信号组：多时间框架确认策略
    # 从indicators_4h获取sma_0，从indicators_1h获取rsi_0并应用映射
    sma_0_series = extract_indicator_data(indicators_4h, "sma_0")
    sma_1_series = extract_indicator_data(indicators_4h, "sma_1")
    rsi_0_series = extract_indicator_data(indicators_1h, "rsi_0")
    bbands_0_upper_series = extract_indicator_data(indicators_15m, "bbands_0_upper")
    bbands_0_lower_series = extract_indicator_data(indicators_15m, "bbands_0_lower")

    # 统一通过映射函数处理，函数内部会判断是否需要映射
    sma_0_mapped = apply_mapping_if_needed(sma_0_series, "ohlcv_4h", processed_data)
    sma_1_mapped = apply_mapping_if_needed(sma_1_series, "ohlcv_4h", processed_data)
    rsi_0_mapped = apply_mapping_if_needed(rsi_0_series, "ohlcv_1h", processed_data)
    bbands_0_upper_mapped = apply_mapping_if_needed(
        bbands_0_upper_series, "ohlcv_15m", processed_data
    )
    bbands_0_lower_mapped = apply_mapping_if_needed(
        bbands_0_lower_series, "ohlcv_15m", processed_data
    )

    close = source_data_15m["close"]

    # long
    enter_long_1 = sma_0_mapped > sma_1_mapped

    enter_long_2 = rsi_0_mapped < signal_params["rsi_lower"].value

    enter_long_3 = (close > bbands_0_upper_mapped) & (
        close.shift(1) > bbands_0_upper_mapped.shift(1)
    ).not_()

    enter_long = enter_long_1 & enter_long_2 & enter_long_3

    exit_long = close < bbands_0_upper_mapped

    # short
    enter_short_1 = sma_0_mapped < sma_1_mapped

    enter_short_2 = rsi_0_mapped > signal_params["rsi_upper"].value

    enter_short_3 = (close < bbands_0_lower_mapped) & (
        close.shift(1) < bbands_0_lower_mapped.shift(1)
    ).not_()

    enter_short = enter_short_1 & enter_short_2 & enter_short_3

    exit_short = close > bbands_0_lower_mapped

    result = pl.DataFrame(
        {
            "enter_long": enter_long.fill_null(False),
            "exit_long": exit_long.fill_null(False),
            "enter_short": enter_short.fill_null(False),
            "exit_short": exit_short.fill_null(False),
        }
    )

    return result
