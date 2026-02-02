use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

use super::{registry::Indicator, utils::null_to_nan_expr};
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use std::collections::HashMap;

/// EMA 的配置结构体
pub struct EMAConfig {
    pub period: i64,                    // EMA 周期
    pub column_name: String,            // 要计算 EMA 的输入列名 (e.g., "close")
    pub alias_name: String,             // EMA 结果的输出别名 (e.g., "ema")
    pub processed_column_alias: String, // 处理后的列的别名，用于避免冲突
    pub initial_value_temp: String,
    pub start_offset: i64,  // 新增：有效数据起始偏移，用于如 MACD signal 的场景
    pub ignore_nulls: bool, // 新增：是否忽略NULL值，默认true
}

impl EMAConfig {
    /// 创建一个新的 EMAConfig 实例。
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "ema".to_string(),
            processed_column_alias: "ema_processed_close_temp".to_string(),
            initial_value_temp: "ema_initial_value_temp".to_string(),
            start_offset: 0,
            ignore_nulls: true, // 默认true，匹配原有逻辑
        }
    }
}

// --- 表达式分离函数 ---
/// 🔍 返回计算 EMA 所需的所有核心表达式。
pub fn ema_expr(config: &EMAConfig) -> Result<(Expr, Expr), QuantError> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;
    let processed_column_alias = config.processed_column_alias.as_str();
    let initial_value_temp_name = config.initial_value_temp.as_str();
    let index_col_name = "index";
    let start_offset = config.start_offset;
    let alpha = 2.0 / (period as f64 + 1.0);

    // 1. SMA 初始值表达式
    let sma_initial_value_expr = col(col_name)
        .slice(lit(start_offset), lit(period as u32))
        .mean()
        .cast(DataType::Float64)
        .alias(initial_value_temp_name);

    // 初始值的放置位置
    let initial_idx = start_offset + period - 1;

    // 2. processed 表达式
    let processed_expr = when(
        col(index_col_name)
            .cast(DataType::Int64)
            .lt(lit(initial_idx)),
    )
    .then(lit(NULL))
    .when(
        col(index_col_name)
            .cast(DataType::Int64)
            .eq(lit(initial_idx)),
    )
    .then(sma_initial_value_expr)
    .otherwise(col(col_name).cast(DataType::Float64))
    .alias(processed_column_alias);

    // 3. EMA 表达式，使用配置的ignore_nulls
    let ema_expr = col(processed_column_alias)
        .ewm_mean(EWMOptions {
            alpha,
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: config.ignore_nulls, // 使用配置值
        })
        .cast(DataType::Float64)
        .alias(alias_name);

    Ok((processed_expr, ema_expr))
}

// --- 蓝图函数 (复用分离出的表达式) ---
pub fn ema_lazy(lazy_df: LazyFrame, config: &EMAConfig) -> Result<LazyFrame, QuantError> {
    let (processed_close_expr, ema_expr) = ema_expr(config)?;
    let result_lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(processed_close_expr)
        .with_column(ema_expr)
        // 在蓝图层将 EMA 结果的 NULL 转换为 NaN
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

// --- Eager 包装函数 (保持不变) ---
pub fn ema_eager(ohlcv_df: &DataFrame, config: &EMAConfig) -> Result<Series, QuantError> {
    let alias_name = &config.alias_name;
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            alias_name.to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }
    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty(
            config.alias_name.clone().into(),
            &DataType::Float64,
        ));
    }
    let n_periods = config.period as usize;
    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort(
            alias_name.to_string(),
            config.period,
            series_len as i64,
        )
        .into());
    }
    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = ema_lazy(lazy_df, config)?;
    let result_df = lazy_plan
        .select([col(alias_name)])
        .collect()
        .map_err(QuantError::from)?;
    Ok(result_df
        .column(alias_name)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone())
}

pub struct EmaIndicator;

impl Indicator for EmaIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = params
            .get("period")
            .ok_or_else(|| {
                crate::error::IndicatorError::ParameterNotFound(
                    "period".to_string(),
                    indicator_key.to_string(),
                )
            })?
            .value as i64;

        let mut config = EMAConfig::new(period);
        config.alias_name = indicator_key.to_string();
        let ema_series = ema_eager(ohlcv_df, &config)?;
        Ok(vec![ema_series])
    }
}
