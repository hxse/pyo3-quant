//! # ADX (Average Directional Index)
//!
// ... (omitted comments for brevity)
//!
use crate::backtest_engine::indicators::tr::{tr_expr, TRConfig};
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

/// ⚙️ Configuration for the ADX indicator.
#[derive(Debug, Clone, PartialEq)]
pub struct ADXConfig {
    /// 📈 High column name.
    pub high_col: String,
    /// 📉 Low column name.
    pub low_col: String,
    /// 📊 Close column name.
    pub close_col: String,
    /// ⏳ Period for ADX calculation.
    pub period: i64,
    /// 🏷 Alias for the ADX output column.
    pub adx_alias: String,
    /// 🏷 Alias for the Plus DM output column.
    pub plus_dm_alias: String,
    /// 🏷 Alias for the Minus DM output column.
    pub minus_dm_alias: String,
    /// ⏳ Period for ADXR calculation.
    pub adxr_length: i64,
    /// 🏷 Alias for the ADXR output column.
    pub adxr_alias: String,
}
impl ADXConfig {
    pub fn new(period: i64) -> Self {
        Self {
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            period,
            adx_alias: "adx".to_string(),
            plus_dm_alias: "plus_dm".to_string(),
            minus_dm_alias: "minus_dm".to_string(),
            adxr_length: 2,
            adxr_alias: "adxr".to_string(),
        }
    }
}

/// 辅助函数：生成修正后的输入序列（用于EWM初始化）和最终的Aggregate表达式
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
    // 移除所有用于防止优化的 period literal 别名
    let period_lit_f64 = lit(period as f64);
    let alpha = 1.0 / period as f64;

    // 1. 计算 Simple Average (SMA) 的配置
    let rolling_opts = RollingOptionsFixedWindow {
        window_size: period_usize,
        min_periods: period_usize,
        weights: None,
        center: false,
        fn_params: None,
    };
    // Simple Sum (用于计算 SMA)
    let dm1_rolling_sum = col(dm1_col_name).rolling_sum(rolling_opts);
    // Initial Simple Average at index P-1: Sum / Period
    let dm1_initial_avg = dm1_rolling_sum / period_lit_f64.clone();

    // 第一个有效索引为 P - 1
    let initial_idx = period - 1;
    let index_col = col(index_col_name).cast(DataType::Int64);
    let initial_idx_lit_i64 = lit(initial_idx);
    let initial_idx_mask = index_col.clone().eq(initial_idx_lit_i64.clone());

    // Store the alias name for the processed column
    let processed_col_name = format!("{}_processed_temp", dm1_col_name);
    // 唯一的 NULL 表达式，用于填充 SMA 之前的行 (保留别名以防 Polars 优化器合并)
    let unique_null_expr = lit(NULL)
        .cast(DataType::Float64)
        .alias(&format!("null_init_{}", dm1_col_name));

    // 2. 创建 'Processed Input' 序列：在 P-1 处注入 SMA，然后 EWM 将在此基础上开始递推
    let dm1_processed_expr = when(index_col.lt(initial_idx_lit_i64))
        .then(unique_null_expr) // 使用独特的 NULL 表达式
        .when(initial_idx_mask)
        .then(dm1_initial_avg) // P-1 处是 SMA
        .otherwise(col(dm1_col_name).cast(DataType::Float64)) // > P-1 处是原始 DM1
        .alias(processed_col_name.as_str());

    // 3. EWM Mean (Polars 递推公式)
    let ewm_options = EWMOptions {
        alpha,
        adjust: false,
        bias: false,
        min_periods: 1,
        ignore_nulls: true,
    };
    // Use the stored alias name string to reference the processed column
    let dm1_mean_fixed = col(processed_col_name.as_str()).ewm_mean(ewm_options);

    // 4. Aggregate Sum (最终输出) = Mean * Period
    let dm_smooth_agg =
        (dm1_mean_fixed * period_lit_f64).alias(format!("{}_smooth_temp", dm1_col_name).as_str());

    Ok((dm1_processed_expr, dm_smooth_agg))
}

