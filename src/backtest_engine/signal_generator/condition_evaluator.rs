use super::operand_resolver::{resolve_data_operand, resolve_right_operand, ResolvedOperand};
use super::types::{CompareOp, OffsetType, SignalCondition, SignalRightOperand};
use crate::data_conversion::types::backtest_summary::IndicatorResults;
use crate::data_conversion::types::param_set::SignalParams;
use crate::data_conversion::types::DataContainer;
use crate::error::{QuantError, SignalError};
use polars::prelude::*;
use std::ops::{BitAnd, BitOr, Not};

/// 执行比较操作的通用函数
fn perform_comparison(
    left: &Series,
    right: &ResolvedOperand,
    right_idx: usize, // Index for right series if it's a vector
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<BooleanChunked, QuantError> {
    // 1. 执行原始比较
    let raw_result = match right {
        ResolvedOperand::Series(series_vec) => {
            let right_series = if series_vec.len() == 1 {
                &series_vec[0]
            } else {
                &series_vec[right_idx]
            };
            compare_series(left, right_series)?
        }
        ResolvedOperand::Scalar(value) => compare_scalar(left, *value)?,
    };

    // 2. 计算左操作数的无效掩码 (NaN 或 Null)
    // is_nan() 返回 True(NaN), Null(Null), False(Valid)
    // is_null() 返回 True(Null), False(Others)
    // 组合: is_nan | is_null
    // Null | True -> True (Null case covered)
    // True | False -> True (NaN case covered)
    // False | False -> False (Valid case covered)
    // 结果是没有 Null 的纯 BooleanChunked
    let left_invalid = left.is_nan()?.bitor(left.is_null());

    // 3. 计算右操作数的无效掩码并合并
    let final_mask = match right {
        ResolvedOperand::Series(series_vec) => {
            let right_series = if series_vec.len() == 1 {
                &series_vec[0]
            } else {
                &series_vec[right_idx]
            };
            let right_invalid = right_series.is_nan()?.bitor(right_series.is_null());
            left_invalid.bitor(right_invalid)
        }
        ResolvedOperand::Scalar(value) => {
            if value.is_nan() {
                // 如果标量是 NaN，所有结果都无效
                // 返回全 True 的掩码 (或者直接返回全 False 的结果)
                // 这里我们构造一个全 True 的掩码来与 left_invalid 合并 (实际上 logical OR true = true)
                // 为简单起见，后续直接处理
                return Ok(raw_result.apply(|_| Some(false)));
            }
            // 标量有效，掩码仅取决于左侧
            left_invalid
        }
    };

    // 4. 过滤结果
    // result = raw_result & (!invalid)
    // 如果 raw_result 是 Null (因 Null 传播)，!invalid 是 False (因 invalid 是 True)，
    // Null & False -> False. 正确.
    Ok(raw_result.bitand(final_mask.not()))
}

/// 执行简单比较（非交叉）的工具函数
fn perform_simple_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<BooleanChunked, QuantError> {
    perform_comparison(
        left_s,
        right_resolved,
        right_idx,
        compare_series,
        compare_scalar,
    )
}

/// 执行交叉比较的工具函数
///
/// 交叉比较逻辑：当前值满足条件 AND 前一个值不满足条件
fn perform_crossover_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked> + Copy,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked> + Copy,
) -> Result<BooleanChunked, QuantError> {
    // 当前值的比较
    let current = perform_comparison(
        left_s,
        right_resolved,
        right_idx,
        compare_series,
        compare_scalar,
    )?;

    // 前一个值的准备
    let prev_left = left_s.shift(1);
    let prev_right_resolved = match right_resolved {
        ResolvedOperand::Series(v) => {
            let s = if v.len() == 1 { &v[0] } else { &v[right_idx] };
            ResolvedOperand::Series(vec![s.shift(1)])
        }
        ResolvedOperand::Scalar(val) => ResolvedOperand::Scalar(*val),
    };

    // 前一个值的比较
    let prev = perform_comparison(
        &prev_left,
        &prev_right_resolved,
        0, // right_idx is 0 because we constructed a vec of 1
        compare_series,
        compare_scalar,
    )?;

    // 返回：当前满足 AND 前值不满足
    Ok(current.bitand(prev.not()))
}

