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

use nom::{
    branch::alt,
    bytes::complete::tag,
    character::complete::{alpha1, alphanumeric1, digit1, multispace0},
    combinator::{map, map_res, opt, recognize, value},
    error::Error,
    multi::many0,
    sequence::{delimited, pair, preceded, separated_pair},
    IResult, Parser,
};
use std::str::FromStr;

use super::types::{
    CompareOp, OffsetType, ParamOperand, SignalCondition, SignalDataOperand, SignalRightOperand,
};
use crate::error::{QuantError, SignalError};

type Res<'a, T> = IResult<&'a str, T, Error<&'a str>>;

/// 解析标识符（变量名、列名等）
///
/// 规则：以字母或下划线开头，后跟任意数量的字母、数字、下划线或减号
///
/// # 示例
/// - `close` ✓
/// - `sma_0` ✓
/// - `rsi-middle` ✓
/// - `bbands_0_upper` ✓
/// - `_temp` ✓
/// - `123abc` ✗ (不能以数字开头)
/// - `-test` ✗ (不能以减号开头)
fn parse_identifier(input: &str) -> Res<&str> {
    recognize(pair(
        alt((alpha1, tag("_"))),
        many0(alt((alphanumeric1, tag("_"), tag("-")))),
    ))
    .parse(input)
}

/// 解析无符号32位整数
///
/// # 示例
/// - `0` → 0
/// - `123` → 123
fn parse_u32(input: &str) -> Res<u32> {
    map_res(digit1, u32::from_str).parse(input)
}

/// 解析64位浮点数（支持负数和小数）
///
/// # 示例
/// - `70` → 70.0
/// - `0.5` → 0.5
/// - `-10.5` → -10.5
fn parse_f64(input: &str) -> Res<f64> {
    map_res(
        recognize(pair(
            opt(tag("-")),
            pair(digit1, opt(pair(tag("."), digit1))),
        )),
        f64::from_str,
    )
    .parse(input)
}

/// 解析 AND 范围偏移：`&start-end`
///
/// AND 表示范围内所有偏移都必须满足条件
///
/// # 示例
/// - `&1-5` → OffsetType::RangeAnd(1, 5)  // offsets: [1, 2, 3, 4, 5]
/// - `&0-2` → OffsetType::RangeAnd(0, 2)  // offsets: [0, 1, 2]
fn parse_offset_range_and(input: &str) -> Res<OffsetType> {
    map(
        preceded(tag("&"), separated_pair(parse_u32, tag("-"), parse_u32)),
        |(start, end)| OffsetType::RangeAnd(start, end),
    )
    .parse(input)
}

/// 解析 OR 范围偏移：`|start-end`
///
/// OR 表示范围内至少有一个偏移满足条件即可
///
/// # 示例
/// - `|1-5` → OffsetType::RangeOr(1, 5)  // offsets: [1, 2, 3, 4, 5]
/// - `|0-2` → OffsetType::RangeOr(0, 2)  // offsets: [0, 1, 2]
fn parse_offset_range_or(input: &str) -> Res<OffsetType> {
    map(
        preceded(tag("|"), separated_pair(parse_u32, tag("-"), parse_u32)),
        |(start, end)| OffsetType::RangeOr(start, end),
    )
    .parse(input)
}

/// 解析 AND 列表偏移：`&val1/val2/val3`
///
/// # 示例
/// - `&0` → OffsetType::ListAnd([0])
/// - `&0/1/5` → OffsetType::ListAnd([0, 1, 5])
fn parse_offset_list_and(input: &str) -> Res<OffsetType> {
    use nom::multi::separated_list1;
    map(
        preceded(tag("&"), separated_list1(tag("/"), parse_u32)),
        |vals| {
            if vals.len() == 1 {
                OffsetType::Single(vals[0])
            } else {
                OffsetType::ListAnd(vals)
            }
        },
    )
    .parse(input)
}

/// 解析 OR 列表偏移：`|val1/val2/val3`
///
/// # 示例
/// - `|0` → OffsetType::ListOr([0])
/// - `|0/1/5` → OffsetType::ListOr([0, 1, 5])
fn parse_offset_list_or(input: &str) -> Res<OffsetType> {
    use nom::multi::separated_list1;
    map(
        preceded(tag("|"), separated_list1(tag("/"), parse_u32)),
        |vals| {
            if vals.len() == 1 {
                OffsetType::Single(vals[0])
            } else {
                OffsetType::ListOr(vals)
            }
        },
    )
    .parse(input)
}

/// 解析偏移量（单个值、范围或列表）
///
/// # 示例
/// - `0` → OffsetType::Single(0)
/// - `&1-5` → OffsetType::RangeAnd(1, 5)  // 范围：[1,2,3,4,5]全都符合
/// - `|1-5` → OffsetType::RangeOr(1, 5)   // 范围：[1,2,3,4,5]任一符合
/// - `&0/1/5` → OffsetType::ListAnd([0,1,5])  // 列表：[0,1,5]全都符合
/// - `|0/1/5` → OffsetType::ListOr([0,1,5])   // 列表：[0,1,5]任一符合
fn parse_offset(input: &str) -> Res<OffsetType> {
    alt((
        parse_offset_range_and,             // &1-5
        parse_offset_range_or,              // |1-5
        parse_offset_list_and,              // &0/1/5 或 &0
        parse_offset_list_or,               // |0/1/5 或 |0
        map(parse_u32, OffsetType::Single), // 0
    ))
    .parse(input)
}

