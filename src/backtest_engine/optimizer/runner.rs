//! 优化器运行器模块
//!
//! 主入口函数和并行调度逻辑

use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::optimizer_core::{
    merge_top_k, should_stop_patience, validate_config, SamplePoint,
};
use crate::backtest_engine::optimizer::param_extractor::{
    apply_values_to_param, extract_optimizable_params, quantize_value, FlattenedParam,
};
use crate::backtest_engine::optimizer::sampler::{
    lhs_sample, transform_sample, weighted_gaussian_sample,
};
use crate::error::{OptimizerError, QuantError};
use crate::types::OptimizerConfig;
use crate::types::{DataContainer, SettingContainer, SingleParamSet, TemplateContainer};
use crate::types::{OptimizationResult, RoundSummary};
use pyo3::prelude::*;
use rand::rngs::StdRng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashMap;

/// 生成一批采样点的参数值
///
/// # 参数
/// * `n_samples` - 采样数量
/// * `explore_count` - 探索采样数量（LHS）
/// * `n_dims` - 参数维度
/// * `flat_params` - 平铺参数列表
/// * `top_k_samples` - 当前TopK样本
/// * `config` - 优化器配置
/// * `rng` - 随机数生成器
///
/// # 返回
/// 采样参数值列表
fn generate_samples(
    n_samples: usize,
    explore_count: usize,
    n_dims: usize,
    flat_params: &[FlattenedParam],
    top_k_samples: &[SamplePoint],
    config: &OptimizerConfig,
    rng: &mut StdRng,
) -> Vec<Vec<f64>> {
    let exploitation_count = n_samples - explore_count;
    let mut next_round_vals = Vec::with_capacity(n_samples);

    // 探索部分：LHS
    if explore_count > 0 {
        let u_samples = lhs_sample(explore_count, n_dims, rng);
        for u_row in u_samples {
            let mut vals = Vec::new();
            for (dim, &u) in u_row.iter().enumerate() {
                let p = &flat_params[dim];
                let val = transform_sample(u, p.min, p.max, p.log_scale);
                vals.push(quantize_value(val, p.step, p.dtype));
            }
            next_round_vals.push(vals);
        }
    }

    // 利用部分：权重高斯
    if exploitation_count > 0 && !top_k_samples.is_empty() {
        for _ in 0..exploitation_count {
            let mut vals = Vec::new();
            for (dim, p) in flat_params.iter().enumerate() {
                let centers: Vec<(f64, f64)> = top_k_samples
                    .iter()
                    .enumerate()
                    .map(|(i, s)| {
                        let weight = (-(config.weight_decay * i as f64)).exp();
                        (s.values[dim], weight)
                    })
                    .collect();

                let val = weighted_gaussian_sample(
                    &centers,
                    p.min,
                    p.max,
                    config.sigma_ratio,
                    p.log_scale,
                    rng,
                );
                vals.push(quantize_value(val, p.step, p.dtype));
            }
            next_round_vals.push(vals);
        }
    }

    next_round_vals
}

/// 构建最佳参数的结构化映射
fn build_best_params_map(
    best_values: &[f64],
    flat_params: &[FlattenedParam],
) -> (
    HashMap<String, HashMap<String, HashMap<String, f64>>>,
    HashMap<String, f64>,
    HashMap<String, f64>,
) {
    let mut best_indicators_map: HashMap<String, HashMap<String, HashMap<String, f64>>> =
        HashMap::new();
    let mut best_signal_map = HashMap::new();
    let mut best_backtest_map = HashMap::new();

    for (dim, &val) in best_values.iter().enumerate() {
        let p = &flat_params[dim];
        let final_val = quantize_value(val, p.step, p.dtype);

        match p.type_idx {
            0 => {
                // Indicator
                let parts: Vec<&str> = p.group.split(':').collect();
                if parts.len() == 2 {
                    best_indicators_map
                        .entry(parts[0].to_string())
                        .or_default()
                        .entry(parts[1].to_string())
                        .or_default()
                        .insert(p.name.clone(), final_val);
                }
            }
            1 => {
                // Signal
                best_signal_map.insert(p.name.clone(), final_val);
            }
            2 => {
                // Backtest
                best_backtest_map.insert(p.name.clone(), final_val);
            }
            _ => {}
        }
    }

    (best_indicators_map, best_signal_map, best_backtest_map)
}

