//! 参数提取与设置模块
//!
//! 负责将嵌套的参数结构平铺为一维向量，并提供反向设置功能

use crate::types::{ParamType, SingleParamSet};

/// 平铺后的参数结构
#[derive(Clone)]
pub struct FlattenedParam {
    /// 参数类型索引: 0 = indicator, 1 = signal, 2 = backtest
    pub type_idx: u8,
    /// 分组标识
    pub group: String,
    /// 参数名称
    pub name: String,
    /// 完整参数结构
    pub param: crate::types::inputs::Param,
}

/// 量化参数值到指定精度
///
/// # 参数
/// * `val` - 原始值
/// * `step` - 步长精度
/// * `dtype` - 参数数据类型
///
/// # 返回
/// 量化后的值
pub fn quantize_value(val: f64, step: f64, dtype: ParamType) -> f64 {
    let raw_val = if step > 0.0 {
        (val / step).round() * step
    } else {
        val
    };

    match dtype {
        ParamType::Integer => raw_val.round(),
        ParamType::Boolean => {
            if raw_val >= 0.5 {
                1.0
            } else {
                0.0
            }
        }
        ParamType::Float => raw_val,
    }
}

/// 从参数集中提取所有需要优化的参数并平铺
///
/// # 参数
/// * `single_param` - 单个参数集
///
/// # 返回
/// 平铺后的参数列表
pub fn extract_optimizable_params(single_param: &SingleParamSet) -> Vec<FlattenedParam> {
    let mut flat_params = Vec::new();

    // 指标参数
    for (timeframe, groups) in &single_param.indicators {
        for (group_name, params) in groups {
            for (param_name, param) in params {
                if param.optimize {
                    flat_params.push(FlattenedParam {
                        type_idx: 0,
                        group: format!("{}:{}", timeframe, group_name),
                        name: param_name.clone(),
                        param: param.clone(),
                    });
                }
            }
        }
    }

    // 信号参数
    for (param_name, param) in &single_param.signal {
        if param.optimize {
            flat_params.push(FlattenedParam {
                type_idx: 1,
                group: String::new(),
                name: param_name.clone(),
                param: param.clone(),
            });
        }
    }

    // Backtest 参数
    // Backtest 参数
    for &name in crate::types::inputs::BacktestParams::OPTIMIZABLE_PARAMS {
        if let Some(param) = single_param.backtest.get_optimizable_param(name) {
            if param.optimize {
                flat_params.push(FlattenedParam {
                    type_idx: 2,
                    group: String::new(),
                    name: name.to_string(),
                    param: param.clone(),
                });
            }
        }
    }

    flat_params
}

/// 将采样值设置到参数结构中
///
/// # 参数
/// * `single_param` - 要修改的参数集
/// * `flat_param` - 平铺的参数定义
/// * `val` - 要设置的值
pub fn set_param_value(single_param: &mut SingleParamSet, flat_param: &FlattenedParam, val: f64) {
    let final_val = quantize_value(val, flat_param.param.step, flat_param.param.dtype);

    match flat_param.type_idx {
        0 => {
            // Indicator
            let parts: Vec<&str> = flat_param.group.split(':').collect();
            if parts.len() == 2 {
                if let Some(groups) = single_param.indicators.get_mut(parts[0]) {
                    if let Some(params) = groups.get_mut(parts[1]) {
                        if let Some(param) = params.get_mut(&flat_param.name) {
                            param.value = final_val;
                        }
                    }
                }
            }
        }
        1 => {
            // Signal
            if let Some(param) = single_param.signal.get_mut(&flat_param.name) {
                param.value = final_val;
            }
        }
        2 => {
            // Backtest
            if let Some(param) = single_param
                .backtest
                .get_optimizable_param_mut(&flat_param.name)
            {
                param.value = final_val;
            }
        }
        _ => {}
    }
}

/// 批量应用采样值到参数结构
///
/// # 参数
/// * `single_param` - 要修改的参数集
/// * `flat_params` - 平铺的参数定义列表
/// * `values` - 对应的采样值列表
pub fn apply_values_to_param(
    single_param: &mut SingleParamSet,
    flat_params: &[FlattenedParam],
    values: &[f64],
) {
    for (dim, &val) in values.iter().enumerate() {
        set_param_value(single_param, &flat_params[dim], val);
    }
}
