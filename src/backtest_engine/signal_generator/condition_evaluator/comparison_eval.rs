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

/// 区间穿越：矢量化预计算比较结果 + 迭代器状态机
///
/// Phase 1: 用 perform_comparison 矢量化计算 out_of_zone（SIMD 优化）
/// Phase 2: 迭代器扫描 cross + out_of_zone 的 bool 结果，维护 active 状态
pub(super) fn perform_zone_cross(
    cross_result: &BooleanChunked,
    cross_mask: &BooleanChunked,
    left_s: &Series,
    right_resolved: &ResolvedOperand,
    end_resolved: &ResolvedOperand,
    op: &CompareOp,
) -> Result<BooleanChunked, QuantError> {
    let len = left_s.len();

    let ((ooz_end, end_mask), (ooz_activate, activate_mask)) = match op {
        CompareOp::CGT => (
            perform_comparison(
                left_s,
                end_resolved,
                0,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
            perform_comparison(
                left_s,
                right_resolved,
                0,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
        ),
        CompareOp::CGE => (
            perform_comparison(left_s, end_resolved, 0, |a, b| a.gt(b), |a, v| a.gt(v))?,
            perform_comparison(left_s, right_resolved, 0, |a, b| a.lt(b), |a, v| a.lt(v))?,
        ),
        CompareOp::CLT => (
            perform_comparison(
                left_s,
                end_resolved,
                0,
                |a, b| a.lt_eq(b),
                |a, v| a.lt_eq(v),
            )?,
            perform_comparison(
                left_s,
                right_resolved,
                0,
                |a, b| a.gt_eq(b),
                |a, v| a.gt_eq(v),
            )?,
        ),
        CompareOp::CLE => (
            perform_comparison(left_s, end_resolved, 0, |a, b| a.lt(b), |a, v| a.lt(v))?,
            perform_comparison(left_s, right_resolved, 0, |a, b| a.gt(b), |a, v| a.gt(v))?,
        ),
        _ => {
            return Err(QuantError::Signal(SignalError::InvalidInput(format!(
                "zone_cross 仅支持交叉运算符(x>, x<, x>=, x<=)，当前运算符: {:?}",
                op
            ))));
        }
    };

    let out_of_zone = ooz_end.bitor(ooz_activate);
    let combined_invalid = cross_mask.bitor(&end_mask).bitor(activate_mask);

    let mut result = Vec::with_capacity(len);
    let mut active = false;

    let cross_iter = cross_result.iter();
    let ooz_iter = out_of_zone.into_iter();
    let invalid_iter = combined_invalid.into_iter();

    for (c, (o, inv)) in cross_iter.zip(ooz_iter.zip(invalid_iter)) {
        let is_invalid = inv.unwrap_or(true);
        if is_invalid {
            active = false;
            result.push(false);
            continue;
        }

        let is_cross = c.unwrap_or(false);
        let is_ooz = o.unwrap_or(true);

        if is_cross && !is_ooz {
            active = true;
        } else if is_ooz {
            active = false;
        }

        result.push(active);
    }

    Ok(BooleanChunked::from_slice(
        PlSmallStr::from_static("zone_cross"),
        &result,
    ))
}
