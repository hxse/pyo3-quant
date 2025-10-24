use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

use crate::backtest_engine::indicators::tr::{tr_expr, TRConfig};

/// ATR (Average True Range) 的配置结构体
pub struct ATRConfig {
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub alias_name: String,
    pub period: i64,
}

// --- 表达式层 ---

/// 🔍 返回计算 ATR 所需的所有核心表达式。
///
/// 包括：处理过的 TR 表达式 (processed_tr) 和最终的 ATR 表达式。
///
/// **表达式层 (Expr)**
/// 接收配置结构体，所有列名均通过结构体参数传入。
pub fn atr_expr(config: &ATRConfig) -> PolarsResult<(Expr, Expr)> {
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    // 内部临时列名，用于计算过程，保持在表达式层内部
    let tr_temp_name = "tr_temp";
    let initial_value_temp_name = "atr_initial_value_temp";
    let processed_tr_temp_name = "processed_tr_temp";
    let index_col_name = "index"; // 依赖于 lazy_df.with_row_index("index", None)

    // 1. 计算真实波幅 (TR)
    // TR 表达式在 atr_lazy 中直接注入，这里不需要构建 tr_series_expr

    // 2. SMA 初始值表达式：高效计算前 N 个 TR 值的平均值
    let sma_initial_value_expr = col(tr_temp_name) // 使用 TR 临时列
        .slice(1, period as u32) // 修改: 从索引 1 开始切片，以匹配 TA-Lib 的初始 SMA 逻辑
        .mean()
        .alias(initial_value_temp_name); // 赋予临时别名

    // 3. 构建处理后的 TR 序列 (presma 逻辑)
    //    前 period 个值设为 NaN (与 TA-Lib 保持一致)
    //    第 period 个位置 (0-indexed) 放入 SMA 初始值
    //    其余位置为原始 TR 值
    let processed_tr_expr = when(
        col(index_col_name).cast(DataType::Int64).lt(lit(period)), // 修改: 从 period - 1 改为 period
    )
    .then(lit(NULL))
    .when(
        col(index_col_name).cast(DataType::Int64).eq(lit(period)), // 修改: 从 period - 1 改为 period
    )
    .then(sma_initial_value_expr) // 注入高效的 SMA 标量表达式
    .otherwise(col(tr_temp_name)) // 使用原始 TR 表达式
    .alias(processed_tr_temp_name); // 赋予临时别名

    // 4. 对处理后的 TR 序列应用 RMA
    let atr_expr = col(processed_tr_temp_name) // 使用内部临时列
        .ewm_mean(EWMOptions {
            alpha: 1.0 / (period as f64), // ATR 的 Wilder Smoothing 因子是 1/period
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: true,
        })
        .alias(alias_name); // 使用配置的输出别名

    Ok((processed_tr_expr, atr_expr))
}

// --- 蓝图层 ---

/// 🧱 平均真实波幅 (ATR) 惰性蓝图函数：接收 LazyFrame，返回包含 "atr" 列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn atr_lazy(lazy_df: LazyFrame, period: i64) -> PolarsResult<LazyFrame> {
    let config = ATRConfig {
        high_col: "high".to_string(),
        low_col: "low".to_string(),
        close_col: "close".to_string(),
        alias_name: "atr".to_string(),
        period,
    };

    // 1. 获取所有核心表达式
    let (processed_tr_expr, atr_expr) = atr_expr(&config)?;

    // 2. 链接到 LazyFrame 上
    let result_lazy_df = lazy_df
        // 必须添加行索引，因为 processed_tr_expr 依赖于它
        .with_row_index("index", None)
        // 计算并注入 "tr_temp"
        .with_column(tr_expr(&TRConfig {
            high_col: config.high_col.clone(),
            low_col: config.low_col.clone(),
            close_col: config.close_col.clone(),
            alias_name: "tr_temp".to_string(),
        })?)
        // 计算并注入 "processed_tr_temp" (它会自动包含 SMA 初始值计算)
        .with_column(processed_tr_expr)
        // 计算 "atr"
        .with_column(atr_expr)
        // 删除所有临时列，只保留原始 OHLCV 列和最终的 ATR 列
        .select(&[
            col(&config.high_col),
            col(&config.low_col),
            col(&config.close_col),
            col(&config.alias_name),
        ]);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 平均真实波幅 (ATR) 急切计算函数
///
/// **计算层 (Eager Wrapper)**
pub fn atr_eager(ohlcv_df: &DataFrame, period: i64) -> PolarsResult<Series> {
    if period <= 0 {
        return Err(PolarsError::InvalidOperation(
            "Period must be positive".into(),
        ));
    }
    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty("atr".into(), &DataType::Float64));
    }
    let n_periods = period as usize;
    if series_len < n_periods {
        return Ok(Series::new_null("atr".into(), series_len));
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = atr_lazy(lazy_df, period)?;
    let df = lazy_plan.select([col("atr")]).collect()?;

    Ok(df.column("atr")?.as_materialized_series().clone())
}
