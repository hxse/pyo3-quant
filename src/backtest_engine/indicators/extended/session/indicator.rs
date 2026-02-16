use super::config::OpeningBarConfig;
use super::pipeline::opening_bar_eager;
use crate::backtest_engine::indicators::registry::Indicator;
use crate::backtest_engine::utils::validate_timestamp_ms;
use crate::error::QuantError;
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

/// 开盘 K 线检测指标 (基于时间断层)。
pub struct OpeningBarIndicator;

impl Indicator for OpeningBarIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        // 获取阈值（秒），默认 3600 秒（1 小时）。
        let threshold_sec = params.get("threshold").map(|p| p.value).unwrap_or(3600.0);

        let mut config = OpeningBarConfig::new(threshold_sec);
        config.alias_name = indicator_key.to_string();

        // 仅检查第一根时间戳，保持原有校验粒度。
        if let Some(first_time) = ohlcv_df.column("time")?.i64()?.get(0) {
            validate_timestamp_ms(
                first_time,
                &format!("OpeningBarIndicator({})", indicator_key),
            )?;
        }

        let s = opening_bar_eager(ohlcv_df, &config)?;
        Ok(vec![s])
    }
}
