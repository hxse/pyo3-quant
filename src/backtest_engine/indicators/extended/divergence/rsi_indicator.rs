use super::config::DivergenceConfig;
use super::expr::divergence_expr;
use crate::backtest_engine::indicators::{
    registry::{require_resolved_param, Indicator},
    rsi::{rsi_lazy, RSIConfig},
};
use crate::error::QuantError;
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

pub struct RsiDivergenceIndicator;

impl Indicator for RsiDivergenceIndicator {
    fn calculate(
        &self,
        df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = params.get("period").map(|p| p.value as i64).unwrap_or(14);
        let window = params.get("window").map(|p| p.value as usize).unwrap_or(10);

        let mut rsi_cfg = RSIConfig::new(period);
        rsi_cfg.alias_name = "rsi_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, &rsi_cfg.alias_name);
        if let Some(p) = params.get("gap") {
            div_cfg.gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;
        let div_alias = format!("{}_struct", indicator_key);

        let result_df = rsi_lazy(df.clone().lazy(), &rsi_cfg)?
            .with_column(expr.alias(&div_alias))
            .select([
                col(&div_alias)
                    .struct_()
                    .field_by_name("top")
                    .alias(&format!("{}_top", indicator_key)),
                col(&div_alias)
                    .struct_()
                    .field_by_name("bottom")
                    .alias(&format!("{}_bottom", indicator_key)),
                col(&rsi_cfg.alias_name).alias(&format!("{}_value", indicator_key)),
            ])
            .collect()?;

        Ok(vec![
            result_df
                .column(&format!("{}_top", indicator_key))?
                .as_materialized_series()
                .cast(&DataType::Float64)?,
            result_df
                .column(&format!("{}_bottom", indicator_key))?
                .as_materialized_series()
                .cast(&DataType::Float64)?,
            result_df
                .column(&format!("{}_value", indicator_key))?
                .as_materialized_series()
                .clone(),
        ])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // 本指标有效业务列 `_value` 继承 RSI，预热与 RSI 一致。
        let period = require_resolved_param(resolved_params, "period", "rsi-divergence")? as i64;
        Ok(period.max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：RSI divergence 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
