use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

/// EMA 的配置结构体
pub struct EMAConfig {
    pub column_name: String, // 要计算 EMA 的输入列名 (e.g., "close")
    pub alias_name: String,  // EMA 结果的输出别名 (e.g., "ema")
    pub period: i64,
}

// --- 表达式分离函数 ---

/// 🔍 返回计算 EMA 所需的所有核心表达式。
///
/// 包括：处理过的收盘价表达式 (processed_close) 和最终的 EMA 表达式。
///
/// # 参数
/// * `config`: EMA 的配置结构体。
///
/// # 返回
/// 返回一个 Polars Result，包含 (processed_close Expr, EMA Expr)
fn ema_expr(config: &EMAConfig) -> PolarsResult<(Expr, Expr)> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    // 内部临时列名，用于计算过程，保持在表达式层内部
    let initial_value_temp_name = "ema_initial_value_temp";
    let processed_close_temp_name = "ema_processed_close_temp";
    let index_col_name = "index"; // 依赖于 lazy_df.with_row_index("index", None)

    // 1. SMA 初始值表达式：高效计算前 N 个值的平均值
    let sma_initial_value_expr = col(col_name) // 使用配置的输入列
        .slice(0, period as u32)
        .mean()
        .alias(initial_value_temp_name); // 赋予临时别名

    // 2. processed_close 表达式：负责注入 SMA 初始值
    // 注意：这个表达式依赖于 LazyFrame 中已存在的 "index" 列
    let processed_close_expr = when(
        col(index_col_name)
            .cast(DataType::Int64)
            .lt(lit(period - 1)),
    )
    .then(lit(NULL))
    .when(
        col(index_col_name)
            .cast(DataType::Int64)
            .eq(lit(period - 1)),
    )
    .then(sma_initial_value_expr) // 注入高效的 SMA 标量表达式
    .otherwise(col(col_name).cast(DataType::Float64)) // 使用配置的输入列
    .alias(processed_close_temp_name); // 赋予临时别名

    // 3. 最终的 EMA 表达式
    let ema_expr = col(processed_close_temp_name) // 使用内部临时列
        .ewm_mean(EWMOptions {
            alpha: 2.0 / (period as f64 + 1.0),
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: true,
        })
        .alias(alias_name); // 使用配置的输出别名

    Ok((processed_close_expr, ema_expr))
}

// --- 蓝图函数 (复用分离出的表达式) ---

/// 将 EMA 的完整计算流程封装成一个纯粹的 LazyFrame -> LazyFrame 函数。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
fn ema_lazy(lazy_df: LazyFrame, period: i64) -> PolarsResult<LazyFrame> {
    // 蓝图层负责定义配置（包括默认输入列名和输出别名）
    let config = EMAConfig {
        column_name: "close".to_string(), // 默认输入 "close" 列
        alias_name: "ema".to_string(),    // 默认输出别名 "ema"
        period,
    };

    // 1. 获取所有核心表达式
    let (processed_close_expr, ema_expr) = ema_expr(&config)?;

    // 2. 链接到 LazyFrame 上
    let result_lazy_df = lazy_df
        // 必须添加行索引，因为 processed_close_expr 依赖于它
        .with_row_index("index", None)
        // 计算并注入 "processed_close" (它会自动包含 SMA 初始值计算)
        .with_column(processed_close_expr)
        // 计算 "ema"
        .with_column(ema_expr);

    Ok(result_lazy_df)
}

// --- Eager 包装函数 (保持不变) ---

pub fn ema_eager(ohlcv_df: &DataFrame, period: i64) -> PolarsResult<Series> {
    // --- 边界情况处理 (省略不变) ---
    if period <= 0 {
        return Err(PolarsError::InvalidOperation(
            "Period must be positive".into(),
        ));
    }
    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty("ema".into(), &DataType::Float64));
    }
    let n_periods = period as usize;
    if series_len < n_periods {
        return Ok(Series::new_null("ema".into(), series_len));
    }

    // --- 核心逻辑变更为调用懒人函数 ---
    let lazy_df = ohlcv_df.clone().lazy();

    // 1. 调用纯粹的懒人函数 `ema_lazy`
    let lazy_plan = ema_lazy(lazy_df, period)?;

    // 2. 执行计算并提取结果
    // 由于 ema_lazy 使用了默认配置 "ema"，这里选择 "ema" 列
    let result_df = lazy_plan.select([col("ema")]).collect()?;

    Ok(result_df.column("ema")?.as_materialized_series().clone())
}
