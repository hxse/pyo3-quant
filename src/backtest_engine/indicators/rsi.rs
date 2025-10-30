// src/backtest_engine/indicators/rsi.rs
use super::registry::Indicator;
use crate::backtest_engine::indicators::rma::{rma_expr, RMAConfig};
use crate::data_conversion::input::param::Param;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;
use std::collections::HashMap;

/// RSI 的配置结构体
pub struct RSIConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
}

impl RSIConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "rsi".to_string(), // 临时默认值，将在 impl Indicator 中动态设置
        }
    }
}

// --- 表达式层 ---

/// 🔍 返回计算 RSI 所需的所有核心表达式。
///
/// 包括：change、gain、loss、processed_gain、processed_loss、avg_gain、avg_loss、rsi 表达式。
///
/// **表达式层 (Expr)**
/// 接收配置结构体，所有列名均通过结构体参数传入。
pub fn rsi_expr(
    config: &RSIConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let col_name = config.column_name.as_str();
    let period = config.period;

    // 内部临时列名，用于计算过程，保持在表达式层内部
    let change_temp_name = "rsi_change_temp";
    let gain_temp_name = "rsi_gain_temp";
    let loss_temp_name = "rsi_loss_temp";
    let initial_avg_gain_temp_name = "rsi_initial_avg_gain_temp";
    let initial_avg_loss_temp_name = "rsi_initial_avg_loss_temp";
    let processed_gain_temp_name = "rsi_processed_gain_temp";
    let processed_loss_temp_name = "rsi_processed_loss_temp";
    let avg_gain_temp_name = "rsi_avg_gain_temp";
    let avg_loss_temp_name = "rsi_avg_loss_temp";
    let index_col_name = "index"; // 依赖于 lazy_df.with_row_index("index", None)

    // 1. 计算价格变化
    let change_expr = col(col_name)
        .diff(lit(1), Default::default())
        .alias(change_temp_name);

    // 2. 计算 gain 和 loss
    let gain_expr = when(col(change_temp_name).gt(lit(0.0)))
        .then(col(change_temp_name))
        .otherwise(lit(0.0))
        .alias(gain_temp_name);

    let loss_expr = when(col(change_temp_name).lt(lit(0.0)))
        .then(col(change_temp_name).abs())
        .otherwise(lit(0.0))
        .alias(loss_temp_name);

    // 3. 计算初始的 SMA (用于 Wilder 平滑的第一个值)
    // 注意：TA-Lib 从索引 1 开始切片 period 个值作为初始 SMA
    let initial_avg_gain_expr = col(gain_temp_name)
        .slice(lit(1), lit(period as u32)) // 从索引 1 开始切片，period 个值
        .mean()
        .alias(initial_avg_gain_temp_name);

    let initial_avg_loss_expr = col(loss_temp_name)
        .slice(lit(1), lit(period as u32)) // 从索引 1 开始切片，period 个值
        .mean()
        .alias(initial_avg_loss_temp_name);

    // 4. 构建处理后的 gain/loss 序列 (presma 逻辑)
    //    前 period 个值设为 NaN (索引 0 到 period-1)
    //    第 period 个位置 (索引 period) 放入 SMA 初始值
    //    其余位置为原始 gain/loss 值
    let processed_gain_expr = when(col(index_col_name).cast(DataType::Int64).lt(lit(period)))
        .then(lit(NULL))
        .when(col(index_col_name).cast(DataType::Int64).eq(lit(period)))
        .then(initial_avg_gain_expr)
        .otherwise(col(gain_temp_name))
        .alias(processed_gain_temp_name);

    let processed_loss_expr = when(col(index_col_name).cast(DataType::Int64).lt(lit(period)))
        .then(lit(NULL))
        .when(col(index_col_name).cast(DataType::Int64).eq(lit(period)))
        .then(initial_avg_loss_expr)
        .otherwise(col(loss_temp_name))
        .alias(processed_loss_temp_name);

    // 5. 对处理后的 gain/loss 序列应用 Wilder 平滑 (ewm_mean)
    // Wilder 平滑使用 alpha = 1.0 / period
    let avg_gain_expr = rma_expr(&RMAConfig {
        column_name: processed_gain_temp_name.to_string(),
        alias_name: avg_gain_temp_name.to_string(),
        period,
    })
    .map_err(QuantError::from)?;

    let avg_loss_expr = rma_expr(&RMAConfig {
        column_name: processed_loss_temp_name.to_string(),
        alias_name: avg_loss_temp_name.to_string(),
        period,
    })
    .map_err(QuantError::from)?;

    // 6. 计算 RSI
    // RSI = 100.0 * (avg_gain / (avg_gain + avg_loss))
    let rsi_expr = (lit(100.0) * col(avg_gain_temp_name)
        / (col(avg_gain_temp_name) + col(avg_loss_temp_name)))
    .alias(config.alias_name.as_str());

    Ok((
        change_expr,
        gain_expr,
        loss_expr,
        processed_gain_expr,
        processed_loss_expr,
        avg_gain_expr,
        avg_loss_expr,
        rsi_expr,
    ))
}

// --- 蓝图层 ---

/// 🧱 相对强弱指数 (RSI) 惰性蓝图函数：接收 LazyFrame，返回包含 "rsi" 列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn rsi_lazy(lazy_df: LazyFrame, config: &RSIConfig) -> Result<LazyFrame, QuantError> {
    // 1. 获取所有核心表达式
    let (
        change_expr,
        gain_expr,
        loss_expr,
        processed_gain_expr,
        processed_loss_expr,
        avg_gain_expr,
        avg_loss_expr,
        rsi_expr,
    ) = rsi_expr(config)?;

    // 2. 链接到 LazyFrame 上
    let result_lazy_df = lazy_df
        // 必须添加行索引，因为 processed_gain/loss_expr 依赖于它
        .with_row_index("index", None)
        // 计算并注入 "change_temp"
        .with_column(change_expr)
        // 计算并注入 "gain_temp"
        .with_column(gain_expr)
        // 计算并注入 "loss_temp"
        .with_column(loss_expr)
        // 计算并注入 "processed_gain_temp" (它会自动包含 SMA 初始值计算)
        .with_column(processed_gain_expr)
        // 计算并注入 "processed_loss_temp" (它会自动包含 SMA 初始值计算)
        .with_column(processed_loss_expr)
        // 计算并注入 "avg_gain_temp"
        .with_column(avg_gain_expr)
        // 计算并注入 "avg_loss_temp"
        .with_column(avg_loss_expr)
        // 计算最终的 "rsi"
        .with_column(rsi_expr)
        // 删除所有临时列，只保留原始列和最终的 RSI 列
        .select(&[col(&config.column_name), col(&config.alias_name)]);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 相对强弱指数 (RSI) 急切计算函数
///
/// **计算层 (Eager Wrapper)**
pub fn rsi_eager(ohlcv_df: &DataFrame, config: &RSIConfig) -> Result<Series, QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "rsi".to_string(),
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
    if series_len <= n_periods {
        return Err(IndicatorError::DataTooShort("rsi".to_string(), config.period).into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = rsi_lazy(lazy_df, config)?;
    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}

pub struct RsiIndicator;

impl Indicator for RsiIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = param_map
            .get("period")
            .map(|p| p.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'period' parameter".to_string(),
                )
            })?;

        let mut config = RSIConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let result_series = rsi_eager(ohlcv_df, &config)?;

        Ok(vec![result_series])
    }
}
