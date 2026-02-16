use super::config::ADXConfig;
use crate::backtest_engine::indicators::tr::{tr_expr, TRConfig};
use crate::backtest_engine::indicators::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::{col, lit, when, Expr};
use polars::prelude::*;

/// 生成修正后的输入序列和最终聚合表达式。
fn get_fixed_aggregate(
    dm1_col_name: &str,
    period: i64,
    index_col_name: &str,
) -> Result<(Expr, Expr), QuantError> {
    let period_usize = period as usize;
    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "adx".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    let period_lit_f64 = lit(period as f64);
    let alpha = 1.0 / period as f64;

    let rolling_opts = RollingOptionsFixedWindow {
        window_size: period_usize,
        min_periods: period_usize,
        weights: None,
        center: false,
        fn_params: None,
    };
    let dm1_rolling_sum = col(dm1_col_name).rolling_sum(rolling_opts);
    let dm1_initial_avg = dm1_rolling_sum / period_lit_f64.clone();

    let initial_idx = period - 1;
    let index_col = col(index_col_name).cast(DataType::Int64);
    let initial_idx_lit_i64 = lit(initial_idx);
    let initial_idx_mask = index_col.clone().eq(initial_idx_lit_i64.clone());

    let processed_col_name = format!("{}_processed_temp", dm1_col_name);
    let dm1_processed_expr = when(index_col.clone().lt(initial_idx_lit_i64.clone()))
        .then(lit(NULL).cast(DataType::Float64))
        .when(initial_idx_mask)
        .then(dm1_initial_avg)
        .otherwise(col(dm1_col_name).cast(DataType::Float64))
        .alias(processed_col_name.as_str());

    let ewm_options = EWMOptions {
        alpha,
        adjust: false,
        bias: false,
        min_periods: 1,
        ignore_nulls: true,
    };
    let dm1_mean_fixed = col(processed_col_name.as_str()).ewm_mean(ewm_options);

    let dm_smooth_agg =
        (dm1_mean_fixed * period_lit_f64).alias(format!("{}_smooth_temp", dm1_col_name).as_str());

    Ok((dm1_processed_expr, dm_smooth_agg))
}

/// 计算原始的 +DM1, -DM1, TR 表达式。
fn get_raw_dm_tr_exprs(
    config: &ADXConfig,
    index_col_name: &str,
) -> Result<(Expr, Expr, Expr), QuantError> {
    let high = col(&config.high_col);
    let low = col(&config.low_col);
    let index = col(index_col_name);

    let diff_p = (high.clone() - high.shift(lit(1))).fill_null(lit(0.0));
    let diff_m = (low.clone().shift(lit(1)) - low.clone()).fill_null(lit(0.0));

    let lit_0_f64 = lit(0.0);
    let lit_1_i64 = lit(1i64);

    let plus_dm1 = when(index.clone().lt(lit_1_i64.clone()))
        .then(lit_0_f64.clone())
        .otherwise(
            when((diff_m.clone().gt(lit_0_f64.clone())).and(diff_p.clone().lt(diff_m.clone())))
                .then(lit_0_f64.clone())
                .when((diff_p.clone().gt(lit_0_f64.clone())).and(diff_p.clone().gt(diff_m.clone())))
                .then(diff_p.clone())
                .otherwise(lit_0_f64.clone()),
        )
        .alias("plus_dm1_temp");

    let minus_dm1 = when(index.clone().lt(lit_1_i64))
        .then(lit_0_f64.clone())
        .otherwise(
            when((diff_m.clone().gt(lit_0_f64.clone())).and(diff_p.clone().lt(diff_m.clone())))
                .then(diff_m.clone())
                .when((diff_p.clone().gt(lit_0_f64.clone())).and(diff_p.clone().gt(diff_m.clone())))
                .then(lit_0_f64.clone())
                .otherwise(lit_0_f64.clone()),
        )
        .alias("minus_dm1_temp");

    let tr_config = TRConfig {
        high_col: config.high_col.clone(),
        low_col: config.low_col.clone(),
        close_col: config.close_col.clone(),
        alias_name: "tr_temp".to_string(),
    };
    let tr_temp = tr_expr(&tr_config)?.alias("tr_temp");
    Ok((plus_dm1, minus_dm1, tr_temp))
}

