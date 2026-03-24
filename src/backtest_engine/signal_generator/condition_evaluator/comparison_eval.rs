use super::super::operand_resolver::ResolvedOperand;
use super::super::types::CompareOp;
use crate::error::{QuantError, SignalError};
use polars::prelude::*;
use std::ops::{BitAnd, BitOr, Not};

/// 执行比较操作的通用函数
pub(super) fn perform_comparison(
    left: &Series,
    right: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
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

    let left_invalid = left.is_nan()?.bitor(left.is_null());

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
                let mask =
                    BooleanChunked::full(left_invalid.name().clone(), true, left_invalid.len());
                return Ok((raw_result.apply(|_| Some(false)), mask));
            }
            left_invalid
        }
    };

    Ok((raw_result.bitand(final_mask.clone().not()), final_mask))
}

/// 执行简单比较（非交叉）的工具函数
pub(super) fn perform_simple_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked>,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked>,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
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
pub(super) fn perform_crossover_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    compare_series: impl Fn(&Series, &Series) -> PolarsResult<BooleanChunked> + Copy,
    compare_scalar: impl Fn(&Series, f64) -> PolarsResult<BooleanChunked> + Copy,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    let (current, current_mask) = perform_comparison(
        left_s,
        right_resolved,
        right_idx,
        compare_series,
        compare_scalar,
    )?;

    let prev_left = left_s.shift(1);
    let prev_right_resolved = match right_resolved {
        ResolvedOperand::Series(v) => {
            let s = if v.len() == 1 { &v[0] } else { &v[right_idx] };
            ResolvedOperand::Series(vec![s.shift(1)])
        }
        ResolvedOperand::Scalar(val) => ResolvedOperand::Scalar(*val),
    };

    let (prev, prev_mask) = perform_comparison(
        &prev_left,
        &prev_right_resolved,
        0,
        compare_series,
        compare_scalar,
    )?;

    let prev_valid_and_not_satisfied = prev.not().bitand(prev_mask.clone().not());
    let cross_result = current.bitand(prev_valid_and_not_satisfied);

    Ok((cross_result, current_mask.bitor(prev_mask)))
}

