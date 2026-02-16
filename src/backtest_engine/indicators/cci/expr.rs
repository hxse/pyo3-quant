use super::config::CCIConfig;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 通用 rolling 计算。
fn rolling_compute<F>(series: &Series, period: usize, compute_fn: F) -> Result<Series, QuantError>
where
    F: Fn(&[f64]) -> f64,
{
    let ca = series.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(ca.name().clone(), ca.len());

    for _ in 0..period - 1 {
        builder.append_null();
    }

    let vals: Vec<f64> = ca.into_iter().map(|value| value.unwrap_or(f64::NAN)).collect();
    let mut window_buffer: Vec<f64> = Vec::with_capacity(period);

    for i in (period - 1)..vals.len() {
        let window = &vals[i + 1 - period..=i];
        window_buffer.clear();

        let mut has_nan = false;
        for &value in window {
            if value.is_nan() {
                has_nan = true;
                break;
            }
            window_buffer.push(value);
        }

        if has_nan || window_buffer.len() != period {
            builder.append_null();
        } else {
            builder.append_value(compute_fn(&window_buffer));
        }
    }

    Ok(builder.finish().into_series())
}

fn calculate_mad(tp: &Series, period: usize) -> Result<Series, QuantError> {
    rolling_compute(tp, period, |window| {
        let mean = window.iter().sum::<f64>() / period as f64;
        window.iter().map(|value| (value - mean).abs()).sum::<f64>() / period as f64
    })
}

/// CCI 表达式。
pub fn cci_expr(config: &CCIConfig) -> Result<Expr, QuantError> {
    let high = col(&config.high_col);
    let low = col(&config.low_col);
    let close = col(&config.close_col);

    let period = config.period;
    let constant = config.constant;

    let tp_expr = (high + low + close) / lit(3.0);

    let sma_expr = tp_expr.clone().rolling_mean(RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: None,
    });

    let mad_expr = tp_expr.clone().map_many(
        move |series| {
            let source_series = series[0].as_materialized_series();
            let mad_series =
                calculate_mad(source_series, period as usize).map_err(|error| {
                    PolarsError::ComputeError(error.to_string().into())
                })?;
            Ok(mad_series.into())
        },
        &[],
        move |_, _| Ok(Field::new("mad".into(), DataType::Float64)),
    );

    let cci_expr = (tp_expr - sma_expr) / (mad_expr * lit(constant));
    Ok(cci_expr.alias(&config.alias_name))
}
