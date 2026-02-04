use crate::backtest_engine::indicators::registry::Indicator;
use crate::backtest_engine::utils::validate_timestamp_ms;
use crate::error::QuantError;
use crate::types::Param;
use polars::prelude::*;
use polars::series::ops::NullBehavior;

use std::collections::HashMap;

/// 开盘 K 线检测指标 (基于时间断层)
pub struct OpeningBarIndicator;

impl Indicator for OpeningBarIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        // 获取阈值（秒），默认为 1 小时 (3600s)
        let threshold_sec = params.get("threshold").map(|p| p.value).unwrap_or(3600.0);
        let threshold_ms = (threshold_sec * 1000.0) as i64;

        // 命名规则: {key}
        let alias = indicator_key.to_string();

        if let Some(first_time) = ohlcv_df.column("time")?.i64()?.get(0) {
            validate_timestamp_ms(
                first_time,
                &format!("OpeningBarIndicator({})", indicator_key),
            )?;
        }

        let lazy_df = ohlcv_df.clone().lazy();

        // 核心计算:
        // 1. 计算相邻 time 的差值 (假设单位为 ms)
        // 2. 差值 > threshold_ms 判定为开盘
        // 3. 第一根 K 线 (diff 为 null) 默认判定为不开盘 (fill_null(false))
        let result_df = lazy_df
            .with_column(
                (col("time").diff(lit(1), NullBehavior::Ignore))
                    .gt(lit(threshold_ms))
                    .fill_null(lit(false))
                    .cast(DataType::Float64)
                    .alias(&alias),
            )
            .select([col(&alias)])
            .collect()?;

        let s = result_df.column(&alias)?.as_materialized_series().clone();
        Ok(vec![s])
    }
}
