use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::param_extractor::{apply_values_to_param, FlattenedParam};
use crate::error::QuantError;
use crate::types::{DataContainer, SettingContainer, SingleParamSet, TemplateContainer};
use std::collections::HashMap;

/// 使用指定参数运行单次回测（用于测试集评估）
pub fn run_single_backtest(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    values: &[f64],
    flat_params: &[FlattenedParam],
) -> Result<HashMap<String, f64>, QuantError> {
    // 1. 复制参数并应用优化值
    let mut eval_param = param.clone();
    apply_values_to_param(&mut eval_param, flat_params, values);

    // 2. 直接调用回测引擎
    let result = execute_single_backtest(data_dict, &eval_param, template, settings)?;

    // 3. 返回性能指标
    Ok(result.performance.unwrap_or_default())
}