/// 辅助函数：计算原始的 +DM1, -DM1, TR 表达式
fn get_raw_dm_tr_exprs(
    config: &ADXConfig,
    index_col_name: &str,
) -> Result<(Expr, Expr, Expr), QuantError> {
    let high = col(&config.high_col);
    let low = col(&config.low_col);
    let index = col(index_col_name);

    // +DM1 and -DM1 calculation
    let diff_p = (high.clone() - high.shift(lit(1))).fill_null(lit(0.0));
    let diff_m = (low.clone().shift(lit(1)) - low.clone()).fill_null(lit(0.0));

    // 移除 when/otherwise 中的所有常量别名
    let lit_0_f64 = lit(0.0);
    // 关键修复：lit_1_i64 必须克隆才能在 plus_dm1 和 minus_dm1 中使用
    let lit_1_i64 = lit(1i64);

    let plus_dm1 = when(index.clone().lt(lit_1_i64.clone())) // <-- 修复点：使用 .clone()
        .then(lit_0_f64.clone())
        .otherwise(
            when((diff_m.clone().gt(lit_0_f64.clone())).and(diff_p.clone().lt(diff_m.clone())))
                .then(lit_0_f64.clone())
                .when((diff_p.clone().gt(lit_0_f64.clone())).and(diff_p.clone().gt(diff_m.clone())))
                .then(diff_p.clone())
                .otherwise(lit_0_f64.clone()),
        )
        .alias("plus_dm1_temp");

    let minus_dm1 = when(index.clone().lt(lit_1_i64)) // <-- 修复点：这里现在可以使用 original lit_1_i64 (或 .clone())
        .then(lit_0_f64.clone())
        .otherwise(
            when((diff_m.clone().gt(lit_0_f64.clone())).and(diff_p.clone().lt(diff_m.clone())))
                .then(diff_m.clone())
                .when((diff_p.clone().gt(lit_0_f64.clone())).and(diff_p.clone().gt(diff_m.clone())))
                .then(lit_0_f64.clone())
                .otherwise(lit_0_f64.clone()),
        )
        .alias("minus_dm1_temp");

    // TR1 expression
    let tr_config = TRConfig {
        high_col: config.high_col.clone(),
        low_col: config.low_col.clone(),
        close_col: config.close_col.clone(),
        alias_name: "tr_temp".to_string(), // 保持别名用于后续引用
    };
    let tr_temp = tr_expr(&tr_config)?.alias("tr_temp");
    Ok((plus_dm1, minus_dm1, tr_temp))
}

