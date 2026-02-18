use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::param_extractor::{
    apply_values_to_param, extract_optimizable_params, quantize_value,
};
use crate::backtest_engine::utils;
use crate::error::QuantError;
use crate::types::{
    DataContainer, SensitivityConfig, SensitivityResult, SensitivitySample, SettingContainer,
    SingleParamSet, TemplateContainer,
};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rand::rngs::StdRng;
use rand::Rng;
use rand::SeedableRng;
use rand_distr::{Distribution, Normal};
use rayon::prelude::*;
use std::collections::HashMap;

fn quantile_from_sorted(sorted_values: &[f64], q: f64) -> f64 {
    if sorted_values.is_empty() {
        return 0.0;
    }
    let clamped_q = q.clamp(0.0, 1.0);
    let idx = ((sorted_values.len() - 1) as f64 * clamped_q).round() as usize;
    sorted_values[idx]
}

/// 生成抖动采样点
fn generate_jitter_samples(
    original_values: &[f64],
    flat_params: &[crate::backtest_engine::optimizer::param_extractor::FlattenedParam],
    config: &SensitivityConfig,
    rng: &mut StdRng,
) -> Vec<Vec<f64>> {
    let mut samples = Vec::with_capacity(config.n_samples);

    for _ in 0..config.n_samples {
        let mut sample_row = Vec::with_capacity(original_values.len());

        for (i, &val) in original_values.iter().enumerate() {
            let param = &flat_params[i].param;
            let ratio = config.jitter_ratio;

            // 计算扰动后的原始值 (未量化)
            let raw_perturbed = if ratio > 0.0 {
                if config.distribution == "normal" {
                    let normal =
                        Normal::new(0.0, ratio).unwrap_or_else(|_| Normal::new(0.0, 1e-6).unwrap());
                    val * (1.0 + normal.sample(rng))
                } else {
                    // 均匀分布: val * [1-ratio, 1+ratio]
                    let noise = rng.random_range(-ratio..ratio);
                    val * (1.0 + noise)
                }
            } else {
                val
            };

            // 约束在 min/max 范围内
            let clamped = raw_perturbed.clamp(param.min, param.max);

            // 量化 (尊重 step 和 dtype)
            let quantized = quantize_value(clamped, param.step, param.dtype);
            sample_row.push(quantized);
        }
        samples.push(sample_row);
    }

    samples
}

