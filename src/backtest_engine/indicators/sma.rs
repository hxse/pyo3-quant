use polars::lazy::dsl::col;
use polars::prelude::*;

/// 简单移动平均线 (SMA) 的配置结构体
pub struct SMAConfig {
    pub column_name: String, // 要计算 SMA 的输入列名
    pub alias_name: String,  // SMA 结果的输出别名
    pub period: i64,
}

// --- 表达式层 ---

/// 🔍 返回计算简单移动平均线 (SMA) 的 Polars 表达式
///
/// **表达式层 (Expr)**
/// 接收配置结构体，实现了参数的高度抽象化。
pub fn sma_expr(config: &SMAConfig) -> PolarsResult<Expr> {
    let column_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    if period <= 0 {
        return Err(polars::prelude::PolarsError::InvalidOperation(
            "Period must be positive for SMA calculation".into(),
        ));
    }

    let sma_expr = col(column_name) // 使用抽象的输入列名
        .cast(DataType::Float64)
        .rolling_mean(RollingOptionsFixedWindow {
            window_size: period as usize,
            min_periods: period as usize,
            weights: None,
            center: false,
            fn_params: None,
        })
        .alias(alias_name); // 使用抽象的输出别名

    Ok(sma_expr)
}

// --- 蓝图层 ---

/// 🧱 SMA 惰性蓝图函数：接收 LazyFrame，返回包含 "sma" 列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn sma_lazy(lazy_df: LazyFrame, period: i64) -> PolarsResult<LazyFrame> {
    // 蓝图层负责定义配置（包括默认输入列名和输出别名）
    let config = SMAConfig {
        column_name: "close".to_string(), // 默认输入 "close" 列
        alias_name: "sma".to_string(),    // 默认输出别名 "sma"
        period,
    };

    // 1. 获取 SMA 表达式
    let sma_expr = sma_expr(&config)?;

    // 2. 构建 LazyFrame 管道：添加 SMA 列
    let result_lazy_df = lazy_df.with_column(sma_expr);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 SMA 急切计算函数
///
/// **计算层 (Eager Wrapper)**
pub fn sma_eager(ohlcv_df: &DataFrame, period: i64) -> PolarsResult<Series> {
    // 边界检查
    if period <= 0 {
        return Err(polars::prelude::PolarsError::InvalidOperation(
            "Period must be positive for SMA calculation".into(),
        ));
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty("sma".into(), &DataType::Float64));
    }

    // 1. 将 DataFrame 转换为 LazyFrame
    let lazy_df = ohlcv_df.clone().lazy();

    // 2. 调用蓝图函数构建计算计划 (默认输出列名为 "sma")
    let lazy_plan = sma_lazy(lazy_df, period)?;

    // 3. 触发计算，只选择最终结果
    let df = lazy_plan.select([col("sma")]).collect()?;

    // 4. 提取结果 Series
    Ok(df.column("sma")?.as_materialized_series().clone())
}