/// 运行参数优化
///
/// # 参数
/// * `data_dict` - 数据容器
/// * `param_set` - 参数集容器
/// * `template` - 模板容器
/// * `settings` - 设置容器
/// * `config` - 优化器配置
///
/// # 返回
/// 优化结果或错误
pub fn run_optimization(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &OptimizerConfig,
) -> Result<OptimizationResult, QuantError> {
    // 验证配置
    let validation = validate_config(
        config.explore_ratio,
        config.top_k_ratio,
        config.samples_per_round,
        config.sigma_ratio,
    );
    if !validation.is_valid {
        return Err(OptimizerError::InvalidConfig(format!(
            "Invalid config: {}",
            validation.errors.join("; ")
        ))
        .into());
    }

    let mut rng = StdRng::from_os_rng();

    // 1. 提取所有需要优化的参数并平铺
    let flat_params = extract_optimizable_params(param);

    if flat_params.is_empty() {
        return Err(
            OptimizerError::InvalidConfig("No parameters marked for optimization".into()).into(),
        );
    }

    let n_dims = flat_params.len();
    let mut best_all_time: Option<SamplePoint> = None;
    let mut history = Vec::new();
    let mut total_samples = 0;
    let mut top_k_samples: Vec<SamplePoint> = Vec::new();

    // 追踪历史极值用于计算发现新高
    let mut max_seen: f64 = f64::NEG_INFINITY;

    // 优化目标指标（使用枚举的as_str()获取键名）
    let optimize_metric = config.optimize_metric.as_str();

    for round in 1..=config.max_rounds {
        if total_samples >= config.max_samples {
            break;
        }

        let n_samples = config.samples_per_round;
        let explore_count = if round == 1 {
            n_samples
        } else {
            (n_samples as f64 * config.explore_ratio) as usize
        };

        // 生成采样点
        let next_round_vals = generate_samples(
            n_samples,
            explore_count,
            n_dims,
            &flat_params,
            &top_k_samples,
            config,
            &mut rng,
        );

        // 并行回测执行
        let round_results: Vec<Result<SamplePoint, QuantError>> = next_round_vals
            .into_par_iter()
            .map(|vals| {
                let mut current_set = param.clone();
                apply_values_to_param(&mut current_set, &flat_params, &vals);

                // 执行实际回测
                let summary =
                    execute_single_backtest(data_dict, &current_set, template, settings, None)?;

                // 使用配置的优化指标
                let metric_value = summary
                    .performance
                    .as_ref()
                    .and_then(|p| p.get(optimize_metric))
                    .cloned()
                    .unwrap_or(0.0);
                Ok(SamplePoint {
                    values: vals,
                    calmar: metric_value, // 字段名暂保持calmar，但实际存储的是optimize_metric的值
                })
            })
            .collect();

        // 收集成功的结果
        let mut successful_samples = Vec::new();
        let mut _error_count = 0;
        for res in round_results {
            match res {
                Ok(s) => successful_samples.push(s),
                Err(_e) => {
                    _error_count += 1;
                    // 可以在此记录日志
                }
            }
        }

        if successful_samples.is_empty() {
            return Err(
                OptimizerError::SamplingFailed("All samples in round failed".into()).into(),
            );
        }

        total_samples += successful_samples.len();

        // 排序
        successful_samples.sort_by(|a, b| {
            b.calmar
                .partial_cmp(&a.calmar)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let round_best = successful_samples[0].calmar;
        let round_median = successful_samples[successful_samples.len() / 2].calmar;

        // 合并 TopK（累积历史最优）
        let k = (n_samples as f64 * config.top_k_ratio) as usize;
        top_k_samples = merge_top_k(&top_k_samples, &successful_samples, k);

        // 更新全局最优
        if best_all_time
            .as_ref()
            .map_or(true, |b| round_best > b.calmar)
        {
            best_all_time = Some(successful_samples[0].clone());
        }

        // 更新历史极值（用于停止条件判断）
        if round_best > max_seen {
            max_seen = round_best;
        }

        // 记录历史（存储累积最佳，而非当前轮最佳，用于停止条件计算）
        history.push(RoundSummary {
            round,
            best_calmar: max_seen, // 累积最佳，用于停止条件
            median_calmar: round_median,
            sample_count: successful_samples.len(),
        });

        // 停止条件检测（需满足最小采样数和最小轮数）
        if total_samples >= config.min_samples {
            if should_stop_patience(&history, config.stop_patience) {
                break;
            }
        }
    }

    // 构建最终结果
    let best = best_all_time
        .ok_or_else(|| OptimizerError::SamplingFailed("No samples succeeded".into()))?;

    let (best_indicators_map, best_signal_map, best_backtest_map) =
        build_best_params_map(&best.values, &flat_params);

    Ok(OptimizationResult {
        best_params: best_indicators_map,
        best_signal_params: best_signal_map,
        best_backtest_params: best_backtest_map,
        best_calmar: best.calmar,
        total_samples,
        rounds: history.len(),
        history,
        best_sample_values: Some(best.values.clone()),
        top_k_samples,
    })
}

#[pyfunction]
pub fn py_run_optimizer(
    data_dict: DataContainer,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    optimizer_config: OptimizerConfig,
) -> PyResult<OptimizationResult> {
    run_optimization(
        &data_dict,
        &param,
        &template,
        &engine_settings,
        &optimizer_config,
    )
    .map_err(|e| e.into())
}
