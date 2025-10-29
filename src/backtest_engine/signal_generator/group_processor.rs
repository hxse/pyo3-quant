use super::condition_evaluator::evaluate_condition;
use crate::data_conversion::input::param_set::SignalParams;
use crate::data_conversion::input::template::{LogicOp, SignalGroup};
use crate::data_conversion::input::DataContainer;
use crate::error::QuantError;
use polars::prelude::*;
use std::collections::HashMap;

/// 处理 SignalGroup，根据 LogicOp 组合多个 SignalCondition 的结果
pub fn process_signal_group(
    group: &SignalGroup,
    processed_data: &DataContainer,
    indicator_dfs: &HashMap<String, Vec<DataFrame>>,
    signal_params: &SignalParams,
) -> Result<Series, QuantError> {
    let mut aggregated_result: Option<Series> = None;
    let data_len = processed_data.mapping.height(); // 从 processed_data.mapping 获取数据长度

    for condition in &group.conditions {
        let condition_result =
            evaluate_condition(condition, processed_data, indicator_dfs, signal_params)?;

        if let Some(agg_series) = aggregated_result {
            aggregated_result = Some(match group.logic {
                LogicOp::AND => (&agg_series & &condition_result)?,
                LogicOp::OR => (&agg_series | &condition_result)?,
            });
        } else {
            aggregated_result = Some(condition_result);
        }
    }

    Ok(aggregated_result.unwrap_or_else(|| {
        BooleanChunked::full(PlSmallStr::from(""), false, data_len).into_series()
    }))
}
