use super::registry::Indicator;
use super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

/// 简单移动平均线 (SMA) 的配置结构体
pub struct SMAConfig {
    pub period: i64,
    pub column_name: String, // 要计算 SMA 的输入列名
    pub alias_name: String,  // SMA 结果的输出别名
}

impl SMAConfig {
    /// 创建 SMAConfig 的新实例。
    ///
    /// # 参数
    /// * `period` - SMA 的周期。
    ///
    /// # 返回
    /// `SMAConfig` 的新实例。
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "sma".to_string(),
        }
    }
}

// --- 表达式层 ---

/// 🔍 返回计算简单移动平均线 (SMA) 的 Polars 表达式
///
/// **表达式层 (Expr)**
/// 接收配置结构体，实现了参数的高度抽象化。
pub fn sma_expr(config: &SMAConfig) -> Result<Expr, QuantError> {
    let column_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "sma".to_string(),
            "Period must be positive for SMA calculation".to_string(),
        )
        .into());
    }

    let sma_expr = col(column_name) // 使用抽象的输入列名
        .cast(DataType::Float64)
        .rolling_mean(RollingOptionsFixedWindow {
            window_size: period as usize,
            min_periods: period as usize,
            weights: None,
            center: false,
            fn_params: None,
        })
        .alias(alias_name); // 使用抽象的输出别名

    Ok(sma_expr)
}

// --- 蓝图层 ---

/// 🧱 SMA 惰性蓝图函数：接收 LazyFrame，返回包含 "sma" 列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn sma_lazy(lazy_df: LazyFrame, config: &SMAConfig) -> Result<LazyFrame, QuantError> {
    // 1. 获取 SMA 表达式
    let sma_expr = sma_expr(config)?;

    // 2. 构建 LazyFrame 管道：添加 SMA 列，并转换 NULL 为 NaN
    let result_lazy_df = lazy_df
        .with_column(sma_expr)
        .with_column(null_to_nan_expr(&config.alias_name));

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 SMA 急切计算函数
///
/// **计算层 (Eager Wrapper)**
pub fn sma_eager(ohlcv_df: &DataFrame, config: &SMAConfig) -> Result<Series, QuantError> {
    // 边界检查
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "sma".to_string(),
            "Period must be positive for SMA calculation".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    // 1. 将 DataFrame 转换为 LazyFrame
    let lazy_df = ohlcv_df.clone().lazy();

    // 2. 调用蓝图函数构建计算计划
    let lazy_plan = sma_lazy(lazy_df, config)?;

    // 3. 触发计算，只选择最终结果
    let df = lazy_plan
        .select([col(config.alias_name.as_str())])
        .collect()
        .map_err(QuantError::from)?;

    // 4. 提取结果 Series
    Ok(df
        .column(config.alias_name.as_str())?
        .as_materialized_series()
        .clone())
}

pub struct SmaIndicator;

impl Indicator for SmaIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = params
            .get("period")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("period".to_string(), indicator_key.to_string())
            })?
            .value as i64;

        let mut config = SMAConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let sma_series = sma_eager(ohlcv_df, &config)?;
        Ok(vec![sma_series])
    }
}