/// 构建 ADX 指标表达式组。
pub(crate) fn adx_expr(config: &ADXConfig) -> Result<Vec<Vec<Expr>>, QuantError> {
    let mut expr_groups: Vec<Vec<Expr>> = Vec::new();
    let index_col_name = "index";
    let period = config.period;
    let adxr_length = config.adxr_length;

    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "adx".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }
    if adxr_length <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "adx".to_string(),
            "ADXR Length must be positive".to_string(),
        )
        .into());
    }

    let lit_100 = lit(100.0);
    let lit_0_5 = lit(0.5);
    let lit_0 = lit(0.0);
    let lit_null_f64 = lit(NULL).cast(DataType::Float64);

    let null_final_fill = lit_null_f64.clone().alias("null_final_fill");
    let period_minus_1_lit_dm = lit(period - 1);
    let adx_lookback_lit = lit(2 * period - 1);
    let adxr_lookback_lit = lit(2 * period - 1 + adxr_length);
    let adxr_length_lit = lit(adxr_length);

    let (plus_dm1_raw, minus_dm1_raw, tr_raw) = get_raw_dm_tr_exprs(config, index_col_name)?;
    expr_groups.push(vec![plus_dm1_raw, minus_dm1_raw, tr_raw]);

    let (plus_dm1_processed, plus_dm_smooth_agg) =
        get_fixed_aggregate("plus_dm1_temp", period, index_col_name)?;
    let (minus_dm1_processed, minus_dm_smooth_agg) =
        get_fixed_aggregate("minus_dm1_temp", period, index_col_name)?;
    let (tr1_processed, tr_smooth_agg) = get_fixed_aggregate("tr_temp", period, index_col_name)?;
    expr_groups.push(vec![plus_dm1_processed, minus_dm1_processed, tr1_processed]);

    expr_groups.push(vec![
        plus_dm_smooth_agg.alias("plus_dm_smooth_temp"),
        minus_dm_smooth_agg.alias("minus_dm_smooth_temp"),
        tr_smooth_agg.alias("tr_smooth_temp"),
    ]);

    let plus_di = (lit_100.clone()
        * when(col("tr_smooth_temp").gt(lit_0.clone()))
            .then(col("plus_dm_smooth_temp") / col("tr_smooth_temp"))
            .otherwise(lit_0.clone()))
    .alias("temp_plus_di");

    let minus_di = (lit_100.clone()
        * when(col("tr_smooth_temp").gt(lit_0.clone()))
            .then(col("minus_dm_smooth_temp") / col("tr_smooth_temp"))
            .otherwise(lit_0.clone()))
    .alias("temp_minus_di");
    expr_groups.push(vec![plus_di, minus_di]);

    let di_sum_expr = col("temp_plus_di") + col("temp_minus_di");
    let di_diff_abs = (col("temp_plus_di") - col("temp_minus_di")).abs();
    let dx_input_expr = (lit_100.clone()
        * when(di_sum_expr.clone().gt(lit_0.clone()))
            .then(di_diff_abs / di_sum_expr)
            .otherwise(lit_0.clone()))
    .alias("dx_temp");
    expr_groups.push(vec![dx_input_expr]);

    let adx_input_col_name = "dx_temp";
    let adx_processed_col_name = "dx_processed_for_adx_temp";
    let alpha = 1.0 / period as f64;
    let period_lit_f64 = lit(period as f64);

    let adx_initial_idx = 2 * period - 1;
    let rolling_opts_adx_sma = RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: None,
    };
    let dx_rolling_sum = col(adx_input_col_name).rolling_sum(rolling_opts_adx_sma);
    let dx_initial_avg = dx_rolling_sum / period_lit_f64;
    let index_col = col(index_col_name).cast(DataType::Int64);

    let initial_adx_idx_lit = lit(adx_initial_idx);
    let initial_adx_mask = index_col.clone().eq(initial_adx_idx_lit.clone());
    let dx_processed_expr = when(index_col.clone().lt(initial_adx_idx_lit.clone()))
        .then(lit_null_f64.clone())
        .when(initial_adx_mask)
        .then(dx_initial_avg)
        .otherwise(col(adx_input_col_name).cast(DataType::Float64))
        .alias(adx_processed_col_name);
    expr_groups.push(vec![dx_processed_expr]);

    let ewm_options_adx = EWMOptions {
        alpha,
        adjust: false,
        bias: false,
        min_periods: 1,
        ignore_nulls: true,
    };
    let adx_expr_final = col(adx_processed_col_name)
        .ewm_mean(ewm_options_adx)
        .alias("temp_adx");
    expr_groups.push(vec![adx_expr_final]);

    let adxr_expr =
        ((col("temp_adx") + col("temp_adx").shift(adxr_length_lit)) * lit_0_5).alias("temp_adxr");
    expr_groups.push(vec![adxr_expr]);

    let plus_dm_final_expr = when(
        col("index")
            .cast(DataType::Int64)
            .lt(period_minus_1_lit_dm.clone()),
    )
    .then(null_final_fill.clone())
    .otherwise(col("plus_dm_smooth_temp"))
    .alias(&config.plus_dm_alias);

    let minus_dm_final_expr = when(col("index").cast(DataType::Int64).lt(period_minus_1_lit_dm))
        .then(null_final_fill.clone())
        .otherwise(col("minus_dm_smooth_temp"))
        .alias(&config.minus_dm_alias);

    let adx_final_expr = when(col("index").cast(DataType::Int64).lt(adx_lookback_lit))
        .then(null_final_fill.clone())
        .otherwise(col("temp_adx"))
        .alias(&config.adx_alias);

    let adxr_final_expr = when(col("index").cast(DataType::Int64).lt(adxr_lookback_lit))
        .then(null_final_fill)
        .otherwise(col("temp_adxr"))
        .alias(&config.adxr_alias);

    expr_groups.push(vec![
        plus_dm_final_expr,
        minus_dm_final_expr,
        adx_final_expr,
        adxr_final_expr,
    ]);

    Ok(expr_groups)
}

/// 统一对外 null->nan 处理表达式。
pub(crate) fn final_null_to_nan_exprs(config: &ADXConfig) -> Vec<Expr> {
    vec![
        null_to_nan_expr(&config.adx_alias),
        null_to_nan_expr(&config.adxr_alias),
        null_to_nan_expr(&config.plus_dm_alias),
        null_to_nan_expr(&config.minus_dm_alias),
    ]
}
