mod comparison_eval;

use super::operand_resolver::{resolve_data_operand, resolve_right_operand, ResolvedOperand};
use super::types::{CompareOp, OffsetType, SignalCondition, SignalRightOperand};
use crate::error::{QuantError, SignalError};
use crate::types::DataContainer;
use crate::types::IndicatorResults;
use crate::types::SignalParams;
use comparison_eval::{
    perform_crossover_comparison, perform_simple_comparison, perform_zone_cross,
};
use polars::prelude::*;
use std::ops::{BitAnd, BitOr, Not};

pub fn evaluate_parsed_condition(
    condition: &SignalCondition,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<(Series, BooleanChunked), QuantError> {
    let left_series_vec = resolve_data_operand(&condition.left, processed_data, indicator_dfs)?;
    let right_resolved = resolve_right_operand(
        &condition.right,
        processed_data,
        indicator_dfs,
        signal_params,
    )?;

    let left_offset_type = &condition.left.offset;

    let binding = OffsetType::Single(0);
    let right_offset_type = match &condition.right {
        SignalRightOperand::Data(d) => &d.offset,
        _ => &binding,
    };

    let (is_and, is_or) = match (left_offset_type, right_offset_type) {
        (OffsetType::RangeAnd(_, _), OffsetType::RangeAnd(_, _))
        | (OffsetType::RangeAnd(_, _), OffsetType::ListAnd(_))
        | (OffsetType::RangeAnd(_, _), OffsetType::Single(_))
        | (OffsetType::ListAnd(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::ListAnd(_), OffsetType::ListAnd(_))
        | (OffsetType::ListAnd(_), OffsetType::Single(_)) => (true, false),

        (OffsetType::Single(_), OffsetType::RangeAnd(_, _))
        | (OffsetType::Single(_), OffsetType::ListAnd(_)) => (true, false),

        (OffsetType::RangeOr(_, _), OffsetType::RangeOr(_, _))
        | (OffsetType::RangeOr(_, _), OffsetType::ListOr(_))
        | (OffsetType::RangeOr(_, _), OffsetType::Single(_))
        | (OffsetType::ListOr(_), OffsetType::RangeOr(_, _))
        | (OffsetType::ListOr(_), OffsetType::ListOr(_))
        | (OffsetType::ListOr(_), OffsetType::Single(_)) => (false, true),

        (OffsetType::Single(_), OffsetType::RangeOr(_, _))
        | (OffsetType::Single(_), OffsetType::ListOr(_)) => (false, true),

        (OffsetType::Single(_), OffsetType::Single(_)) => (true, false),

        _ => {
            return Err(QuantError::Signal(SignalError::InvalidOffset(format!(
                "Invalid offset combination: {:?} and {:?}",
                left_offset_type, right_offset_type
            ))));
        }
    };

    let left_len = left_series_vec.len();
    let right_len = match &right_resolved {
        ResolvedOperand::Series(v) => v.len(),
        ResolvedOperand::Scalar(_) => 1,
    };

    let comparison_pairs: Vec<(usize, usize)> = match (left_len, right_len) {
        (1, 1) => vec![(0, 0)],
        (l, 1) if l > 1 => (0..l).map(|i| (i, 0)).collect(),
        (1, r) if r > 1 => (0..r).map(|i| (0, i)).collect(),
        (l, r) if l == r && l > 1 => (0..l).map(|i| (i, i)).collect(),
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
    let mut final_mask: Option<BooleanChunked> = None;

    for (left_idx, right_idx) in comparison_pairs {
        let left_s = &left_series_vec[left_idx];

        let (comparison_result, mask_result) = match condition.op {
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

        match final_mask {
            None => final_mask = Some(mask_result),
            Some(ref mut m) => {
                *m = m.clone().bitor(mask_result);
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

    let mut mask = final_mask.ok_or_else(|| {
        QuantError::Signal(SignalError::InvalidInput("Empty mask result".to_string()))
    })?;

    if let Some(zone_end_operand) = &condition.zone_end {
        let end_resolved = resolve_right_operand(
            zone_end_operand,
            processed_data,
            indicator_dfs,
            signal_params,
        )?;

        if let ResolvedOperand::Series(end_series_vec) = &end_resolved {
            let end_s = &end_series_vec[0];
            let end_invalid = end_s.is_nan()?.bitor(end_s.is_null());
            mask = mask.bitor(end_invalid);
        }

        let cross_bool = result_series.bool()?.clone();
        let left_s = &left_series_vec[0];

        let zone_result = perform_zone_cross(
            &cross_bool,
            &mask,
            left_s,
            &right_resolved,
            &end_resolved,
            &condition.op,
        )?;

        result_series = zone_result.into_series();
    }

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

    Ok((result_series, mask))
}
