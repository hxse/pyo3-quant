use crate::backtest_engine::indicators::{
    cci::{cci_lazy, CCIConfig},
    macd::{macd_lazy, MACDConfig},
    registry::Indicator,
    rsi::{rsi_lazy, RSIConfig},
};
use crate::error::QuantError;
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

/// 通用背离检测配置
pub struct DivergenceConfig {
    pub window: usize,
    pub idx_gap: i32,
    pub recency: i32,
    pub is_high_mode: bool,
    pub price_col: String,
    pub indicator_col: String,
    pub signal_alias: String,
    pub value_alias: String,
}

impl DivergenceConfig {
    pub fn new(window: usize, is_high_mode: bool, indicator_col: &str) -> Self {
        Self {
            window,
            idx_gap: 3,
            recency: 3,
            is_high_mode,
            price_col: if is_high_mode {
                "high".to_string()
            } else {
                "low".to_string()
            },
            indicator_col: indicator_col.to_string(),
            signal_alias: "div".to_string(),
            value_alias: "value".to_string(),
        }
    }
}

pub fn divergence_expr(config: &DivergenceConfig) -> Result<Expr, QuantError> {
    let price_col = config.price_col.clone();
    let indicator_col = config.indicator_col.clone();
    let window = config.window;
    let idx_gap_threshold = config.idx_gap;
    let recency_threshold = config.recency;
    let is_high_mode = config.is_high_mode;

    let div_expr = col(&price_col).map_many(
        move |s| {
            let prices = s[0].as_materialized_series().f64()?;
            let indicator = s[1].as_materialized_series().f64()?;
            let len = prices.len();
            let mut builder = BooleanChunkedBuilder::new("divergence".into(), len);

            for _ in 0..(window - 1) {
                builder.append_value(false);
            }

            for i in (window - 1)..len {
                let start_idx = i + 1 - window;
                let end_idx = i;
                let mut peak_p_val = if is_high_mode { f64::MIN } else { f64::MAX };
                let mut peak_p_idx: usize = 0;
                let mut peak_i_val = if is_high_mode { f64::MIN } else { f64::MAX };
                let mut peak_i_idx: usize = 0;
                let mut has_nan = false;

                for j in start_idx..=end_idx {
                    let p = prices.get(j).unwrap_or(f64::NAN);
                    let ind = indicator.get(j).unwrap_or(f64::NAN);
                    if p.is_nan() || ind.is_nan() {
                        has_nan = true;
                        break;
                    }

                    if is_high_mode {
                        if p >= peak_p_val {
                            peak_p_val = p;
                            peak_p_idx = j;
                        }
                        if ind >= peak_i_val {
                            peak_i_val = ind;
                            peak_i_idx = j;
                        }
                    } else {
                        if p <= peak_p_val {
                            peak_p_val = p;
                            peak_p_idx = j;
                        }
                        if ind <= peak_i_val {
                            peak_i_val = ind;
                            peak_i_idx = j;
                        }
                    }
                }

                if has_nan {
                    builder.append_value(false);
                    continue;
                }

                let recency_ok = (end_idx - peak_p_idx) < recency_threshold as usize;
                let idx_gap = peak_p_idx as i32 - peak_i_idx as i32;
                let divergence_ok = (peak_p_idx > peak_i_idx) && (idx_gap >= idx_gap_threshold);
                builder.append_value(recency_ok && divergence_ok);
            }
            Ok(builder.finish().into_series().into())
        },
        &[col(&indicator_col)],
        move |_, _| Ok(Field::new("divergence".into(), DataType::Boolean)),
    );

    Ok(div_expr.alias(&config.signal_alias))
}

// --- 特定指标实现 ---

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
        let mode_val = params.get("mode").map(|p| p.value).unwrap_or(0.0);

        let mut cci_cfg = CCIConfig::new(period);
        cci_cfg.alias_name = "cci_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, mode_val == 0.0, &cci_cfg.alias_name);
        div_cfg.signal_alias = format!("{}_div", indicator_key);
        div_cfg.value_alias = format!("{}_cci", indicator_key);
        if let Some(p) = params.get("idx_gap") {
            div_cfg.idx_gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;

        // 核心组合：基础指标 Lazy -> 背离计算 Expr -> 一次 Collect
        let result_df = cci_lazy(df.clone().lazy(), &cci_cfg)?
            .with_column(expr)
            .select([
                col(&div_cfg.signal_alias),
                col(&cci_cfg.alias_name).alias(&div_cfg.value_alias),
            ])
            .collect()?;

        Ok(vec![
            result_df
                .column(&div_cfg.signal_alias)?
                .as_materialized_series()
                .cast(&DataType::Float64)?,
            result_df
                .column(&div_cfg.value_alias)?
                .as_materialized_series()
                .clone(),
        ])
    }
}

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
        let mode_val = params.get("mode").map(|p| p.value).unwrap_or(0.0);

        let mut rsi_cfg = RSIConfig::new(period);
        rsi_cfg.alias_name = "rsi_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, mode_val == 0.0, &rsi_cfg.alias_name);
        div_cfg.signal_alias = format!("{}_div", indicator_key);
        div_cfg.value_alias = format!("{}_rsi", indicator_key);
        if let Some(p) = params.get("idx_gap") {
            div_cfg.idx_gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;

        let result_df = rsi_lazy(df.clone().lazy(), &rsi_cfg)?
            .with_column(expr)
            .select([
                col(&div_cfg.signal_alias),
                col(&rsi_cfg.alias_name).alias(&div_cfg.value_alias),
            ])
            .collect()?;

        Ok(vec![
            result_df
                .column(&div_cfg.signal_alias)?
                .as_materialized_series()
                .cast(&DataType::Float64)?,
            result_df
                .column(&div_cfg.value_alias)?
                .as_materialized_series()
                .clone(),
        ])
    }
}

pub struct MacdDivergenceIndicator;
impl Indicator for MacdDivergenceIndicator {
    fn calculate(
        &self,
        df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let fast = params
            .get("fast_period")
            .map(|p| p.value as i64)
            .unwrap_or(12);
        let slow = params
            .get("slow_period")
            .map(|p| p.value as i64)
            .unwrap_or(26);
        let signal = params
            .get("signal_period")
            .map(|p| p.value as i64)
            .unwrap_or(9);
        let window = params.get("window").map(|p| p.value as usize).unwrap_or(10);
        let mode_val = params.get("mode").map(|p| p.value).unwrap_or(0.0);

        let mut macd_cfg = MACDConfig::new(fast, slow, signal);
        macd_cfg.macd_alias = "macd_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, mode_val == 0.0, &macd_cfg.macd_alias);
        div_cfg.signal_alias = format!("{}_div", indicator_key);
        div_cfg.value_alias = format!("{}_macd", indicator_key);
        if let Some(p) = params.get("idx_gap") {
            div_cfg.idx_gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;

        let result_df = macd_lazy(df.clone().lazy(), &macd_cfg)?
            .with_column(expr)
            .select([
                col(&div_cfg.signal_alias),
                col(&macd_cfg.macd_alias).alias(&div_cfg.value_alias),
            ])
            .collect()?;

        Ok(vec![
            result_df
                .column(&div_cfg.signal_alias)?
                .as_materialized_series()
                .cast(&DataType::Float64)?,
            result_df
                .column(&div_cfg.value_alias)?
                .as_materialized_series()
                .clone(),
        ])
    }
}