/// 区间比较：按 bar 执行闭区间判断 / 进入区间判断 / 区间状态机
///
/// 中文说明：
/// - `in A..B` 表示当前值位于 `[low, high]`
/// - `xin A..B` 表示前一根不在 `[low, high]`，当前进入 `[low, high]`
/// - `x> A..B` 表示从区间下方进入 `[low, high]`
/// - `x< A..B` 表示从区间上方进入 `[low, high]`
/// - `A..B` 会先自动归一化成 `low=min(A,B)`、`high=max(A,B)`
/// - `x>` / `x<` 进入后只要仍在闭区间内就保持激活，跑出区间外才失效
pub(super) fn perform_range_comparison(
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    right_idx: usize,
    end_resolved: &ResolvedOperand,
    end_idx: usize,
    op: &CompareOp,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    /// 中文注释：统一把 Series 视为 f64 序列，便于逐 bar 做区间状态机。
    fn cast_series_to_f64(series: &Series) -> Result<Float64Chunked, QuantError> {
        series
            .cast(&DataType::Float64)
            .map_err(|e| {
                QuantError::Signal(SignalError::InvalidInput(format!(
                    "range_comparison 无法将序列转换为 Float64: {}",
                    e
                )))
            })?
            .f64()
            .map_err(|e| {
                QuantError::Signal(SignalError::InvalidInput(format!(
                    "range_comparison 无法读取 Float64 序列: {}",
                    e
                )))
            })
            .cloned()
    }

    #[derive(Clone)]
    enum OperandView {
        Series(Float64Chunked),
        Scalar(f64),
    }

    impl OperandView {
        fn current(&self, idx: usize) -> Option<f64> {
            match self {
                Self::Series(series) => series.get(idx),
                Self::Scalar(value) => Some(*value),
            }
        }

        fn previous(&self, idx: usize) -> Option<f64> {
            match self {
                Self::Series(series) => {
                    idx.checked_sub(1).and_then(|prev_idx| series.get(prev_idx))
                }
                Self::Scalar(value) => Some(*value),
            }
        }
    }

    fn build_operand_view(
        operand: &ResolvedOperand,
        operand_idx: usize,
    ) -> Result<OperandView, QuantError> {
        match operand {
            ResolvedOperand::Series(series_vec) => {
                let selected = if series_vec.len() == 1 {
                    &series_vec[0]
                } else {
                    &series_vec[operand_idx]
                };
                Ok(OperandView::Series(cast_series_to_f64(selected)?))
            }
            ResolvedOperand::Scalar(value) => Ok(OperandView::Scalar(*value)),
        }
    }

    fn is_invalid(value: Option<f64>) -> bool {
        value.is_none_or(f64::is_nan)
    }

    let len = left_s.len();
    let left_view = OperandView::Series(cast_series_to_f64(left_s)?);
    let right_view = build_operand_view(right_resolved, right_idx)?;
    let end_view = build_operand_view(end_resolved, end_idx)?;

    let mut result = Vec::with_capacity(len);
    let mut mask = Vec::with_capacity(len);
    let mut active = false;

    for idx in 0..len {
        let curr_left = left_view.current(idx);
        let curr_right = right_view.current(idx);
        let curr_end = end_view.current(idx);
        let prev_left = left_view.previous(idx);
        let prev_right = right_view.previous(idx);
        let prev_end = end_view.previous(idx);

        let current_invalid =
            is_invalid(curr_left) || is_invalid(curr_right) || is_invalid(curr_end);
        let previous_invalid =
            is_invalid(prev_left) || is_invalid(prev_right) || is_invalid(prev_end);

        let requires_prev = matches!(op, CompareOp::XIN | CompareOp::XGT | CompareOp::XLT);

        if current_invalid || (requires_prev && previous_invalid) {
            active = false;
            result.push(false);
            mask.push(true);
            continue;
        }

        let curr_left = curr_left.unwrap();
        let curr_right = curr_right.unwrap();
        let curr_end = curr_end.unwrap();
        let curr_low = curr_right.min(curr_end);
        let curr_high = curr_right.max(curr_end);
        let is_in_zone = curr_low <= curr_left && curr_left <= curr_high;

        match op {
            CompareOp::IN => {
                result.push(is_in_zone);
                mask.push(false);
                continue;
            }
            CompareOp::XIN => {
                let prev_left = prev_left.unwrap();
                let prev_right = prev_right.unwrap();
                let prev_end = prev_end.unwrap();
                let prev_low = prev_right.min(prev_end);
                let prev_high = prev_right.max(prev_end);
                let was_in_zone = prev_low <= prev_left && prev_left <= prev_high;
                result.push(!was_in_zone && is_in_zone);
                mask.push(false);
                continue;
            }
            CompareOp::XGT => {
                let prev_left = prev_left.unwrap();
                let prev_right = prev_right.unwrap();
                let prev_end = prev_end.unwrap();
                let prev_low = prev_right.min(prev_end);
                if prev_left < prev_low && is_in_zone {
                    active = true;
                } else if !is_in_zone {
                    active = false;
                }
            }
            CompareOp::XLT => {
                let prev_left = prev_left.unwrap();
                let prev_right = prev_right.unwrap();
                let prev_end = prev_end.unwrap();
                let prev_high = prev_right.max(prev_end);
                if prev_left > prev_high && is_in_zone {
                    active = true;
                } else if !is_in_zone {
                    active = false;
                }
            }
            _ => {
                return Err(QuantError::Signal(SignalError::InvalidInput(format!(
                    "区间比较仅支持 in、xin、x>、x<，当前运算符: {:?}",
                    op
                ))));
            }
        }

        result.push(active);
        mask.push(false);
    }

    Ok((
        BooleanChunked::from_slice(PlSmallStr::from_static("range_comparison"), &result),
        BooleanChunked::from_slice(PlSmallStr::from_static("range_comparison_mask"), &mask),
    ))
}
