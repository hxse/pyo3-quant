// File: src/params.rs
//
// 该文件实现了单入口的配置处理管道：
// Python数据 (Py<PyDict>) -> 转换 (Rust 枚举) -> 计算/总结 -> 结果 (String) 返回给 Python。

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;
use pyo3::exceptions::PyKeyError;
use std::collections::HashMap;

/// ----------------------------------------------------------------------
/// 核心宏：自动提取字段，并检查 KeyError
/// ----------------------------------------------------------------------
// 宏用于精简参数提取的重复代码，并确保必需字段存在。
macro_rules! extract_params_from_dict {
    (
        $dict:expr,
        $name:expr,
        $struct_type:ident,
        $( $field:ident : $type:ty ),* ) => {{
        let result: PyResult<$struct_type> = (|| {
            // 循环处理每个字段
            $(
                let $field: $type = {
                    // 尝试从字典中获取字段
                    match $dict.get_item(stringify!($field))? {
                        // 如果字段缺失，抛出 PyKeyError
                        None => {
                            return Err(PyKeyError::new_err(
                                format!("配置 '{}' 缺失必需键 '{}'", $name, stringify!($field))
                            ));
                        }
                        // 如果存在，解包并尝试提取到目标类型
                        Some(bound_item) => bound_item.extract()?
                    }
                };
            )*

            // 返回构建好的结构体
            Ok($struct_type { $($field),* })
        })();

        result?
    }};
}
/// ----------------------------------------------------------------------

/// 1. 最内层的指标参数结构体
#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct SmaParams {
    pub period: u32,
    pub weight: f64,
}

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct EmaParams {
    pub period: u32,
    pub weight: f64,
}

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub struct BBandsParams {
    pub period: u32,
    pub std: f64,
    pub weight: f64,
}

#[allow(dead_code)]
#[derive(Clone, Debug)]
pub enum IndicatorParams {
    SMA(SmaParams),
    EMA(EmaParams),
    BBANDS(BBandsParams),
}

#[allow(dead_code)]
pub type AllStrategyConfigs = Vec<Vec<HashMap<String, Py<PyDict>>>>;

#[allow(dead_code)]
pub type ConvertedStrategyConfigs = Vec<Vec<HashMap<String, IndicatorParams>>>;

#[allow(dead_code)]
fn create_indicator_params<'py>(name: &str, dict: &'py Bound<'py, PyDict>) -> PyResult<IndicatorParams> {
    match () {
        _ if name.starts_with("sma_") => {
            let params = extract_params_from_dict!(
                dict, name, SmaParams,
                period: u32,
                weight: f64
            );
            Ok(IndicatorParams::SMA(params))
        }
        _ if name.starts_with("ema_") => {
            let params = extract_params_from_dict!(
                dict, name, EmaParams,
                period: u32,
                weight: f64
            );
            Ok(IndicatorParams::EMA(params))
        }
        _ if name.starts_with("bbands_") => {
            let params = extract_params_from_dict!(
                dict, name, BBandsParams,
                period: u32,
                std: f64,
                weight: f64
            );
            Ok(IndicatorParams::BBANDS(params))
        }
        _ => {
            Err(PyKeyError::new_err(format!(
                "配置类型未知，键名 '{}' 必须以 'sma_'、'ema_' 或 'bbands_' 开头", name
            )))
        }
    }
}

#[allow(dead_code)]
fn convert_configs_internal(py: Python, configs: AllStrategyConfigs) -> PyResult<ConvertedStrategyConfigs> {
    // 使用 collect 链式调用处理嵌套结构，并使用 ? 运算符处理 PyResult 错误
    let converted_configs: ConvertedStrategyConfigs = configs.into_iter()
        .map(|strategy_config| {
            strategy_config.into_iter()
                .map(|period_config| {
                    let converted_period_config: HashMap<String, IndicatorParams> = period_config.into_iter()
                        .map(|(name, params_dict)| {
                            // 将 Py<PyDict> 转换为 &PyDict，以便访问其内容
                            let dict = params_dict.bind(py);

                            let indicator = create_indicator_params(&name, &dict)?;

                            Ok((name, indicator))
                        })
                        .collect::<PyResult<HashMap<String, IndicatorParams>>>()?;

                    Ok(converted_period_config)
                })
                .collect::<PyResult<Vec<HashMap<String, IndicatorParams>>>>()
        })
        .collect::<PyResult<ConvertedStrategyConfigs>>()?;

    Ok(converted_configs)
}

#[allow(dead_code)]
fn calculate_metrics_internal(converted_configs: ConvertedStrategyConfigs) -> PyResult<String> {
    let total_configs = converted_configs.len();
    let mut total_periods = 0;
    let mut total_indicators = 0;
    let mut summary = String::new();

    for (i, strategy) in converted_configs.iter().enumerate() {
        total_periods += strategy.len();
        for (j, period_map) in strategy.iter().enumerate() {
            total_indicators += period_map.len();

            for (name, indicator) in period_map.iter() {
                match indicator {
                    IndicatorParams::SMA(sma_param) => {
                        summary.push_str(&format!(
                            "  Strategy {}: Period {}, {} (SMA): period={}, weight={}\n",
                            i + 1, j + 1, name, sma_param.period, sma_param.weight
                        ));
                    }
                    IndicatorParams::EMA(ema_param) => {
                        summary.push_str(&format!(
                            "  Strategy {}: Period {}, {} (EMA): period={}, weight={}\n",
                            i + 1, j + 1, name, ema_param.period, ema_param.weight
                        ));
                    }
                    IndicatorParams::BBANDS(bbands_param) => {
                        summary.push_str(&format!(
                            "  Strategy {}: Period {}, {} (BBANDS): period={}, std={}, weight={}\n",
                            i + 1, j + 1, name, bbands_param.period, bbands_param.std, bbands_param.weight
                        ));
                        // 示例计算: 利用纯 Rust 结构体进行数学计算
                        let upper_band_calc = bbands_param.weight + bbands_param.std * bbands_param.period as f64;
                        summary.push_str(&format!("    -> 上轨指数 (计算值): {:.2}\n", upper_band_calc));
                    }
                }
            }
        }
    }

    // 插入总结信息
    summary.insert_str(
        0,
        &format!(
            "Rust 成功执行单入口管道: {} 策略配置, {} 个时间周期, 共计 {} 个指标:\n",
            total_configs, total_periods, total_indicators
        ),
    );

    Ok(summary)
}

#[allow(dead_code)]
#[pyfunction]
pub fn process_all_configs(py: Python, configs: AllStrategyConfigs) -> PyResult<String> {
    // 1. 调用内部函数进行数据转换 (与 Python GIL 交互)
    let converted: Vec<Vec<HashMap<String, IndicatorParams>>> = convert_configs_internal(py, configs)?;

    // 2. 调用内部函数进行计算和总结 (纯 Rust 逻辑)
    calculate_metrics_internal(converted)
}