/// 🏗 Constructs a lazy DataFrame for ADX, Plus DM, and Minus DM.
pub fn adx_lazy(lazy_df: LazyFrame, config: &ADXConfig) -> Result<LazyFrame, QuantError> {
    let period = config.period;
    let adxr_length = config.adxr_length;
    let index_col_name = "index";
    let period_usize = period as usize;

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

    // --------------------------------------------------------------------------------
    // --- Polars 优化器常量定义 (简化别名) ---
    // --------------------------------------------------------------------------------
    let lit_100 = lit(100.0);
    let lit_0_5 = lit(0.5);
    let lit_0 = lit(0.0);
    let lit_null_f64 = lit(NULL).cast(DataType::Float64);

    // 最终裁剪的 NULL 填充值 (只保留一个别名，其余直接使用 lit_null_f64 或克隆别名)
    let null_final_fill = lit_null_f64.clone().alias("null_final_fill");

    // 最终裁剪的 lookback 值 (移除别名)
    let period_minus_1_lit_dm = lit(period - 1);
    let adx_lookback_lit = lit(2 * period - 1);
    let adxr_lookback_lit = lit(2 * period - 1 + adxr_length);
    // ADXR shift 值 (移除别名)
    let adxr_length_lit = lit(adxr_length);
    // ----------------------------------------------------------------------
    // --- 常量定义结束 ---
    // ----------------------------------------------------------------------

    // --- Step 1: Add Index and Raw DM/TR columns to LazyFrame ---
    let (plus_dm1_raw, minus_dm1_raw, tr_raw) = get_raw_dm_tr_exprs(config, index_col_name)?;
    let mut lazy_df = lazy_df.with_row_index(index_col_name, None).with_columns([
        tr_raw,        // Creates column "tr_temp"
        plus_dm1_raw,  // Creates column "plus_dm1_temp"
        minus_dm1_raw, // Creates column "minus_dm1_temp"
    ]);

    // --- Step 2: Calculate and Add Processed Input Columns (Input for EWM) ---
    // **保持分离**：这是 EWM/SMA 启动的关键步骤，避免 Polars 优化器混淆。
    let (plus_dm1_processed, plus_dm_smooth_agg) =
        get_fixed_aggregate("plus_dm1_temp", period, index_col_name)?;
    let (minus_dm1_processed, minus_dm_smooth_agg) =
        get_fixed_aggregate("minus_dm1_temp", period, index_col_name)?;
    let (tr1_processed, tr_smooth_agg) = get_fixed_aggregate("tr_temp", period, index_col_name)?;

    // FIX: Split into three separate with_columns calls to avoid 'literal' duplicate name for SMA/EWM setup
    lazy_df = lazy_df.with_columns([plus_dm1_processed]);
    lazy_df = lazy_df.with_columns([minus_dm1_processed]);
    lazy_df = lazy_df.with_columns([tr1_processed]);

    // --- Step 3a: Add Smooth Aggregates as Columns (用于 DI/DX 的输入) ---
    // FIX: Split into separate with_columns calls to avoid 'literal' duplicate name for (EWM * Period)
    lazy_df = lazy_df.with_columns([plus_dm_smooth_agg.alias("plus_dm_smooth_temp")]);
    lazy_df = lazy_df.with_columns([minus_dm_smooth_agg.alias("minus_dm_smooth_temp")]);
    lazy_df = lazy_df.with_columns([tr_smooth_agg.alias("tr_smooth_temp")]);

    // --- Step 3b & 3c: Calculate DI and DX Expressions ---
    // Plus DI
    let plus_di = (lit_100.clone()
        * when(col("tr_smooth_temp").gt(lit_0.clone()))
            .then(col("plus_dm_smooth_temp") / col("tr_smooth_temp"))
            .otherwise(lit_0.clone()))
    .alias("temp_plus_di");

    // Minus DI
    let minus_di = (lit_100.clone()
        * when(col("tr_smooth_temp").gt(lit_0.clone()))
            .then(col("minus_dm_smooth_temp") / col("tr_smooth_temp"))
            .otherwise(lit_0.clone()))
    .alias("temp_minus_di");

    // 先注册 Plus DI 和 Minus DI 列
    lazy_df = lazy_df.with_columns([plus_di, minus_di]);

    // 然后计算 DX，使用已注册的 DI 列
    let di_sum_expr = col("temp_plus_di") + col("temp_minus_di");
    let di_diff_abs = (col("temp_plus_di") - col("temp_minus_di")).abs();
    let dx_input_expr = (lit_100.clone()
        * when(di_sum_expr.clone().gt(lit_0.clone()))
            .then(di_diff_abs / di_sum_expr)
            .otherwise(lit_0.clone()))
    .alias("dx_temp");

    // 注册 DX 列
    lazy_df = lazy_df.with_columns([
        dx_input_expr, // Creates column "dx_temp"
    ]);

    // ----------------------------------------------------------------------
    // --- Step 3d: ADX EWM Initialization (引用已注册的 "dx_temp") ---
    // ----------------------------------------------------------------------
    let adx_input_col_name = "dx_temp";
    let adx_processed_col_name = "dx_processed_for_adx_temp";
    let alpha = 1.0 / period as f64;
    let period_lit_f64 = lit(period as f64);

    // 1. 计算 Initial SMA
    let adx_initial_idx = 2 * period - 1; // ADX EWM 启动索引
    let rolling_opts_adx_sma = RollingOptionsFixedWindow {
        window_size: period_usize,
        min_periods: period_usize,
        weights: None,
        center: false,
        fn_params: None,
    };
    let dx_rolling_sum = col(adx_input_col_name).rolling_sum(rolling_opts_adx_sma);
    let dx_initial_avg = dx_rolling_sum / period_lit_f64;
    let index_col = col(index_col_name).cast(DataType::Int64);

    let initial_adx_idx_lit = lit(adx_initial_idx);
    let initial_adx_mask = index_col.clone().eq(initial_adx_idx_lit.clone());
    // 保留别名以防 Polars 优化器合并
    let unique_null_adx_init = lit_null_f64.clone().alias("null_init_adx_for_process");

    // 2. 创建 'Processed DX' 序列
    let dx_processed_expr = when(index_col.lt(initial_adx_idx_lit))
        .then(unique_null_adx_init)
        .when(initial_adx_mask)
        .then(dx_initial_avg) // 2*P-1 处是 P 个 DX 值的 SMA
        .otherwise(col(adx_input_col_name).cast(DataType::Float64))
        .alias(adx_processed_col_name);

    // Add Processed DX to the LazyFrame
    lazy_df = lazy_df.with_columns([dx_processed_expr]);

    // --- Step 3e: Calculate and Add Final ADX ---
    // 3. ADX EWM Mean
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
    // Add ADX
    lazy_df = lazy_df.with_columns([adx_expr_final]);

    // --- Step 3f: Calculate and Add Final ADXR (引用上一步创建的 ADX) ---
    // ADXR
    let adxr_expr =
        ((col("temp_adx") + col("temp_adx").shift(adxr_length_lit)) * lit_0_5).alias("temp_adxr");
    // Add ADXR
    lazy_df = lazy_df.with_columns([adxr_expr]);

    // --- Step 4: Final clipping and selection ---
    // Plus DM
    let plus_dm_final_expr = when(
        col("index")
            .cast(DataType::Int64)
            .lt(period_minus_1_lit_dm.clone()),
    )
    .then(null_final_fill.clone())
    .otherwise(col("plus_dm_smooth_temp"))
    .alias(&config.plus_dm_alias);

    // Minus DM
    let minus_dm_final_expr = when(col("index").cast(DataType::Int64).lt(period_minus_1_lit_dm))
        .then(null_final_fill.clone())
        .otherwise(col("minus_dm_smooth_temp"))
        .alias(&config.minus_dm_alias);

    // ADX
    let adx_final_expr = when(col("index").cast(DataType::Int64).lt(adx_lookback_lit))
        .then(null_final_fill.clone())
        .otherwise(col("temp_adx"))
        .alias(&config.adx_alias);

    // ADXR
    let adxr_final_expr = when(col("index").cast(DataType::Int64).lt(adxr_lookback_lit))
        .then(null_final_fill)
        .otherwise(col("temp_adxr"))
        .alias(&config.adxr_alias);

    // 所有的最终表达式合并到一个 with_columns 调用中
    lazy_df = lazy_df.with_columns([
        plus_dm_final_expr,
        minus_dm_final_expr,
        adx_final_expr,
        adxr_final_expr,
    ]);

    // Final selection
    Ok(lazy_df.select(&[
        col(&config.adx_alias),
        col(&config.adxr_alias),
        col(&config.plus_dm_alias),
        col(&config.minus_dm_alias),
    ]))
}

/// 🚀 Eagerly computes ADX, Plus DM, Minus DM, and ADXR.
pub fn adx_eager(
    df: &DataFrame,
    config: &ADXConfig,
) -> Result<(Series, Series, Series, Series), QuantError> {
    let lazy_df = df.clone().lazy();
    let df_with_adx = adx_lazy(lazy_df, config)?
        .collect()
        .map_err(QuantError::from)?;

    let adx_series = df_with_adx
        .column(&config.adx_alias)?
        .as_materialized_series()
        .clone();
    let adxr_series = df_with_adx
        .column(&config.adxr_alias)?
        .as_materialized_series()
        .clone();
    let plus_dm_series = df_with_adx
        .column(&config.plus_dm_alias)?
        .as_materialized_series()
        .clone();
    let minus_dm_series = df_with_adx
        .column(&config.minus_dm_alias)?
        .as_materialized_series()
        .clone();

    Ok((adx_series, adxr_series, plus_dm_series, minus_dm_series))
}
