use crate::backtest_engine::evaluate_param_set;
use crate::backtest_engine::optimizer::param_extractor::{apply_values_to_param, FlattenedParam};
use crate::error::QuantError;
use crate::types::{DataPack, SingleParamSet, TemplateContainer};
use std::collections::HashMap;

/// 使用指定参数运行单次绩效评估（用于测试集评估）
pub fn evaluate_param_values(
    data_pack: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
    values: &[f64],
    flat_params: &[FlattenedParam],
) -> Result<HashMap<String, f64>, QuantError> {
    // 1. 复制参数并应用优化值
    let mut eval_param = param.clone();
    apply_values_to_param(&mut eval_param, flat_params, values);

    // 中文注释：优化器评估路径固定收口为 performance-only 评估，不再依赖公开 SettingContainer。
    evaluate_param_set(data_pack, &eval_param, template)
}
