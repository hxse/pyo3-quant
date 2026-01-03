//! 参数提取与设置模块
//!
//! 负责将嵌套的参数结构平铺为一维向量，并提供反向设置功能

use crate::types::{ParamType, SingleParamSet};

/// 平铺后的参数结构
#[derive(Clone)]
pub struct FlattenedParam {
    /// 参数类型索引: 0 = indicator, 1 = signal, 2 = backtest
    pub type_idx: u8,
    /// 分组标识（对于 indicator 为 "timeframe:group_name"）
    pub group: String,
    /// 参数名称
    pub name: String,
    /// 参数最小值
    pub min: f64,
    /// 参数最大值
    pub max: f64,
    /// 是否使用对数尺度
    pub log_scale: bool,
    /// 参数数据类型
    pub dtype: ParamType,
    /// 最小精度步长
    pub step: f64,
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
                        min: if param.min == 0.0 && param.initial_min != 0.0 {
                            param.initial_min
                        } else {
                            param.min
                        },
                        max: if param.max == 0.0 && param.initial_max != 0.0 {
                            param.initial_max
                        } else {
                            param.max
                        },
                        log_scale: param.log_scale,
                        dtype: param.dtype,
                        step: param.step,
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
                min: if param.min == 0.0 && param.initial_min != 0.0 {
                    param.initial_min
                } else {
                    param.min
                },
                max: if param.max == 0.0 && param.initial_max != 0.0 {
                    param.initial_max
                } else {
                    param.max
                },
                log_scale: param.log_scale,
                dtype: param.dtype,
                step: param.step,
            });
        }
    }

    // Backtest 参数
    macro_rules! push_backtest_param {
        ($field:ident, $name:expr) => {
            if let Some(p) = &single_param.backtest.$field {
                if p.optimize {
                    flat_params.push(FlattenedParam {
                        type_idx: 2,
                        group: String::new(),
                        name: $name.into(),
                        min: if p.min == 0.0 && p.initial_min != 0.0 {
                            p.initial_min
                        } else {
                            p.min
                        },
                        max: if p.max == 0.0 && p.initial_max != 0.0 {
                            p.initial_max
                        } else {
                            p.max
                        },
                        log_scale: p.log_scale,
                        dtype: p.dtype,
                        step: p.step,
                    });
                }
            }
        };
    }

    push_backtest_param!(sl_pct, "sl_pct");
    push_backtest_param!(tp_pct, "tp_pct");
    push_backtest_param!(tsl_pct, "tsl_pct");
    push_backtest_param!(sl_atr, "sl_atr");
    push_backtest_param!(tp_atr, "tp_atr");
    push_backtest_param!(tsl_atr, "tsl_atr");
    push_backtest_param!(atr_period, "atr_period");
    push_backtest_param!(tsl_psar_af0, "tsl_psar_af0");
    push_backtest_param!(tsl_psar_af_step, "tsl_psar_af_step");
    push_backtest_param!(tsl_psar_max_af, "tsl_psar_max_af");

    flat_params
}

/// 将采样值设置到参数结构中
///
/// # 参数
/// * `single_param` - 要修改的参数集
/// * `flat_param` - 平铺的参数定义
/// * `val` - 要设置的值
pub fn set_param_value(single_param: &mut SingleParamSet, flat_param: &FlattenedParam, val: f64) {
    let final_val = quantize_value(val, flat_param.step, flat_param.dtype);

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
            match flat_param.name.as_str() {
                "sl_pct" => {
                    if let Some(p) = single_param.backtest.sl_pct.as_mut() {
                        p.value = final_val;
                    }
                }
                "tp_pct" => {
                    if let Some(p) = single_param.backtest.tp_pct.as_mut() {
                        p.value = final_val;
                    }
                }
                "tsl_pct" => {
                    if let Some(p) = single_param.backtest.tsl_pct.as_mut() {
                        p.value = final_val;
                    }
                }
                "sl_atr" => {
                    if let Some(p) = single_param.backtest.sl_atr.as_mut() {
                        p.value = final_val;
                    }
                }
                "tp_atr" => {
                    if let Some(p) = single_param.backtest.tp_atr.as_mut() {
                        p.value = final_val;
                    }
                }
                "tsl_atr" => {
                    if let Some(p) = single_param.backtest.tsl_atr.as_mut() {
                        p.value = final_val;
                    }
                }
                "atr_period" => {
                    if let Some(p) = single_param.backtest.atr_period.as_mut() {
                        p.value = final_val;
                    }
                }
                "tsl_psar_af0" => {
                    if let Some(p) = single_param.backtest.tsl_psar_af0.as_mut() {
                        p.value = final_val;
                    }
                }
                "tsl_psar_af_step" => {
                    if let Some(p) = single_param.backtest.tsl_psar_af_step.as_mut() {
                        p.value = final_val;
                    }
                }
                "tsl_psar_max_af" => {
                    if let Some(p) = single_param.backtest.tsl_psar_max_af.as_mut() {
                        p.value = final_val;
                    }
                }
                _ => {}
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
