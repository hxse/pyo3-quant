use super::super::registry::Indicator;
use super::config::TRConfig;
use super::pipeline::tr_eager;
use crate::error::QuantError;
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct TrIndicator;

impl Indicator for TrIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        _param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let mut config = TRConfig::new();
        config.alias_name = indicator_key.to_string();

        let result_series = tr_eager(ohlcv_df, &config)?;
        Ok(vec![result_series])
    }

    fn required_warmup_bars(
        &self,
        _resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // TR 依赖前一根 close，首根为预热。
        Ok(1)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：TR 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
