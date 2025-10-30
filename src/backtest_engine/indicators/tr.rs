use super::registry::Indicator;
use crate::data_conversion::input::param::Param;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::{col, lit, max_horizontal, when};
use polars::prelude::*;
use std::collections::HashMap;

/// 真实波幅 (TR) 的配置结构体
pub struct TRConfig {
    pub high_col: String,   // 输入高价列名 (e.g., "high")
    pub low_col: String,    // 输入低价列名 (e.g., "low")
    pub close_col: String,  // 输入收盘价列名 (e.g., "close")
    pub alias_name: String, // TR 结果的输出别名 (e.g., "tr")
}

impl TRConfig {
    pub fn new() -> Self {
        Self {
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            alias_name: "tr".to_string(),
        }
    }
}

// --- 表达式层 ---

/// 🔍 返回计算真实波幅 (True Range, TR) 的 Polars 表达式
///
/// TR = Max(|High - Low|, |High - Prev. Close|, |Prev. Close - Low|)
///
/// **表达式层 (Expr)**
/// 接收配置结构体，所有列名均通过结构体参数传入。
pub fn tr_expr(config: &TRConfig) -> Result<Expr, QuantError> {
    let high_col = config.high_col.as_str();
    let low_col = config.low_col.as_str();
    let close_col = config.close_col.as_str();
    let alias_name = config.alias_name.as_str();

    // 1. 获取前一个收盘价
    let prev_close = col(close_col).shift(lit(1i64));

    // 2. 计算三个可能的波幅项的绝对值
    let hl_abs = (col(high_col) - col(low_col)).abs(); // High - Low
    let hpc_abs = (col(high_col) - prev_close.clone()).abs(); // High - Previous Close
    let lpc_abs = (prev_close.clone() - col(low_col)).abs(); // Previous Close - Low

    // 3. 找出三个波幅中的最大值
    let tr_expr = max_horizontal(vec![hl_abs, hpc_abs, lpc_abs])?;

    // 4. 处理第一个数据点的缺失值 (前一个收盘价为 NULL 的情况)
    let final_tr = when(prev_close.is_null())
        .then(lit(NULL))
        .otherwise(tr_expr)
        .alias(alias_name); // 使用抽象的别名

    Ok(final_tr)
}

// --- 蓝图层 ---

/// 🧱 真实波幅 (TR) 惰性蓝图函数：接收 LazyFrame，返回包含 "tr" 列的 LazyFrame。
///
/// **蓝图层 (LazyFrame -> LazyFrame)**
pub fn tr_lazy(lazy_df: LazyFrame, config: &TRConfig) -> Result<LazyFrame, QuantError> {
    // 1. 蓝图层负责定义配置（默认 OHLCV 列名）
    // let config = TRConfig {
    //     high_col: "high".to_string(),
    //     low_col: "low".to_string(),
    //     close_col: "close".to_string(),
    //     alias_name: "tr".to_string(), // 默认输出别名
    // };

    // 2. 获取 TR 表达式
    let tr_expr = tr_expr(config)?;

    // 3. 构建 LazyFrame 管道：添加 TR 列，并保留原始列
    let result_lazy_df = lazy_df.with_column(tr_expr);

    Ok(result_lazy_df)
}

// --- 计算层 ---

/// 📈 真实波幅 (TR) 急切计算函数
///
/// **计算层 (Eager Wrapper)**
pub fn tr_eager(ohlcv_df: &DataFrame, config: &TRConfig) -> Result<Series, QuantError> {
    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    // 1. 将 DataFrame 转换为 LazyFrame
    let lazy_df = ohlcv_df.clone().lazy();

    // 2. 调用蓝图函数构建计算计划
    let lazy_plan = tr_lazy(lazy_df, config)?;

    // 3. 触发计算，只选择最终的 "tr" 结果
    let df = lazy_plan
        .select([col(config.alias_name.as_str())])
        .collect()
        .map_err(QuantError::from)?; // 触发计算

    // 4. 提取结果 Series
    Ok(df
        .column(config.alias_name.as_str())?
        .as_materialized_series()
        .clone())
}

pub struct TrIndicator;

impl Indicator for TrIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        _param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let mut config = TRConfig::new();
        config.alias_name = indicator_key.to_string();

        let result_series = tr_eager(ohlcv_df, &config)?;

        Ok(vec![result_series])
    }
}
