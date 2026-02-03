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
    pub gap: i32,
    pub recency: i32,
    pub indicator_col: String,
}

impl DivergenceConfig {
    pub fn new(window: usize, indicator_col: &str) -> Self {
        Self {
            window,
            gap: 3,
            recency: 3,
            indicator_col: indicator_col.to_string(),
        }
    }
}

/// 核心背离计算逻辑 (单次循环计算双向背离)
/// 返回一个 Struct 列，包含 'top' 和 'bottom' 两个 boolean 字段
pub fn divergence_expr(config: &DivergenceConfig) -> Result<Expr, QuantError> {
    let indicator_col = config.indicator_col.clone();
    let window = config.window;
    let gap_threshold = config.gap;
    let recency_threshold = config.recency;

    // 传入 [indicator, high, low]
    // -------------------------------------------------------------------------
    // Custom Kernel Logic
    // -------------------------------------------------------------------------
    // Polars 标准表达式目前不支持 efficient rolling_argmax (返回窗口内最大值的相对索引)。
    // 因此，我们在此手写 Rust 循环 (Kernel) 来实现该逻辑。
    // 这在性能上等同于 (甚至优于) Numpy 的 sliding_window_view + argmax 的底层 C 实现。
    // 它是 Zero-Copy (零拷贝) 的，直接操作底层 Arrow 数组。
    // -------------------------------------------------------------------------
    let div_expr = col(&indicator_col).map_many(
        move |s| {
            let indicator = s[0]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let high = s[1]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let low = s[2]
                .as_materialized_series()
                .f64()
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            let len = indicator.len();

            let mut top_results = Vec::with_capacity(len);
            let mut bot_results = Vec::with_capacity(len);

            // 头部填充
            for _ in 0..(window - 1) {
                top_results.push(false);
                bot_results.push(false);
            }

            // 滑动窗口计算
            for i in (window - 1)..len {
                let start_idx = i + 1 - window;
                let end_idx = i;

                let mut max_p = f64::MIN;
                let mut max_p_idx = 0;
                let mut min_p = f64::MAX;
                let mut min_p_idx = 0;

                let mut max_i = f64::MIN;
                let mut max_i_idx = 0;
                let mut min_i = f64::MAX;
                let mut min_i_idx = 0;

                let mut has_nan = false;

                for j in start_idx..=end_idx {
                    let h = high.get(j).unwrap_or(f64::NAN);
                    let l = low.get(j).unwrap_or(f64::NAN);
                    let ind = indicator.get(j).unwrap_or(f64::NAN);

                    if h.is_nan() || l.is_nan() || ind.is_nan() {
                        has_nan = true;
                        break;
                    }

                    // 找顶 (High)
                    if h >= max_p {
                        max_p = h;
                        max_p_idx = j;
                    }
                    if ind >= max_i {
                        max_i = ind;
                        max_i_idx = j;
                    }

                    // 找底 (Low)
                    if l <= min_p {
                        min_p = l;
                        min_p_idx = j;
                    }
                    if ind <= min_i {
                        min_i = ind;
                        min_i_idx = j;
                    }
                }

                if has_nan {
                    top_results.push(false);
                    bot_results.push(false);
                    continue;
                }

                // 判定顶背离 (Price Peak later than Indicator Peak)
                let top_recency_ok = (end_idx - max_p_idx) < recency_threshold as usize;
                let top_gap = max_p_idx as i32 - max_i_idx as i32;
                let top_ok =
                    top_recency_ok && (max_p_idx > max_i_idx) && (top_gap >= gap_threshold);

                // 判定底背离
                let bot_recency_ok = (end_idx - min_p_idx) < recency_threshold as usize;
                let bot_gap = min_p_idx as i32 - min_i_idx as i32;
                let bot_ok =
                    bot_recency_ok && (min_p_idx > min_i_idx) && (bot_gap >= gap_threshold);

                top_results.push(top_ok);
                bot_results.push(bot_ok);
            }

            let s_top = Series::new("top".into(), top_results);
            let s_bot = Series::new("bottom".into(), bot_results);

            let df_div = df![
                "top" => s_top,
                "bottom" => s_bot
            ]
            .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;

            let s_struct = df_div.into_struct("divergence".into()).into_series();
            Ok(s_struct.into_column())
        },
        &[col("high"), col("low")],
        move |_, _| {
            let fields = vec![
                Field::new("top".into(), DataType::Boolean),
                Field::new("bottom".into(), DataType::Boolean),
            ];
            Ok(Field::new("divergence".into(), DataType::Struct(fields)))
        },
    );

    Ok(div_expr)
}

// --- Specific Implementations ---

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

        let mut macd_cfg = MACDConfig::new(fast, slow, signal);
        macd_cfg.macd_alias = "macd_temp".to_string();

        let mut div_cfg = DivergenceConfig::new(window, &macd_cfg.macd_alias);
        if let Some(p) = params.get("gap") {
            div_cfg.gap = p.value as i32;
        }
        if let Some(p) = params.get("recency") {
            div_cfg.recency = p.value as i32;
        }

        let expr = divergence_expr(&div_cfg)?;
        let div_alias = format!("{}_struct", indicator_key);

        let result_df = macd_lazy(df.clone().lazy(), &macd_cfg)?
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
                col(&macd_cfg.macd_alias).alias(&format!("{}_value", indicator_key)),
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
