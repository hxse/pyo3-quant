use crate::backtest_engine::optimizer::param_extractor::extract_optimizable_params;
use crate::backtest_engine::optimizer::{run_optimization, run_single_backtest};
use crate::backtest_engine::walk_forward::data_splitter::generate_windows;
use crate::error::{OptimizerError, QuantError};
use crate::types::WalkForwardConfig;
use crate::types::{DataContainer, SettingContainer, SingleParamSet, TemplateContainer};
use crate::types::{WalkForwardResult, WindowResult};
use pyo3::prelude::*;
use std::collections::HashMap;

/// 运行向前滚动优化
pub fn run_walk_forward(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError> {
    // 1. 获取总数据长度
    // 获取第一个 DataFrame 的长度作为 total_bars
    let total_bars = if let Some(first_df) = data_dict.source.values().next() {
        first_df.height()
    } else {
        return Err(OptimizerError::NoData.into());
    };

    // 2. 生成窗口
    let windows = generate_windows(total_bars, config)?;

    let mut window_results = Vec::new();
    let mut prev_top_k: Option<Vec<Vec<f64>>> = None;

    // 3. 遍历窗口
    for window in windows {
        // 3.1 准备切片数据
        let train_len = window.train_range.1 - window.train_range.0;
        let train_data = slice_data_container(data_dict, window.train_range.0, train_len);

        // 3.2 配置优化器
        let mut opt_config = config.optimizer_config.clone();

        // 继承权重
        if config.inherit_prior {
            if let Some(ref priors) = prev_top_k {
                if !priors.is_empty() {
                    opt_config.init_samples = Some(priors.clone());
                    // 可以适当调大 explore_ratio 以防止陷入局部
                }
            }
        }

        // 3.3 运行训练集优化
        // 使用 slice 后的 train_data
        let train_result = run_optimization(&train_data, param, template, settings, &opt_config)?;

        // 3.4 准备测试集回测
        let test_len = window.test_range.1 - window.test_range.0;
        let test_data = slice_data_container(data_dict, window.test_range.0, test_len);

        let test_metrics;

        if let Some(best_sample) = train_result.top_k_samples.first() {
            // Extract flat params structure
            let flat_params = extract_optimizable_params(param);

            // Run direct backtest on test data
            test_metrics = run_single_backtest(
                &test_data,
                param,
                template,
                settings,
                &best_sample.values,
                &flat_params,
            )?;
        } else {
            // 训练失败
            test_metrics = HashMap::new();
        }

        // 3.5 记录结果
        window_results.push(WindowResult {
            window_id: window.id,
            train_range: window.train_range,
            test_range: window.test_range,
            best_params: train_result.best_params, // 记录训练得出的最佳参数
            optimize_metric: config.optimizer_config.optimize_metric.as_str().to_string(),
            train_metrics: train_result.metrics,
            test_metrics,
            history: Some(train_result.history), // 保存优化历史
        });

        // 3.6 更新 Prior (Top K)
        let current_top_k: Vec<Vec<f64>> = train_result
            .top_k_samples
            .iter()
            .map(|s| s.values.clone())
            .collect();

        prev_top_k = Some(current_top_k);

        println!("Window {} Finished.", window.id);
    }

    // 4. 汇总

    // 汇总聚合指标（计算每个key的平均值）
    let mut aggregate_test_metrics = HashMap::new();
    if !window_results.is_empty() {
        // 先收集所有可能的 keys (通常每个window的metrics keys 是一样的，取第一个即可)
        if let Some(first) = window_results.first() {
            let keys: Vec<String> = first.test_metrics.keys().cloned().collect();
            for key in keys {
                let sum: f64 = window_results
                    .iter()
                    .map(|w| w.test_metrics.get(&key).cloned().unwrap_or(0.0))
                    .sum();
                let avg = sum / window_results.len() as f64;
                aggregate_test_metrics.insert(key, avg);
            }
        }
    }

    Ok(WalkForwardResult {
        windows: window_results,
        optimize_metric: config.optimizer_config.optimize_metric.as_str().to_string(),
        aggregate_test_metrics,
    })
}

fn slice_data_container(data: &DataContainer, start: usize, len: usize) -> DataContainer {
    // Slice Source
    let sliced_source: std::collections::HashMap<_, _> = data
        .source
        .iter()
        .map(|(k, df)| (k.clone(), df.slice(start as i64, len)))
        .collect();

    // Slice Mapping
    // mapping 也是 DataFrame
    let sliced_mapping = data.mapping.slice(start as i64, len);

    // Slice Skip Mask
    let sliced_skip_mask = data
        .skip_mask
        .as_ref()
        .map(|df| df.slice(start as i64, len));

    DataContainer {
        source: sliced_source,
        mapping: sliced_mapping,
        skip_mask: sliced_skip_mask,
        skip_mapping: data.skip_mapping.clone(),
        base_data_key: data.base_data_key.clone(),
    }
}

use pyo3_stub_gen::derive::*;

/// Python 接口
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.walk_forward",
    python = r#"
import pyo3_quant

def run_walk_forward(
    data_dict: pyo3_quant.DataContainer,
    param: pyo3_quant.SingleParamSet,
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
    walk_forward_config: pyo3_quant.WalkForwardConfig,
) -> pyo3_quant.WalkForwardResult:
    """运行滚动前推测试"""
"#
)]
#[pyfunction(name = "run_walk_forward")]
pub fn py_run_walk_forward(
    data_dict: DataContainer,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    config: WalkForwardConfig,
) -> PyResult<WalkForwardResult> {
    run_walk_forward(&data_dict, &param, &template, &engine_settings, &config).map_err(|e| e.into())
}
