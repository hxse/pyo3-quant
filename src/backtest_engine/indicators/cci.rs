use super::registry::Indicator;
use super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

/// CCI 配置结构体
pub struct CCIConfig {
    pub period: i64,
    pub constant: f64,
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub alias_name: String,
}

impl CCIConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            constant: 0.015, // Default constant
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            alias_name: "cci".to_string(),
        }
    }
}

// --- 辅助计算函数 (保持纯 Rust 逻辑) ---

/// 通用 Rolling 计算函数
/// 处理窗口遍历、Null 检查和 Builder 构建
fn rolling_compute<F>(series: &Series, period: usize, f: F) -> Result<Series, QuantError>
where
    F: Fn(&[f64]) -> f64,
{
    let ca = series.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(ca.name().clone(), ca.len());

    // Pre-fill initial NaNs
    for _ in 0..period - 1 {
        builder.append_null();
    }

    let vals: Vec<f64> = ca.into_iter().map(|v| v.unwrap_or(f64::NAN)).collect();
    let mut window_buffer: Vec<f64> = Vec::with_capacity(period);

    for i in (period - 1)..vals.len() {
        let window = &vals[i + 1 - period..=i];

        window_buffer.clear();
        let mut has_nan = false;

        for &v in window {
            if v.is_nan() {
                has_nan = true;
                break;
            }
            window_buffer.push(v);
        }

        if has_nan || window_buffer.len() != period {
            builder.append_null();
        } else {
            let result = f(&window_buffer);
            builder.append_value(result);
        }
    }

    Ok(builder.finish().into_series())
}

fn calculate_mad(tp: &Series, period: usize) -> Result<Series, QuantError> {
    rolling_compute(tp, period, |w| {
        let mean = w.iter().sum::<f64>() / period as f64;
        w.iter().map(|x| (x - mean).abs()).sum::<f64>() / period as f64
    })
}

// --- 表达式层 ---

pub fn cci_expr(config: &CCIConfig) -> Result<Expr, QuantError> {
    // 准备列名
    let high = col(&config.high_col);
    let low = col(&config.low_col);
    let close = col(&config.close_col);

    let period = config.period;
    let constant = config.constant;

    // 1. TP Expr (Pure Expr)
    let tp_expr = (high + low + close) / lit(3.0);

    // 2. SMA Expr (Native Polars Expr)
    let sma_expr = tp_expr.clone().rolling_mean(RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: None,
    });

    // 3. MAD Expr (UDF via map_many to avoid GetOutput import issues)
    // We use map_many with no extra columns to act as map_batches
    let mad_expr = tp_expr.clone().map_many(
        move |s| {
            // s[0] is the series
            let series = s[0].as_materialized_series();
            let mad_series = calculate_mad(series, period as usize)
                .map_err(|e| PolarsError::ComputeError(e.to_string().into()))?;
            Ok(mad_series.into())
        },
        &[], // No extra columns
        move |_, _| Ok(Field::new("mad".into(), DataType::Float64)),
    );

    // 4. CCI Expr
    // (tp - sma) / (0.015 * mad)
    let cci_expr = (tp_expr - sma_expr) / (mad_expr * lit(constant));

    Ok(cci_expr.alias(&config.alias_name))
}

// --- 蓝图层 ---

pub fn cci_lazy(lazy_df: LazyFrame, config: &CCIConfig) -> Result<LazyFrame, QuantError> {
    let cci_expr = cci_expr(config)?;

    let result_lazy_df = lazy_df
        .with_column(cci_expr)
        .with_column(null_to_nan_expr(&config.alias_name)); // Ensure NaNs for display consistency

    Ok(result_lazy_df)
}

// --- 计算层 (Eager Wrapper) ---

pub fn cci_eager(ohlcv_df: &DataFrame, config: &CCIConfig) -> Result<Series, QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "cci".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    // Check length (though lazy execution handles this gracefully, explicit check is good)
    if ohlcv_df.height() < config.period as usize {
        return Err(IndicatorError::DataTooShort(
            "cci".to_string(),
            config.period,
            ohlcv_df.height() as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = cci_lazy(lazy_df, config)?;

    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}

pub struct CciIndicator;

impl Indicator for CciIndicator {
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

        let mut config = CCIConfig::new(period);
        config.alias_name = indicator_key.to_string();

        if let Some(c) = params.get("constant") {
            config.constant = c.value;
        }

        let series = cci_eager(ohlcv_df, &config)?;
        Ok(vec![series])
    }
}
