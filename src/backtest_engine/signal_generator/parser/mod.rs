//! # 信号条件解析器
//!
//! 使用 nom 解析器组合子将字符串条件表达式解析为结构化的 `SignalCondition` 类型。
//!
//! ## 语法规则
//!
//! 完整语法：`[!] LeftOperand Op RightOperand`
//!
//! ### 数据操作数 (Data Operand)
//! 格式：`name, source, offset`
//! - `name`: 数据列名称（如 `close`, `sma_0`, `rsi_0`）
//! - `source`: 数据源名称（如 `ohlcv_15m`, `ohlcv_1h`）
//! - `offset`: 偏移量（可选，默认为 0）
//!   - 单个值：`0`, `1`, `2`
//!   - AND范围：`0&5` (满足范围内所有偏移)
//!   - OR范围：`0|5` (满足范围内任一偏移)
//!
//! ### 比较运算符 (Operators)
//! - 普通比较：`>`, `<`, `>=`, `<=`, `==`, `!=`
//! - 交叉比较：`x>`, `x<`, `x>=`, `x<=`, `x==`, `x!=`
//!   - 交叉表示当前值与前一个值的关系发生变化
//!
//! ### 右操作数 (Right Operand)
//! 可以是以下三种之一：
//! - **参数引用**：`$param_name` (如 `$rsi_middle`)
//! - **数值字面量**：`70`, `0.5`, `-10.5`
//! - **数据操作数**：`name, source, offset`
//!
//! ### 逻辑否定
//! 在条件前加 `!` 表示对结果取反
//!
//! ## 示例
//!
//! ```text
//! # 基础比较
//! "close, ohlcv_15m, 0 > sma_0, ohlcv_15m, 0"
//! # 含义：当前 15分钟收盘价 大于 当前 SMA(0)
//!
//! # 参数比较
//! "rsi_0, ohlcv_1h, 0 < $rsi_lower"
//! # 含义：当前 1小时 RSI 小于参数 rsi_lower
//!
//! # 数值比较
//! "close, ohlcv_15m, 0 > 100"
//! # 含义：当前 15分钟收盘价 大于 100
//!
//! # 交叉向上
//! "close, ohlcv_15m, 0 x> bbands_0_upper, ohlcv_15m, 0"
//! # 含义：收盘价向上突破布林带上轨（前一根K线在下方，当前K线在上方）
//!
//! # 范围偏移 (AND)
//! "close, ohlcv_15m, 0&2 > sma_0, ohlcv_15m, 0"
//! # 含义：最近3根K线的收盘价都大于 SMA (offsets: 0, 1, 2)
//!
//! # 范围偏移 (OR)
//! "close, ohlcv_15m, 0|2 > sma_0, ohlcv_15m, 0"
//! # 含义：最近3根K线中至少有一根收盘价大于 SMA
//!
//! # 逻辑否定
//! "! close, ohlcv_15m, 0 < 50"
//! # 含义：收盘价不小于 50（等价于 >= 50）
//! ```

mod lexer;

use lexer::{parse_data_operand, parse_op, parse_right_operand, Res};
use nom::{
    bytes::complete::tag,
    character::complete::multispace0,
    combinator::opt,
    sequence::{delimited, preceded},
    Parser,
};

use super::types::{CompareOp, OffsetType, SignalCondition};
use crate::error::{QuantError, SignalError};

/// 解析完整的条件表达式（nom 底层函数）
///
/// 语法：`[!] LeftOperand Op RightOperand`
///
/// # 组成部分
/// 1. **可选的否定**：`!` 前缀
/// 2. **左操作数**：必须是数据操作数
/// 3. **运算符**：比较运算符
/// 4. **右操作数**：参数、数值或数据操作数
///
/// # 示例
/// ```text
/// "close, ohlcv_15m, 0 > 100"
/// "! rsi_0, ohlcv_1h, 0 < $rsi_lower"
/// "sma_0, ohlcv_4h, 0&2 x> sma_1, ohlcv_4h, 0"
/// ```
pub fn parse_condition_str(input: &str) -> Res<'_, SignalCondition> {
    let (input, negated) = opt(delimited(multispace0, tag("!"), multispace0)).parse(input)?;
    let (input, left) = delimited(multispace0, parse_data_operand, multispace0).parse(input)?;
    let (input, op) = delimited(multispace0, parse_op, multispace0).parse(input)?;
    let (input, right) = delimited(multispace0, parse_right_operand, multispace0).parse(input)?;

    // 探测 ".." 范围分隔符
    let (input, zone_end) = opt(preceded(
        delimited(multispace0, tag(".."), multispace0),
        parse_right_operand,
    ))
    .parse(input)?;

    Ok((
        input,
        SignalCondition {
            negated: negated.is_some(),
            left,
            right,
            op,
            zone_end,
        },
    ))
}

