use crate::error::{IndicatorError, QuantError};
use polars::prelude::*;
use std::sync::Arc; // 新增导入

mod psar_core;
use psar_core::{psar_first_iteration, psar_update};

// --- 配置结构体 ---
pub struct PSARConfig {
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub af0: f64,
    pub af_step: f64,
    pub max_af: f64,
    // 输出列名
    pub psar_long_alias: String,
    pub psar_short_alias: String,
    pub psar_af_alias: String,
    pub psar_reversal_alias: String,
}

// --- 表达式层：使用 map_many 封装逐行状态更新 ---
pub fn psar_expr(config: &PSARConfig) -> Result<Expr, QuantError> {
    // 修改返回类型
    let high_col = col(&config.high_col);
    let low_col = col(&config.low_col);
    let close_col = col(&config.close_col);
    let af0 = config.af0;
    let af_step = config.af_step;
    let max_af = config.max_af;
    let psar_long_alias = config.psar_long_alias.clone();
    let psar_short_alias = config.psar_short_alias.clone();
    let psar_af_alias = config.psar_af_alias.clone();
    let psar_reversal_alias = config.psar_reversal_alias.clone();
    let output_dtype = DataType::Struct(vec![
        Field::new(psar_long_alias.clone().into(), DataType::Float64),
        Field::new(psar_short_alias.clone().into(), DataType::Float64),
        Field::new(psar_af_alias.clone().into(), DataType::Float64),
        Field::new(psar_reversal_alias.clone().into(), DataType::Float64),
    ]);

    let psar_struct_expr = high_col
        .map_many(
            move |s| {
                let high_series = &s[0];
                let low_series = &s[1];
                let close_series = &s[2];
                let high_vec: Vec<f64> = high_series
                    .f64()? //，因为闭包返回 PolarsResult
                    .into_iter()
                    .map(|x| x.unwrap_or(f64::NAN))
                    .collect();
                let low_vec: Vec<f64> = low_series
                    .f64()?
                    .into_iter()
                    .map(|x| x.unwrap_or(f64::NAN))
                    .collect();
                let close_vec: Vec<f64> = close_series
                    .f64()?
                    .into_iter()
                    .map(|x| x.unwrap_or(f64::NAN))
                    .collect();

                let n = high_vec.len();
                let mut psar_long = vec![f64::NAN; n];
                let mut psar_short = vec![f64::NAN; n];
                let mut psar_af = vec![f64::NAN; n];
                let mut psar_reversal = vec![0.0; n];

                if n < 2 {
                    // 对于数据不足的情况，返回 PolarsError::ComputeError
                    return Err(PolarsError::ComputeError(
                        format!(
                            "Input data is too short to calculate psar. Minimum 2 data points required. Details: {}",
                            IndicatorError::DataTooShort("psar".to_string(), 2)
                        )
                        .into(),
                    ));
                }

                // 逐行状态更新（封装在 expr 閉包內）
                psar_af[0] = af0;
                psar_reversal[0] = 0.0;

                let (state, long_val, short_val, rev_val) = psar_first_iteration(
                    high_vec[0],
                    high_vec[1],
                    low_vec[0],
                    low_vec[1],
                    close_vec[0],
                    af0,
                    af_step,
                    max_af,
                );
                psar_long[1] = long_val;
                psar_short[1] = short_val;
                psar_af[1] = state.current_af;
                psar_reversal[1] = rev_val;

                if state.current_psar.is_nan() {
                    // 这种情况可能表示初始计算失败，或者数据不足以进行有效计算
                    // 暂时不抛出错误，而是返回全 NaN 的 Series，这与 Polars 的行为更一致
                    // 如果需要更严格的错误处理，可以考虑抛出 IndicatorError::ComputeError
                    let psar_long_series = Series::new(psar_long_alias.as_str().into(), psar_long);
                    let psar_short_series =
                        Series::new(psar_short_alias.as_str().into(), psar_short);
                    let psar_af_series = Series::new(psar_af_alias.as_str().into(), psar_af);
                    let psar_reversal_series =
                        Series::new(psar_reversal_alias.as_str().into(), psar_reversal);
                    let df_temp = DataFrame::new(vec![
                        psar_long_series.into(),
                        psar_short_series.into(),
                        psar_af_series.into(),
                        psar_reversal_series.into(),
                    ])?;
                    return Ok(df_temp
                        .into_struct("psar_struct".into())
                        .into_series()
                        .into());
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
                    );
                    psar_long[i] = long_val;
                    psar_short[i] = short_val;
                    psar_af[i] = new_state.current_af;
                    psar_reversal[i] = rev_val;
                    current_state = new_state;
                }

                let psar_long_series = Series::new(psar_long_alias.as_str().into(), psar_long);
                let psar_short_series = Series::new(psar_short_alias.as_str().into(), psar_short);
                let psar_af_series = Series::new(psar_af_alias.as_str().into(), psar_af);
                let psar_reversal_series =
                    Series::new(psar_reversal_alias.as_str().into(), psar_reversal);
                let df_temp = DataFrame::new(vec![
                    psar_long_series.into(),
                    psar_short_series.into(),
                    psar_af_series.into(),
                    psar_reversal_series.into(),
                ])?;
                Ok(df_temp
                    .into_struct("psar_struct".into())
                    .into_series()
                    .into())
            },
            &[low_col, close_col],
            move |_, _| Ok(Field::new("psar_struct".into(), output_dtype.clone())),
        )
        .alias("psar_struct");

    Ok(psar_struct_expr)
}

// --- 蓝图层 ---
pub fn psar_lazy(
    lazy_df: LazyFrame,
    af0: f64,
    af_step: f64,
    max_af: f64,
) -> Result<LazyFrame, QuantError> {
    // 修改返回类型
    let config = PSARConfig {
        high_col: "high".to_string(),
        low_col: "low".to_string(),
        close_col: "close".to_string(),
        af0,
        af_step,
        max_af,
        psar_long_alias: "psar_long".to_string(),
        psar_short_alias: "psar_short".to_string(),
        psar_af_alias: "psar_af".to_string(),
        psar_reversal_alias: "psar_reversal".to_string(),
    };
    let psar_struct_expr = psar_expr(&config)?;
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
        .drop(Selector::ByName {
            names: Arc::new([struct_col_name.into()]),
            strict: true,
        });
    Ok(final_df)
}

// --- 计算层 (Eager) ---
pub fn psar_eager(
    ohlcv_df: &DataFrame,
    af0: f64,
    af_step: f64,
    max_af: f64,
) -> Result<(Series, Series, Series, Series), QuantError> {
    // 修改返回类型
    if ohlcv_df.height() < 2 {
        // PSAR 至少需要2个数据点
        return Err(IndicatorError::DataTooShort("psar".to_string(), 2).into());
    }

    let lazy_df = psar_lazy(ohlcv_df.clone().lazy(), af0, af_step, max_af)?;
    let result_df = lazy_df.collect().map_err(QuantError::from)?; // 错误转换
    Ok((
        result_df
            .column("psar_long")
            .map_err(QuantError::from)? // 错误转换
            .as_materialized_series()
            .clone(),
        result_df
            .column("psar_short")
            .map_err(QuantError::from)? // 错误转换
            .as_materialized_series()
            .clone(),
        result_df
            .column("psar_af")
            .map_err(QuantError::from)? // 错误转换
            .as_materialized_series()
            .clone(),
        result_df
            .column("psar_reversal")
            .map_err(QuantError::from)? // 错误转换
            .as_materialized_series()
            .clone(),
    ))
}
