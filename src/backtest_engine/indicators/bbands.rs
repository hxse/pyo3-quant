use polars::prelude::*;

pub fn calculate_bbands(
    ohlcv_df: &DataFrame,
    length: i64,
    std_multiplier: f64,
) -> PolarsResult<(Series, Series, Series, Series, Series)> {
    // 从 DataFrame 中提取 "close" 列并转换为 f64 类型
    let close_column = ohlcv_df.column("close")?;
    let close_series = close_column.as_series().unwrap().cast(&DataType::Float64)?;

    // 配置滚动窗口选项，并添加 RollingFnParams 以设置 ddof=0
    let options = RollingOptionsFixedWindow {
        window_size: length as usize,
        min_periods: length as usize, // 确保前导 NaN 数量正确
        weights: None,
        center: false,
        fn_params: Some(RollingFnParams::Var(RollingVarParams { ddof: 0 })),
    };

    // 1. 计算 Middle Band (SMA)
    let middle_band = close_series.rolling_mean(options.clone())?;

    // 2. 计算 Standard Deviation (使用 ddof=0)
    let std_dev = close_series.rolling_std(options)?; // 现已通过 fn_params 设置 ddof=0

    // 3. 计算 Upper/Lower Bands
    let std_multiplier_series = Series::new(PlSmallStr::from("std_multiplier"), &[std_multiplier]);
    let upper_band_temp = (&std_dev * &std_multiplier_series)?;
    let upper_band = (&middle_band + &upper_band_temp)?;
    let lower_band_temp = (&std_dev * &std_multiplier_series)?;
    let lower_band = (&middle_band - &lower_band_temp)?;

    // 4. 计算 Bandwidth
    let diff_bands = (&upper_band - &lower_band)?;
    let hundred_series = Series::new(PlSmallStr::from("100"), &[100.0]);
    let bandwidth_numerator = (&hundred_series * &diff_bands)?;
    let bandwidth = (&bandwidth_numerator / &middle_band)?;

    // 5. 计算 Percent
    let close_minus_lower = (&close_series - &lower_band)?;
    let upper_minus_lower = (&upper_band - &lower_band)?;
    let percent_b = (&close_minus_lower / &upper_minus_lower)?;

    Ok((lower_band, middle_band, upper_band, bandwidth, percent_b))
}
