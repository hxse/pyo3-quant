use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

// 引入抽象后的 sma_expr 函数
use super::{
    registry::Indicator,
    sma::{sma_expr, SMAConfig},
    utils::null_to_nan_expr,
};
use crate::data_conversion::types::param::Param;
use crate::error::{IndicatorError, QuantError};
use std::collections::HashMap;

/// 布林带的配置结构体，将所有输入参数和输出列名抽象化。
pub struct BBandsConfig {
    pub period: i64,
    pub std_multiplier: f64,
    pub close_col: String,
    pub middle_band_alias: String,
    pub std_dev_alias: String,
    pub upper_band_alias: String,
    pub lower_band_alias: String,
    pub bandwidth_alias: String,
    pub percent_alias: String,
}

impl BBandsConfig {
    pub fn new(period: i64, std_multiplier: f64) -> Self {
        Self {
            period,
            std_multiplier,
            close_col: "close".to_string(),
            middle_band_alias: "middle_band".to_string(),
            std_dev_alias: "std_dev".to_string(),
            upper_band_alias: "upper_band".to_string(),
            lower_band_alias: "lower_band".to_string(),
            bandwidth_alias: "bandwidth".to_string(),
            percent_alias: "percent".to_string(),
        }
    }
}

// --- 表达式层 ---

/// 返回布林带计算所需的表达式
///
/// **表达式层 (Exprs)**
/// 接收配置结构体，所有列名均通过结构体参数传入。
pub fn bbands_expr(
    config: &BBandsConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let col_name = config.close_col.as_str();
    let period = config.period;
    let std_multiplier = config.std_multiplier;

    let middle_alias = config.middle_band_alias.as_str();
    let std_dev_alias = config.std_dev_alias.as_str();
    let upper_alias = config.upper_band_alias.as_str();
    let lower_alias = config.lower_band_alias.as_str();
    let bandwidth_alias = config.bandwidth_alias.as_str();
    let percent_alias = config.percent_alias.as_str();

    // 确保依赖顺序的 RollingOptions
    let rolling_options = RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: Some(RollingFnParams::Var(RollingVarParams { ddof: 0 })),
    };

    // 1. 中轨（Middle Band）：【复用】抽象化的 sma_expr
    // 1. 创建 SMAConfig 实例
    let sma_config = SMAConfig {
        column_name: col_name.to_string(),
        alias_name: middle_alias.to_string(), // 中轨的别名应与配置中的 middle_band_alias 保持一致
        period,
    };

    // 2. 将配置的引用传递给 sma_expr
    let middle_band_expr = sma_expr(&sma_config)?;

    // 2. 标准差（Standard Deviation）：使用配置中的列名作为别名
    let std_dev_expr = col(col_name)
        .cast(DataType::Float64)
        .rolling_std(rolling_options)
        .alias(std_dev_alias);

    // 3. 上轨（Upper Band）：依赖 middle_band_alias 和 std_dev_alias
    let upper_band_expr =
        (col(middle_alias) + lit(std_multiplier) * col(std_dev_alias)).alias(upper_alias);

    // 4. 下轨（Lower Band）：依赖 middle_band_alias 和 std_dev_alias
    let lower_band_expr =
        (col(middle_alias) - lit(std_multiplier) * col(std_dev_alias)).alias(lower_alias);

    // 5. 带宽（Bandwidth）：依赖 upper_alias, lower_alias, middle_alias
    let bandwidth_expr = (lit(100.0) * (col(upper_alias) - col(lower_alias)) / col(middle_alias))
        .alias(bandwidth_alias);

    // 6. %B（Percent B）：依赖 输入列, upper_alias, lower_alias
    let percent_b_expr = ((col(col_name).cast(DataType::Float64) - col(lower_alias))
        / (col(upper_alias) - col(lower_alias)))
    .alias(percent_alias);

    Ok((
        middle_band_expr,
        std_dev_expr,
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ))
}

// --- 蓝图层 ---

/// 🧱 布林带惰性蓝图函数：接收 LazyFrame，返回包含所有布林带指标列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn bbands_lazy(lazy_df: LazyFrame, config: &BBandsConfig) -> Result<LazyFrame, QuantError> {
    let (
        middle_band_expr,
        std_dev_expr, // 包含 std_dev，尽管它最终不会被 select
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ) = bbands_expr(config)?; // 传入配置结构体

    // 核心：保持多步 with_columns 调用以确保表达式的依赖顺序
    let result_lazy_df = lazy_df
        // 步骤1：首先计算 middle_band (复用 SMA) 和 std_dev
        .with_columns([middle_band_expr, std_dev_expr])
        // 步骤2：使用上一步生成的列来计算 upper_band 和 lower_band
        .with_columns([upper_band_expr, lower_band_expr])
        // 步骤3：最后计算依赖于 band 的指标
        .with_columns([bandwidth_expr, percent_b_expr])
        // 步骤4：将所有布林带指标的 NULL 转换为 NaN
        .with_columns([
            null_to_nan_expr(&config.lower_band_alias),
            null_to_nan_expr(&config.middle_band_alias),
            null_to_nan_expr(&config.upper_band_alias),
            null_to_nan_expr(&config.bandwidth_alias),
            null_to_nan_expr(&config.percent_alias),
        ]);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 计算布林带（Bollinger Bands）及其相关指标。
///
/// **计算层 (Eager Wrapper)**
pub fn bbands_eager(
    ohlcv_df: &DataFrame,
    config: &BBandsConfig,
) -> Result<(Series, Series, Series, Series, Series), QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "bbands".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    let n_periods = config.period as usize;

    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort(
            "bbands".to_string(),
            config.period,
            series_len as i64,
        )
        .into());
    }

    // 1. 将 DataFrame 转换为 LazyFrame
    let lazy_df = ohlcv_df.clone().lazy();

    // 2. 调用蓝图函数构建计算计划
    let lazy_plan = bbands_lazy(lazy_df, config)?;

    // 3. 触发计算，只选择需要的指标列。
    // 注意：这里使用与 bbands_lazy 中默认配置相匹配的列名
    let combined_df = lazy_plan
        .select([
            col(config.lower_band_alias.as_str()),
            col(config.middle_band_alias.as_str()),
            col(config.upper_band_alias.as_str()),
            col(config.bandwidth_alias.as_str()),
            col(config.percent_alias.as_str()),
            // 不选择 std_dev
        ])
        .collect()
        .map_err(QuantError::from)?;

    // 4. 提取结果 Series
    Ok((
        combined_df
            .column(config.lower_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.middle_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.upper_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.bandwidth_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.percent_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
    ))
}

pub struct BbandsIndicator;

impl Indicator for BbandsIndicator {
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
        let std_multiplier = params
            .get("std")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("std".to_string(), indicator_key.to_string())
            })?
            .value;

        let mut config = BBandsConfig::new(period, std_multiplier);
        config.middle_band_alias = format!("{}_middle", indicator_key);
        config.std_dev_alias = format!("{}_std_dev", indicator_key);
        config.upper_band_alias = format!("{}_upper", indicator_key);
        config.lower_band_alias = format!("{}_lower", indicator_key);
        config.bandwidth_alias = format!("{}_bandwidth", indicator_key);
        config.percent_alias = format!("{}_percent", indicator_key);

        let (lower, middle, upper, bandwidth, percent) = bbands_eager(ohlcv_df, &config)?;

        Ok(vec![lower, middle, upper, bandwidth, percent])
    }
}
