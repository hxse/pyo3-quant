use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

// 引入抽象后的 sma_expr 函数
use super::sma::sma_expr;
use super::sma::SMAConfig;

/// 布林带的配置结构体，将所有输入参数和输出列名抽象化。
pub struct BBandsConfig {
    pub column_name: String,
    pub period: i64,
    pub std_multiplier: f64,
    // 所有输出列名，现已参数化
    pub middle_band_name: String,
    pub std_dev_name: String,
    pub upper_band_name: String,
    pub lower_band_name: String,
    pub bandwidth_name: String,
    pub percent_b_name: String,
}

// --- 表达式层 ---

/// 返回布林带计算所需的表达式
///
/// **表达式层 (Exprs)**
/// 接收配置结构体，所有列名均通过结构体参数传入。
pub fn bbands_expr(config: &BBandsConfig) -> PolarsResult<(Expr, Expr, Expr, Expr, Expr, Expr)> {
    let col_name = config.column_name.as_str();
    let period = config.period;
    let std_multiplier = config.std_multiplier;

    let middle_name = config.middle_band_name.as_str();
    let std_dev_name = config.std_dev_name.as_str();
    let upper_name = config.upper_band_name.as_str();
    let lower_name = config.lower_band_name.as_str();
    let bandwidth_name = config.bandwidth_name.as_str();
    let percent_b_name = config.percent_b_name.as_str();

    // 确保依赖顺序的 RollingOptions
    let rolling_options = RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: Some(RollingFnParams::Var(RollingVarParams { ddof: 0 })),
    };

    // 1. 中轨（Middle Band）：【复用】抽象化的 sma_expr
    // 1. 创建 SMAConfig 实例
    let sma_config = SMAConfig {
        column_name: col_name.to_string(),     // e.g., "close"
        alias_name: "middle_band".to_string(), // 中轨的别名
        period,                                // e.g., 20
    };

    // 2. 将配置的引用传递给 sma_expr
    let middle_band_expr = sma_expr(&sma_config)?;

    // 2. 标准差（Standard Deviation）：使用配置中的列名作为别名
    let std_dev_expr = col(col_name)
        .cast(DataType::Float64)
        .rolling_std(rolling_options)
        .alias(std_dev_name);

    // 3. 上轨（Upper Band）：依赖 middle_band_name 和 std_dev_name
    let upper_band_expr =
        (col(middle_name) + lit(std_multiplier) * col(std_dev_name)).alias(upper_name);

    // 4. 下轨（Lower Band）：依赖 middle_band_name 和 std_dev_name
    let lower_band_expr =
        (col(middle_name) - lit(std_multiplier) * col(std_dev_name)).alias(lower_name);

    // 5. 带宽（Bandwidth）：依赖 upper_name, lower_name, middle_name
    let bandwidth_expr =
        (lit(100.0) * (col(upper_name) - col(lower_name)) / col(middle_name)).alias(bandwidth_name);

    // 6. %B（Percent B）：依赖 输入列, upper_name, lower_name
    let percent_b_expr = ((col(col_name).cast(DataType::Float64) - col(lower_name))
        / (col(upper_name) - col(lower_name)))
    .alias(percent_b_name);

    Ok((
        middle_band_expr,
        std_dev_expr,
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ))
}

// --- 蓝图层 ---

/// 🧱 布林带惰性蓝图函数：接收 LazyFrame，返回包含所有布林带指标列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn bbands_lazy(
    lazy_df: LazyFrame,
    period: i64,
    std_multiplier: f64,
) -> PolarsResult<LazyFrame> {
    // 蓝图层负责定义配置，包括输入列名和默认的输出列名
    let config = BBandsConfig {
        column_name: "close".to_string(), // 默认使用 "close" 列作为输入
        period,
        std_multiplier,
        // 定义默认输出列名 (与 eager 函数的返回签名匹配)
        middle_band_name: "middle_band".to_string(),
        std_dev_name: "std_dev".to_string(),
        upper_band_name: "upper_band".to_string(),
        lower_band_name: "lower_band".to_string(),
        bandwidth_name: "bandwidth".to_string(),
        percent_b_name: "percent_b".to_string(),
    };

    let (
        middle_band_expr,
        std_dev_expr, // 包含 std_dev，尽管它最终不会被 select
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ) = bbands_expr(&config)?; // 传入配置结构体

    // 核心：保持多步 with_columns 调用以确保表达式的依赖顺序
    let result_lazy_df = lazy_df
        // 步骤1：首先计算 middle_band (复用 SMA) 和 std_dev
        .with_columns([middle_band_expr, std_dev_expr])
        // 步骤2：使用上一步生成的列来计算 upper_band 和 lower_band
        .with_columns([upper_band_expr, lower_band_expr])
        // 步骤3：最后计算依赖于 band 的指标
        .with_columns([bandwidth_expr, percent_b_expr]);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 计算布林带（Bollinger Bands）及其相关指标。
///
/// **计算层 (Eager Wrapper)**
pub fn bbands_eager(
    ohlcv_df: &DataFrame,
    period: i64,
    std_multiplier: f64,
) -> PolarsResult<(Series, Series, Series, Series, Series)> {
    if period <= 0 {
        return Err(PolarsError::InvalidOperation(
            "Period must be positive".into(),
        ));
    }

    // 边界条件处理
    if ohlcv_df.height() == 0 {
        return Ok((
            Series::new_empty("lower_band".into(), &DataType::Float64),
            Series::new_empty("middle_band".into(), &DataType::Float64),
            Series::new_empty("upper_band".into(), &DataType::Float64),
            Series::new_empty("bandwidth".into(), &DataType::Float64),
            Series::new_empty("percent_b".into(), &DataType::Float64),
        ));
    }

    // 1. 将 DataFrame 转换为 LazyFrame
    let lazy_df = ohlcv_df.clone().lazy();

    // 2. 调用蓝图函数构建计算计划
    let lazy_plan = bbands_lazy(lazy_df, period, std_multiplier)?;

    // 3. 触发计算，只选择需要的指标列。
    // 注意：这里使用与 bbands_lazy 中默认配置相匹配的列名
    let combined_df = lazy_plan
        .select([
            col("lower_band"),
            col("middle_band"),
            col("upper_band"),
            col("bandwidth"),
            col("percent_b"),
            // 不选择 std_dev
        ])
        .collect()?;

    // 4. 提取结果 Series
    Ok((
        combined_df
            .column("lower_band")?
            .as_materialized_series()
            .clone(),
        combined_df
            .column("middle_band")?
            .as_materialized_series()
            .clone(),
        combined_df
            .column("upper_band")?
            .as_materialized_series()
            .clone(),
        combined_df
            .column("bandwidth")?
            .as_materialized_series()
            .clone(),
        combined_df
            .column("percent_b")?
            .as_materialized_series()
            .clone(),
    ))
}