/// 运行敏感性测试
pub fn run_sensitivity_test(
    data_dict: &DataContainer,
    center_param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &SensitivityConfig,
) -> Result<SensitivityResult, QuantError> {
    // 0. 验证参数
    if config.jitter_ratio <= 0.0 {
        return Err(QuantError::InvalidParam(format!(
            "jitter_ratio must be greater than 0, got {}",
            config.jitter_ratio
        )));
    }

    // 1. 初始化 RNG
    let mut rng = match config.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::from_os_rng(),
    };

    // 2. 提取参数
    let flat_params = extract_optimizable_params(center_param);
    if flat_params.is_empty() {
        return Err(QuantError::InvalidParam(
            "No optimizable parameters found for sensitivity test".into(),
        ));
    }

    let original_values: Vec<f64> = flat_params.iter().map(|p| p.param.value).collect();

    // 3. 生成采样点
    let sample_points = generate_jitter_samples(&original_values, &flat_params, config, &mut rng);

    // 4. 并行执行回测
    let metric_key = config.metric.as_str();

    let total_samples_requested = sample_points.len();
    let results: Vec<Result<SensitivitySample, QuantError>> = sample_points
        .into_par_iter()
        .map(|vals| {
            let mut current_set = center_param.clone();
            apply_values_to_param(&mut current_set, &flat_params, &vals);

            // 强制单线程执行 Polars
            let summary = utils::process_param_in_single_thread(|| {
                execute_single_backtest(data_dict, &current_set, template, settings)
            })?;

            let val = summary
                .performance
                .as_ref()
                .and_then(|p| p.get(metric_key))
                .cloned()
                .unwrap_or(0.0);

            let mut all_metrics = HashMap::new();
            if let Some(perf) = &summary.performance {
                for (k, v) in perf {
                    all_metrics.insert(k.clone(), *v);
                }
            }

            Ok(SensitivitySample {
                values: vals,
                metric_value: val,
                all_metrics,
            })
        })
        .collect();

    // 5. 聚合结果（失败样本不直接中断，统一做失败统计）
    let mut successful_samples: Vec<SensitivitySample> = Vec::new();
    let mut failed_samples: usize = 0;
    for r in results {
        match r {
            Ok(sample) => successful_samples.push(sample),
            Err(_) => failed_samples += 1,
        }
    }

    if successful_samples.is_empty() {
        return Err(QuantError::InfrastructureError(
            "All sensitivity samples failed".into(),
        ));
    }

    // 6. 计算中心参数的性能
    let center_summary = execute_single_backtest(data_dict, center_param, template, settings)?;
    let original_value = center_summary
        .performance
        .as_ref()
        .and_then(|p| p.get(metric_key))
        .cloned()
        .unwrap_or(0.0);

    // 7. 计算统计量
    let values: Vec<f64> = successful_samples.iter().map(|s| s.metric_value).collect();
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n;
    let std = variance.sqrt();
    let min = values.iter().fold(f64::INFINITY, |a, &b| a.min(b));
    let max = values.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));

    let mut sorted_values = values.clone();
    sorted_values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = sorted_values[sorted_values.len() / 2];
    let p05 = quantile_from_sorted(&sorted_values, 0.05);
    let p25 = quantile_from_sorted(&sorted_values, 0.25);
    let p75 = quantile_from_sorted(&sorted_values, 0.75);
    let p95 = quantile_from_sorted(&sorted_values, 0.95);

    let cv = if mean.abs() > 1e-6 {
        std / mean.abs()
    } else {
        0.0
    };

    let successful_count = successful_samples.len();
    let failed_sample_rate = if total_samples_requested > 0 {
        failed_samples as f64 / total_samples_requested as f64
    } else {
        0.0
    };

    let mut by_metric_desc = successful_samples.clone();
    by_metric_desc.sort_by(|a, b| {
        b.metric_value
            .partial_cmp(&a.metric_value)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let top_k_samples: Vec<SensitivitySample> = by_metric_desc.into_iter().take(5).collect();

    let mut by_metric_asc = successful_samples.clone();
    by_metric_asc.sort_by(|a, b| {
        a.metric_value
            .partial_cmp(&b.metric_value)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    let bottom_k_samples: Vec<SensitivitySample> = by_metric_asc.into_iter().take(5).collect();

    Ok(SensitivityResult {
        target_metric: metric_key.to_string(),
        original_value,
        samples: successful_samples,
        total_samples_requested,
        successful_samples: successful_count,
        failed_samples,
        failed_sample_rate,
        mean,
        std,
        min,
        max,
        median,
        p05,
        p25,
        p75,
        p95,
        cv,
        top_k_samples,
        bottom_k_samples,
    })
}

/// PyO3 接口函数：运行敏感性测试
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.sensitivity",
    python = r#"
import pyo3_quant

def run_sensitivity_test(
    data_dict: pyo3_quant.DataContainer,
    param: pyo3_quant.SingleParamSet,
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
    config: pyo3_quant.SensitivityConfig,
) -> pyo3_quant.SensitivityResult:
    """运行敏感性测试"""
"#
)]
#[pyfunction(name = "run_sensitivity_test")]
pub fn py_run_sensitivity_test(
    data_dict: DataContainer,
    center_param: SingleParamSet,
    template: TemplateContainer,
    settings: SettingContainer,
    config: crate::types::SensitivityConfig,
) -> PyResult<crate::types::SensitivityResult> {
    let result = run_sensitivity_test(&data_dict, &center_param, &template, &settings, &config)?;
    Ok(result)
}
