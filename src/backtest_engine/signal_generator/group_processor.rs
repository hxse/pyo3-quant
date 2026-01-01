use super::condition_evaluator::evaluate_parsed_condition;
use super::parser::parse_condition;
use crate::backtest_engine::utils::get_data_length;
use crate::types::IndicatorResults;
use crate::types::SignalParams;
use crate::types::LogicOp;
use crate::types::SignalGroup;
use crate::types::DataContainer;
use crate::error::QuantError;
use polars::prelude::*;
use std::ops::{BitAnd, BitOr};

/// 处理 SignalGroup，根据 LogicOp 组合多个 SignalCondition 的结果
pub fn process_signal_group(
    group: &SignalGroup,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<(BooleanChunked, BooleanChunked), QuantError> {
    let mut combined_result: Option<BooleanChunked> = None;
    let mut combined_mask: Option<BooleanChunked> = None;

    // 1. 处理 comparisons (字符串列表)
    for comparison_str in group.comparisons.iter() {
        // 解析字符串
        let condition = parse_condition(comparison_str)?;

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