pub fn evaluate_parsed_condition(
    condition: &SignalCondition,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<Series, QuantError> {
    let left_series_vec = resolve_data_operand(&condition.left, processed_data, indicator_dfs)?;
    let right_resolved = resolve_right_operand(
        &condition.right,
        processed_data,
        indicator_dfs,
        signal_params,
    )?;

    // Check offset type consistency
    let left_offset_type = &condition.left.offset;

    // Treat Param and Scalar as Single(0) offset for logic determination
    let binding = OffsetType::Single(0);
    let right_offset_type = match &condition.right {
        SignalRightOperand::Data(d) => &d.offset,
        _ => &binding,
    };

    // Determine logic (AND vs OR) based on OffsetType
    // If both are ranges, they must match.
    // If one is range and other is single/scalar, use the range's logic.
    // If both single, it's single (trivial AND/OR).

    let (is_and, is_or) = match (left_offset_type, right_offset_type) {
        // ==================== AND Logic ====================
        // Left is AND (Range/List), Right is AND (Range/List) or Single
        (OffsetType::RangeAnd(_, _), OffsetType::RangeAnd(_, _))
        | (OffsetType::RangeAnd(_, _), OffsetType::ListAnd(_))
        | (OffsetType::RangeAnd(_, _), OffsetType::Single(_))
        | (OffsetType::ListAnd(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::ListAnd(_), OffsetType::ListAnd(_))
        | (OffsetType::ListAnd(_), OffsetType::Single(_)) => (true, false),

        // Left is Single, Right is AND (Range/List)
        (OffsetType::Single(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::Single(_), OffsetType::ListAnd(_)) => (true, false),

        // ==================== OR Logic ====================
        // Left is OR (Range/List), Right is OR (Range/List) or Single
        (OffsetType::RangeOr(_, _), OffsetType::RangeOr(_, _))
        | (OffsetType::RangeOr(_, _), OffsetType::ListOr(_))
        | (OffsetType::RangeOr(_, _), OffsetType::Single(_))
        | (OffsetType::ListOr(_), OffsetType::RangeOr(_, _))
        | (OffsetType::ListOr(_), OffsetType::ListOr(_))
        | (OffsetType::ListOr(_), OffsetType::Single(_)) => (false, true),

        // Left is Single, Right is OR (Range/List)
        (OffsetType::Single(_), OffsetType::RangeOr(_, _))
        | (OffsetType::Single(_), OffsetType::ListOr(_)) => (false, true),

        // ==================== Single Logic ====================
        // Both are Single -> Treat as AND (trivial)
        (OffsetType::Single(_), OffsetType::Single(_)) => (true, false),

        // ==================== Invalid Combinations ====================
        _ => {
            return Err(QuantError::Signal(SignalError::InvalidOffset(format!(
                "Invalid offset combination: {:?} and {:?}",
                left_offset_type, right_offset_type
            ))));
        }
    };

    // Check lengths
    let left_len = left_series_vec.len();
    let right_len = match &right_resolved {
        ResolvedOperand::Series(v) => v.len(),
        ResolvedOperand::Scalar(_) => 1,
    };

    // 使用 match 清晰地处理4种广播情况
    let comparison_pairs: Vec<(usize, usize)> = match (left_len, right_len) {
        // 情况1：左右都是1，直接比较
        (1, 1) => vec![(0, 0)],

        // 情况2：左边>1，右边是1，左边每个元素都与右边比较
        (l, 1) if l > 1 => (0..l).map(|i| (i, 0)).collect(),

        // 情况3：左边是1，右边>1，左边与右边每个元素比较
        (1, r) if r > 1 => (0..r).map(|i| (0, i)).collect(),

        // 情况4：左右长度相等且>1，逐对比较
        (l, r) if l == r && l > 1 => (0..l).map(|i| (i, i)).collect(),

        // 其他情况：长度不匹配，报错
        (l, r) => {
            return Err(QuantError::Signal(SignalError::InvalidOffset(format!(
                "操作数长度不匹配，无法进行广播。\n\
                 左操作数长度: {}\n\
                 右操作数长度: {}\n\
                 左操作数: {:?}\n\
                 右操作数: {:?}\n\
                 提示：广播规则为：(1,1), (n,1), (1,n), (n,n)，其中 n>1",
                l, r, condition.left, condition.right
            ))));
        }
    };

    let mut final_result: Option<BooleanChunked> = None;

    for (left_idx, right_idx) in comparison_pairs {
        let left_s = &left_series_vec[left_idx];

        let comparison_result = match condition.op {
            CompareOp::GT => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt(b),
                |a, v| a.gt(v),
            )?,
            CompareOp::LT => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt(b),
                |a, v| a.lt(v),
            )?,
            CompareOp::GE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
            CompareOp::LE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
            CompareOp::EQ => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.equal(b),
                |a, v| a.equal(v),
            )?,
            CompareOp::NE => perform_simple_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?,
            CompareOp::CGT => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt(b),
                |a, v| a.gt(v),
            )?,
            CompareOp::CLT => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt(b),
                |a, v| a.lt(v),
            )?,
            CompareOp::CGE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
            CompareOp::CLE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
            CompareOp::CEQ => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.equal(b),
                |a, v| a.equal(v),
            )?,
            CompareOp::CNE => perform_crossover_comparison(
                left_s,
                &right_resolved,
                right_idx,
                |a, b| a.not_equal(b),
                |a, v| a.not_equal(v),
            )?,
        };

        match final_result {
            None => final_result = Some(comparison_result),
            Some(ref mut res) => {
                if is_and {
                    *res = res.clone().bitand(comparison_result.clone());
                } else if is_or {
                    *res = res.clone().bitor(comparison_result.clone());
                }
            }
        }
    }

    let mut result_series = final_result
        .ok_or_else(|| {
            QuantError::Signal(SignalError::InvalidInput(
                "Empty comparison result".to_string(),
            ))
        })?
        .into_series()
        .fill_null(FillNullStrategy::Zero)?;

    if condition.negated {
        let bool_chunked = result_series
            .bool()
            .map_err(|_| {
                QuantError::Signal(SignalError::InvalidInput(
                    "Result is not boolean".to_string(),
                ))
            })?
            .clone();
        result_series = bool_chunked.not().into_series();
    }

    Ok(result_series)
}
