use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

/// 指标计算工具函数模块

/// 将结果中的 NULL 转换为 NaN，以与 pandas-ta/TA-Lib 保持一致
///
/// 这个函数应该在指标计算的最后阶段使用，确保：
/// 1. 计算过程中使用 NULL 避免传播问题
/// 2. 最终结果使用 NaN 与标准库保持一致
///
/// # 参数
/// * `column_name` - 要转换的列名
///
/// # 返回值
/// 返回一个表达式，将指定列的 NULL 值转换为 NaN
pub fn null_to_nan_expr(column_name: &str) -> Expr {
    col(column_name).fill_null(lit(f64::NAN))
}

/// 创建一个表达式，在条件满足时返回 NULL，否则返回另一个表达式
///
/// 这是一个便利函数，用于创建条件性的 NULL 值
///
/// # 参数
/// * `condition` - 条件表达式
/// * `otherwise_expr` - 条件不满足时的表达式
///
/// # 返回值
/// 返回一个条件表达式，条件满足时为 NULL，否则为 otherwise_expr
pub fn null_when_expr(condition: Expr, otherwise_expr: Expr) -> Expr {
    when(condition)
        .then(lit(NULL))
        .otherwise(otherwise_expr)
}
