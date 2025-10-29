use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

pub struct RMAConfig {
    pub column_name: String,
    pub alias_name: String,
    pub period: i64,
}

// 表达式层: 直接使用ewm,无前导NaN
pub fn rma_expr(config: &RMAConfig) -> Result<Expr, QuantError> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    // 直接对整个序列使用ewm_mean,无需任何预处理
    let rma_expr = col(col_name)
        .cast(DataType::Float64)
        .ewm_mean(EWMOptions {
            alpha: 1.0 / period as f64,
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: true,
        })
        .alias(alias_name);

    Ok(rma_expr)
}

// 蓝图层: 简化,不需要row_index
pub fn rma_lazy(lazy_df: LazyFrame, period: i64) -> Result<LazyFrame, QuantError> {
    let config = RMAConfig {
        column_name: "close".to_string(),
        alias_name: "rma".to_string(),
        period,
    };

    let rma_expr = rma_expr(&config)?;
    let result_lazy_df = lazy_df.with_column(rma_expr);

    Ok(result_lazy_df)
}

// 计算层: 保持不变
pub fn rma_eager(ohlcv_df: &DataFrame, period: i64) -> Result<Series, QuantError> {
    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "rma".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }
    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty("rma".into(), &DataType::Float64));
    }
    let n_periods = period as usize;
    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort("rma".to_string(), period).into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = rma_lazy(lazy_df, period)?;
    let result_df = lazy_plan.select([col("rma")]).collect()?;

    Ok(result_df.column("rma")?.as_materialized_series().clone())
}
