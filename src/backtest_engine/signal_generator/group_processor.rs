use super::condition_evaluator::evaluate_parsed_condition;
use super::parser::parse_condition;
use super::types::{CompareOp, SignalCondition, SignalRightOperand};
use crate::backtest_engine::utils::get_data_length;
use crate::error::QuantError;
use crate::types::DataPack;
use crate::types::IndicatorResults;
use crate::types::LogicOp;
use crate::types::SignalGroup;
use crate::types::SignalParams;
use polars::prelude::*;
use std::ops::{BitAnd, BitOr};

fn is_cross_operator(op: &CompareOp) -> bool {
    matches!(
        op,
        CompareOp::XGT
            | CompareOp::XLT
            | CompareOp::XGE
            | CompareOp::XLE
            | CompareOp::XEQ
            | CompareOp::XNE
            | CompareOp::XIN
    )
}

fn validate_cross_operator_sources(
    condition: &SignalCondition,
    base_data_key: &str,
    raw_condition: &str,
) -> Result<(), QuantError> {
    if !is_cross_operator(&condition.op) {
        return Ok(());
    }

    let left_source = if condition.left.source.is_empty() {
        base_data_key
    } else {
        condition.left.source.as_str()
    };

    if left_source != base_data_key {
        return Err(crate::error::SignalError::InvalidInput(format!(
            "交叉类运算符(x>, x<, x>=, x<=, x==, x!=, xin) 仅允许用于 base_data_key。\n条件: '{}'\nbase_data_key: '{}'\nleft source: '{}'",
            raw_condition, base_data_key, left_source
        ))
        .into());
    }

    if let SignalRightOperand::Data(right_data) = &condition.right {
        let right_source = if right_data.source.is_empty() {
            base_data_key
        } else {
            right_data.source.as_str()
        };

        if right_source != base_data_key {
            return Err(crate::error::SignalError::InvalidInput(format!(
                "交叉类运算符的数据右操作数也必须使用 base_data_key。\n条件: '{}'\nbase_data_key: '{}'\nright source: '{}'",
                raw_condition, base_data_key, right_source
            ))
            .into());
        }
    }

    if let Some(SignalRightOperand::Data(zone_end_data)) = &condition.zone_end {
        let zone_end_source = if zone_end_data.source.is_empty() {
            base_data_key
        } else {
            zone_end_data.source.as_str()
        };

        if zone_end_source != base_data_key {
            return Err(crate::error::SignalError::InvalidInput(format!(
                "交叉类运算符的区间终止边界也必须使用 base_data_key。\n条件: '{}'\nbase_data_key: '{}'\nzone_end source: '{}'",
                raw_condition, base_data_key, zone_end_source
            ))
            .into());
        }
    }

    Ok(())
}

/// 处理 SignalGroup，根据 LogicOp 组合多个 SignalCondition 的结果
pub fn process_signal_group(
    group: &SignalGroup,
    processed_data: &DataPack,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    let mut combined_result: Option<BooleanChunked> = None;
    let mut combined_mask: Option<BooleanChunked> = None;

    // 1. 处理 comparisons (字符串列表)
    for comparison_str in group.comparisons.iter() {
        // 解析字符串
        let condition = parse_condition(comparison_str)?;
        validate_cross_operator_sources(&condition, &processed_data.base_data_key, comparison_str)?;

        // 评估条件
        let (result_series, mask_bool) =
            evaluate_parsed_condition(&condition, processed_data, indicator_dfs, signal_params)?;

        let result_bool = result_series.bool()?.clone();

        match combined_result {
            None => combined_result = Some(result_bool),
            Some(current) => {
                let new_combined = match group.logic {
                    LogicOp::AND => current.bitand(result_bool),
                    LogicOp::OR => current.bitor(result_bool),
                };

                combined_result = Some(new_combined);
            }
        }

        match combined_mask {
            None => combined_mask = Some(mask_bool),
            Some(current) => {
                combined_mask = Some(current.bitor(mask_bool));
            }
        }
    }

    // 2. 递归处理 sub_groups
    for sub_group in &group.sub_groups {
        let (sub_result, sub_mask) =
            process_signal_group(sub_group, processed_data, indicator_dfs, signal_params)?;

        match combined_result {
            None => combined_result = Some(sub_result),
            Some(current) => match group.logic {
                LogicOp::AND => combined_result = Some(current.bitand(sub_result)),
                LogicOp::OR => combined_result = Some(current.bitor(sub_result)),
            },
        }

        match combined_mask {
            None => combined_mask = Some(sub_mask),
            Some(current) => {
                combined_mask = Some(current.bitor(sub_mask));
            }
        }
    }

    // 如果没有任何条件，返回全 false (或者根据业务逻辑决定)
    // 这里假设空组不产生信号，或者应该报错?
    // 既然是 Option, 如果是 None, 我们返回全 False 的 Series?
    // 或者返回 Error?
    // 为安全起见，如果 combined_result 为 None，创建一个全 False 的 ChunkedArray
    let len = get_data_length(processed_data, "process_signal_group")?;
    let res = combined_result
        .unwrap_or_else(|| BooleanChunked::full(PlSmallStr::from_static("result"), false, len));
    let mask = combined_mask
        .unwrap_or_else(|| BooleanChunked::full(PlSmallStr::from_static("mask"), false, len));

    Ok((res, mask))
}