/// 解析条件字符串的公共 API
///
/// 将字符串解析为 `SignalCondition`，并进行错误处理
///
/// # 参数
/// - `input`: 条件字符串
///
/// # 返回
/// - `Ok(SignalCondition)`: 解析成功
/// - `Err(QuantError::Signal(SignalError::ParseError))`: 解析失败
///
/// # 示例
/// ```rust
/// use pyo3_quant::backtest_engine::signal_generator::parser::parse_condition;
///
/// let cond = parse_condition("close, ohlcv_15m, 0 > sma_0, ohlcv_15m, 0").unwrap();
/// assert!(!cond.negated);
/// assert_eq!(cond.left.name, "close");
/// ```
///
/// # 错误情况
/// - 语法错误：运算符错误、缺少逗号等
/// - 多余字符：条件后有未解析的内容
/// - 不完整输入：条件不完整
pub fn parse_condition(input: &str) -> Result<SignalCondition, QuantError> {
    let trimmed_input = input.trim();
    match parse_condition_str(trimmed_input) {
        Ok((remaining, condition)) => {
            if !remaining.trim().is_empty() {
                return Err(QuantError::Signal(SignalError::ParseError(format!(
                    "解析条件时发现多余字符。\n条件: '{}'\n多余部分: '{}'",
                    trimmed_input, remaining
                ))));
            }

            // 区间穿越(..) 约束校验
            if condition.zone_end.is_some() {
                // 1. 仅允许与交叉操作符搭配
                match condition.op {
                    CompareOp::CGT | CompareOp::CLT | CompareOp::CGE | CompareOp::CLE => {}
                    _ => {
                        return Err(QuantError::Signal(SignalError::ParseError(format!(
                            "区间穿越(..)仅允许与交叉操作符搭配(x>, x<, x>=, x<=)，当前操作符不支持。\n条件: '{}'",
                            trimmed_input
                        ))))
                    }
                }
                // 2. 左操作数仅支持单值偏移
                match &condition.left.offset {
                    OffsetType::Single(_) => {}
                    _ => {
                        return Err(QuantError::Signal(SignalError::ParseError(format!(
                            "区间穿越(..)目前仅支持单值偏移，不支持范围(如 &0-2)或列表(如 |1/3)偏移。\n条件: '{}'",
                            trimmed_input
                        ))))
                    }
                }
            }

            Ok(condition)
        }
        Err(nom::Err::Error(e)) | Err(nom::Err::Failure(e)) => {
            Err(QuantError::Signal(SignalError::ParseError(format!(
                "解析条件失败。\n条件: '{}'\n错误位置: '{}'\n错误类型: {:?}",
                trimmed_input, e.input, e.code
            ))))
        }
        Err(nom::Err::Incomplete(_)) => Err(QuantError::Signal(SignalError::ParseError(format!(
            "条件不完整。\n条件: '{}'",
            trimmed_input
        )))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backtest_engine::signal_generator::types::{CompareOp, SignalRightOperand};

    #[test]
    fn test_parse_zone_cross_scalar() {
        let cond = parse_condition("rsi, ohlcv_15m, 0 x> 30..70").unwrap();
        assert!(matches!(cond.op, CompareOp::CGT));
        if let SignalRightOperand::Scalar(v) = cond.right {
            assert!((v - 30.0).abs() < f64::EPSILON);
        } else {
            panic!("Expected Scalar operand");
        }
        assert!(cond.zone_end.is_some());
        if let SignalRightOperand::Scalar(v) = cond.zone_end.unwrap() {
            assert!((v - 70.0).abs() < f64::EPSILON);
        } else {
            panic!("Expected Scalar operand");
        }
    }

    #[test]
    fn test_parse_zone_cross_data_operand() {
        let cond = parse_condition(
            "close, ohlcv_1h, 0 x> bbands_lower, ohlcv_1h, 0 .. bbands_middle, ohlcv_1h, 0",
        )
        .unwrap();
        assert!(cond.zone_end.is_some());
        if let SignalRightOperand::Data(d) = cond.zone_end.unwrap() {
            assert_eq!(d.name, "bbands_middle");
        } else {
            panic!("Expected Data operand");
        }
    }

    #[test]
    fn test_parse_zone_cross_rejects_non_cross_op() {
        // 普通 > 不允许搭配 ..
        let result = parse_condition("rsi, ohlcv_15m, 0 > 30..70");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_zone_cross_rejects_range_offset() {
        // 范围偏移不允许搭配 ..
        let result = parse_condition("rsi, ohlcv_15m, &1-3 x> 30..70");
        assert!(result.is_err());
    }

    #[test]
    fn test_parse_zone_cross_with_decimal() {
        // 小数点不会和 .. 冲突
        let cond = parse_condition("rsi, ohlcv_15m, 0 x> 20.5..60.3").unwrap();
        if let SignalRightOperand::Scalar(v) = cond.right {
            assert!((v - 20.5).abs() < f64::EPSILON);
        }
        assert!(cond.zone_end.is_some());
        if let SignalRightOperand::Scalar(v) = cond.zone_end.unwrap() {
            assert!((v - 60.3).abs() < f64::EPSILON);
        }
    }
}
