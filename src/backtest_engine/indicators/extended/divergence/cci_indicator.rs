use super::config::DivergenceConfig;
use super::expr::divergence_expr;
use crate::backtest_engine::indicators::{
    cci::{cci_lazy, CCIConfig},
    registry::Indicator,
};
use crate::error::QuantError;
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

pub struct CciDivergenceIndicator;

impl Indicator for CciDivergenceIndicator {
    fn calculate(
        &self,
        df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = params.get("period").map(|p| p.value as i64).unwrap_or(14);
        let window = params.get("window").map(|p| p.value as usize).unwrap_or(10);

        let mut cci_cfg = CCIConfig::new(period);
        cci_cfg.alias_name = "cci_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, &cci_cfg.alias_name);
        if let Some(p) = params.get("gap") {
            div_cfg.gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;
        let div_alias = format!("{}_struct", indicator_key);

        let result_df = cci_lazy(df.clone().lazy(), &cci_cfg)?
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
                col(&cci_cfg.alias_name).alias(&format!("{}_value", indicator_key)),
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
}
