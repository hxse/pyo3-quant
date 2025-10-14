use polars::prelude::*;

pub fn calculate_sma(ohlcv_df: &DataFrame, period: i64) -> PolarsResult<Series> {
    // 从 Column 提取 &Series，并转换为 f64 类型
    let close_column = ohlcv_df.column("close")?;
    let close_series = close_column.as_series().unwrap().cast(&DataType::Float64)?;

    // 配置固定窗口选项
    let options = RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize, // 要求完整窗口，避免部分 NaN
        weights: None,                // 简单均值，无权重
        center: false,                // 右对齐窗口
        fn_params: None,              // 自定义参数，默认为无
    };

    // 在 Series 上直接调用 rolling_mean
    let sma_series = close_series.rolling_mean(options)?;

    Ok(sma_series)
}
