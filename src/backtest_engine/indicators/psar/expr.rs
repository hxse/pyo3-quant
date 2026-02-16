use crate::backtest_engine::indicators::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use polars::prelude::*;
use std::sync::Arc;

use super::config::PSARConfig;
use super::psar_core::{psar_first_iteration, psar_update, ForceDirection};

/// 表达式层：使用 map_many 封装逐行状态更新。
pub fn psar_expr(config: &PSARConfig) -> Result<Expr, QuantError> {
    let high_col = col(&config.high_col);
    let low_col = col(&config.low_col);
    let close_col = col(&config.close_col);
    let af0 = config.af0;
    let af_step = config.af_step;
    let max_af = config.max_af;
    let psar_long_small = PlSmallStr::from_str(&config.psar_long_alias);
    let psar_short_small = PlSmallStr::from_str(&config.psar_short_alias);
    let psar_af_small = PlSmallStr::from_str(&config.psar_af_alias);
    let psar_reversal_small = PlSmallStr::from_str(&config.psar_reversal_alias);

    let output_dtype = DataType::Struct(vec![
        Field::new(psar_long_small.clone(), DataType::Float64),
        Field::new(psar_short_small.clone(), DataType::Float64),
        Field::new(psar_af_small.clone(), DataType::Float64),
        Field::new(psar_reversal_small.clone(), DataType::Float64),
    ]);

    let psar_struct_expr = high_col
        .map_many(
            move |series| {
                let high_series = &series[0];
                let low_series = &series[1];
                let close_series = &series[2];
                let high_vec: Vec<f64> = high_series
                    .f64()?
                    .into_iter()
                    .map(|value| value.unwrap_or(f64::NAN))
                    .collect();
                let low_vec: Vec<f64> = low_series
                    .f64()?
                    .into_iter()
                    .map(|value| value.unwrap_or(f64::NAN))
                    .collect();
                let close_vec: Vec<f64> = close_series
                    .f64()?
                    .into_iter()
                    .map(|value| value.unwrap_or(f64::NAN))
                    .collect();

                let n = high_vec.len();
                let mut psar_long = vec![f64::NAN; n];
                let mut psar_short = vec![f64::NAN; n];
                let mut psar_af = vec![f64::NAN; n];
                let mut psar_reversal = vec![0.0; n];

                if n < 2 {
                    return Err(PolarsError::ComputeError(
                        format!(
                            "Input data is too short to calculate psar. Minimum 2 data points required. Details: {}",
                            IndicatorError::DataTooShort("psar".to_string(), 2, n as i64)
                        )
                        .into(),
                    ));
                }

                psar_af[0] = af0;
                psar_reversal[0] = 0.0;

                let (state, long_val, short_val, rev_val) = psar_first_iteration(
                    high_vec[0],
                    high_vec[1],
                    low_vec[0],
                    low_vec[1],
                    close_vec[0],
                    ForceDirection::Auto,
                    af0,
                    af_step,
                    max_af,
                );
                psar_long[1] = long_val;
                psar_short[1] = short_val;
                psar_af[1] = state.current_af;
                psar_reversal[1] = rev_val;

                if state.current_psar.is_nan() {
                    let psar_long_series = Series::new(psar_long_small.clone(), psar_long);
                    let psar_short_series = Series::new(psar_short_small.clone(), psar_short);
                    let psar_af_series = Series::new(psar_af_small.clone(), psar_af);
                    let psar_reversal_series =
                        Series::new(psar_reversal_small.clone(), psar_reversal);
                    let df_temp = DataFrame::new(vec![
                        psar_long_series.into(),
                        psar_short_series.into(),
                        psar_af_series.into(),
                        psar_reversal_series.into(),
                    ])?;
                    return Ok(df_temp.into_struct("psar_struct".into()).into_series().into());
                }

                let mut current_state = state;
                for i in 2..n {
                    let (new_state, long_val, short_val, rev_val) = psar_update(
                        &current_state,
                        high_vec[i],
                        low_vec[i],
                        high_vec[i - 1],
                        low_vec[i - 1],
                        af_step,
                        max_af,
                        None,
                    );
                    psar_long[i] = long_val;
                    psar_short[i] = short_val;
                    psar_af[i] = new_state.current_af;
                    psar_reversal[i] = rev_val;
                    current_state = new_state;
                }

                let psar_long_series = Series::new(psar_long_small.clone(), psar_long);
                let psar_short_series = Series::new(psar_short_small.clone(), psar_short);
                let psar_af_series = Series::new(psar_af_small.clone(), psar_af);
                let psar_reversal_series = Series::new(psar_reversal_small.clone(), psar_reversal);
                let df_temp = DataFrame::new(vec![
                    psar_long_series.into(),
                    psar_short_series.into(),
                    psar_af_series.into(),
                    psar_reversal_series.into(),
                ])?;
                Ok(df_temp.into_struct("psar_struct".into()).into_series().into())
            },
            &[low_col, close_col],
            move |_, _| Ok(Field::new("psar_struct".into(), output_dtype.clone())),
        )
        .alias("psar_struct");

    Ok(psar_struct_expr)
}

/// 蓝图层：在 LazyFrame 上展开并输出最终 PSAR 列。
pub fn psar_lazy(lazy_df: LazyFrame, config: &PSARConfig) -> Result<LazyFrame, QuantError> {
    let psar_struct_expr = psar_expr(config)?;
    let struct_col_name = "psar_struct";
    let final_df = lazy_df
        .with_column(psar_struct_expr)
        .with_columns(vec![
            col(struct_col_name)
                .struct_()
                .field_by_name(config.psar_long_alias.as_str())
                .alias(&config.psar_long_alias),
            col(struct_col_name)
                .struct_()
                .field_by_name(config.psar_short_alias.as_str())
                .alias(&config.psar_short_alias),
            col(struct_col_name)
                .struct_()
                .field_by_name(config.psar_af_alias.as_str())
                .alias(&config.psar_af_alias),
            col(struct_col_name)
                .struct_()
                .field_by_name(config.psar_reversal_alias.as_str())
                .alias(&config.psar_reversal_alias),
        ])
        .with_columns(vec![
            null_to_nan_expr(&config.psar_long_alias),
            null_to_nan_expr(&config.psar_short_alias),
            null_to_nan_expr(&config.psar_af_alias),
            null_to_nan_expr(&config.psar_reversal_alias),
        ])
        .drop(Selector::ByName {
            names: Arc::new([struct_col_name.into()]),
            strict: true,
        });
    Ok(final_df)
}