/// 解析数据操作数：`name, source[, offset]`
///
/// offset 是可选的，默认为 0
///
/// # 示例
/// - `close, ohlcv_15m, 0` → SignalDataOperand { name: "close", source: "ohlcv_15m", offset: Single(0) }
/// - `sma_0, ohlcv_1h` → SignalDataOperand { name: "sma_0", source: "ohlcv_1h", offset: Single(0) }
/// - `rsi_0, ohlcv_4h, 0&2` → SignalDataOperand { name: "rsi_0", source: "ohlcv_4h", offset: RangeAnd(0, 2) }
fn parse_data_operand(input: &str) -> Res<SignalDataOperand> {
    let (input, _) = multispace0(input)?;
    let (input, name) = parse_identifier(input)?;
    let (input, _) = delimited(multispace0, tag(","), multispace0).parse(input)?;
    let (input, source) = parse_identifier(input)?;

    let (input, offset) = opt(preceded(
        delimited(multispace0, tag(","), multispace0),
        parse_offset,
    ))
    .parse(input)?;

    Ok((
        input,
        SignalDataOperand {
            name: name.to_string(),
            source: source.to_string(),
            offset: offset.unwrap_or(OffsetType::Single(0)),
        },
    ))
}

/// 解析参数操作数：`$param_name`
///
/// 以 `$` 开头表示引用信号参数
///
/// # 示例
/// - `$rsi_middle` → ParamOperand { name: "rsi_middle" }
/// - `$stop_loss` → ParamOperand { name: "stop_loss" }
fn parse_param_operand(input: &str) -> Res<ParamOperand> {
    map(preceded(tag("$"), parse_identifier), |name| ParamOperand {
        name: name.to_string(),
    })
    .parse(input)
}

/// 解析右操作数（参数、数值或数据）
///
/// 尝试顺序：参数 → 数值 → 数据操作数
///
/// # 示例
/// - `$rsi_lower` → SignalRightOperand::Param(...)
/// - `70` → SignalRightOperand::Scalar(70.0)
/// - `sma_1, ohlcv_15m, 0` → SignalRightOperand::Data(...)
fn parse_right_operand(input: &str) -> Res<SignalRightOperand> {
    alt((
        map(parse_param_operand, SignalRightOperand::Param),
        map(parse_f64, SignalRightOperand::Scalar),
        map(parse_data_operand, SignalRightOperand::Data),
    ))
    .parse(input)
}

/// 解析比较运算符
///
/// 优先匹配长运算符（如 `x>=` 先于 `>=` 和 `>`）
///
/// # 普通运算符
/// - `>`, `<`, `>=`, `<=`, `==`, `!=`
///
/// # 交叉运算符（用 `x` 前缀表示）
/// - `x>`: 向上突破（前值 <= 后值，当前值 > 后值）
/// - `x<`: 向下突破（前值 >= 后值，当前值 < 后值）
/// - `x>=`, `x<=`, `x==`, `x!=`: 类似的交叉逻辑
fn parse_op(input: &str) -> Res<CompareOp> {
    alt((
        value(CompareOp::CGT, tag("x>")),
        value(CompareOp::CLT, tag("x<")),
        value(CompareOp::CGE, tag("x>=")),
        value(CompareOp::CLE, tag("x<=")),
        value(CompareOp::CEQ, tag("x==")),
        value(CompareOp::CNE, tag("x!=")),
        value(CompareOp::GE, tag(">=")),
        value(CompareOp::LE, tag("<=")),
        value(CompareOp::EQ, tag("==")),
        value(CompareOp::NE, tag("!=")),
        value(CompareOp::GT, tag(">")),
        value(CompareOp::LT, tag("<")),
    ))
    .parse(input)
}

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
/// ```
/// "close, ohlcv_15m, 0 > 100"
/// "! rsi_0, ohlcv_1h, 0 < $rsi_lower"
/// "sma_0, ohlcv_4h, 0&2 x> sma_1, ohlcv_4h, 0"
/// ```
pub fn parse_condition_str(input: &str) -> Res<SignalCondition> {
    let (input, negated) = opt(delimited(multispace0, tag("!"), multispace0)).parse(input)?;
    let (input, left) = delimited(multispace0, parse_data_operand, multispace0).parse(input)?;
    let (input, op) = delimited(multispace0, parse_op, multispace0).parse(input)?;
    let (input, right) = delimited(multispace0, parse_right_operand, multispace0).parse(input)?;

    Ok((
        input,
        SignalCondition {
            negated: negated.is_some(),
            left,
            right,
            op,
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
/// let cond = parse_condition("close, ohlcv_15m, 0 > sma_0, ohlcv_15m, 0")?;
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
