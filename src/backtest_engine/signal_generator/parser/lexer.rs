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

use crate::backtest_engine::signal_generator::types::{
    CompareOp, OffsetType, ParamOperand, SignalDataOperand, SignalRightOperand,
};

pub(super) type Res<'a, T> = IResult<&'a str, T, Error<&'a str>>;

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
fn parse_identifier(input: &str) -> Res<'_, &str> {
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
fn parse_u32(input: &str) -> Res<'_, u32> {
    map_res(digit1, u32::from_str).parse(input)
}

/// 解析64位浮点数（支持负数和小数）
///
/// # 示例
/// - `70` → 70.0
/// - `0.5` → 0.5
/// - `-10.5` → -10.5
fn parse_f64(input: &str) -> Res<'_, f64> {
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
fn parse_offset_range_and(input: &str) -> Res<'_, OffsetType> {
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
fn parse_offset_range_or(input: &str) -> Res<'_, OffsetType> {
    map(
        preceded(tag("|"), separated_pair(parse_u32, tag("-"), parse_u32)),
        |(start, end)| OffsetType::RangeOr(start, end),
    )
    .parse(input)
}

/// 解析 AND 列表偏移：`&val1/val2/val3`
///
/// # 示例
/// - `&0` → OffsetType::Single(0)
/// - `&0/1/5` → OffsetType::ListAnd([0, 1, 5])
fn parse_offset_list_and(input: &str) -> Res<'_, OffsetType> {
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
fn parse_offset_list_or(input: &str) -> Res<'_, OffsetType> {
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
fn parse_offset(input: &str) -> Res<'_, OffsetType> {
    alt((
        parse_offset_range_and,
        parse_offset_range_or,
        parse_offset_list_and,
        parse_offset_list_or,
        map(parse_u32, OffsetType::Single),
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
pub(super) fn parse_data_operand(input: &str) -> Res<'_, SignalDataOperand> {
    let (input, _) = multispace0(input)?;
    let (input, name) = parse_identifier(input)?;

    let (input, extension) = opt((
        delimited(multispace0, tag(","), multispace0),
        opt(parse_identifier),
        delimited(multispace0, tag(","), multispace0),
        opt(parse_offset),
    ))
    .parse(input)?;

    let (source, offset) = match extension {
        Some((_, source_opt, _, offset_opt)) => (
            source_opt.unwrap_or("").to_string(),
            offset_opt.unwrap_or(OffsetType::Single(0)),
        ),
        None => ("".to_string(), OffsetType::Single(0)),
    };

    Ok((
        input,
        SignalDataOperand {
            name: name.to_string(),
            source,
            offset,
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
fn parse_param_operand(input: &str) -> Res<'_, ParamOperand> {
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
pub(super) fn parse_right_operand(input: &str) -> Res<'_, SignalRightOperand> {
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
pub(super) fn parse_op(input: &str) -> Res<'_, CompareOp> {
    alt((
        value(CompareOp::CGE, tag("x>=")),
        value(CompareOp::CLE, tag("x<=")),
        value(CompareOp::CEQ, tag("x==")),
        value(CompareOp::CNE, tag("x!=")),
        value(CompareOp::CGT, tag("x>")),
        value(CompareOp::CLT, tag("x<")),
        value(CompareOp::GE, tag(">=")),
        value(CompareOp::LE, tag("<=")),
        value(CompareOp::EQ, tag("==")),
        value(CompareOp::NE, tag("!=")),
        value(CompareOp::GT, tag(">")),
        value(CompareOp::LT, tag("<")),
    ))
    .parse(input)
}
