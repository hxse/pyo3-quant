//! 优化器运行器模块
//!
//! 主入口函数和并行调度逻辑

use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::optimizer_core::{
    merge_top_k, should_stop_patience, validate_config, SamplePoint,
};
use crate::backtest_engine::optimizer::param_extractor::{
    apply_values_to_param, extract_optimizable_params, quantize_value, set_param_value,
    FlattenedParam,
};
use crate::backtest_engine::optimizer::sampler::{
    lhs_sample, transform_sample, weighted_gaussian_sample,
};
use crate::error::{OptimizerError, QuantError};
use crate::types::OptimizerConfig;
use crate::types::{DataContainer, SettingContainer, SingleParamSet, TemplateContainer};
use crate::types::{OptimizationResult, RoundSummary};
use rand::rngs::StdRng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashMap;

use super::benchmark::BenchmarkFunction;

/// 评估模式枚举
pub enum EvalMode<'a> {
    /// 回测模式
    Backtest {
        data_dict: &'a DataContainer,
        template: &'a TemplateContainer,
        settings: &'a SettingContainer,
    },
    /// 基准函数模式
    BenchmarkFunction { function: BenchmarkFunction },
}

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
    current_round: usize,
) -> Vec<Vec<f64>> {
    let exploitation_count = n_samples - explore_count;
    let mut next_round_vals = Vec::with_capacity(n_samples);

    // Sigma Decay: 随着轮数增加，搜索半径减小
    // 使用 1/sqrt(round) 衰减，或者 1/round
    // 初始 round=1. decay=1.0. round=10, decay=0.3. round=100, decay=0.1.
    // round=1 -> decay=1.0
    // round=4 -> decay=0.5
    let decay = 1.0 / (current_round as f64).sqrt();
    let current_sigma_ratio = config.sigma_ratio * decay;

    // 探索部分：LHS
    if explore_count > 0 {
        let u_samples = lhs_sample(explore_count, n_dims, rng);
        for u_row in u_samples {
            let mut vals = Vec::new();
            for (dim, &u) in u_row.iter().enumerate() {
                let p = &flat_params[dim];
                let val = transform_sample(u, p.param.min, p.param.max, p.param.log_scale);
                vals.push(quantize_value(val, p.param.step, p.param.dtype));
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
                    p.param.min,
                    p.param.max,
                    current_sigma_ratio,
                    p.param.log_scale,
                    rng,
                );
                vals.push(quantize_value(val, p.param.step, p.param.dtype));
            }
            next_round_vals.push(vals);
        }
    }

    next_round_vals
}

/// 根据最优值重建参数集
fn rebuild_param_set(
    original: &SingleParamSet,
    flat_params: &[FlattenedParam],
    best_values: &[f64],
) -> SingleParamSet {
    let mut new_param_set = original.clone();

    for (dim, &val) in best_values.iter().enumerate() {
        if dim < flat_params.len() {
            set_param_value(&mut new_param_set, &flat_params[dim], val);
        }
    }

    new_param_set
}

/// 运行参数优化 (通用版本)
pub fn run_optimization_generic(
    eval_mode: EvalMode,
    param: &SingleParamSet,
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
            round,
        );

        // 并行回测执行
        let round_results: Vec<Result<SamplePoint, QuantError>> = next_round_vals
            .into_par_iter()
            .map(|vals| {
                let mut current_set = param.clone();
                apply_values_to_param(&mut current_set, &flat_params, &vals);

                // 执行实际回测 或 基准函数评估
                let (metric_value, all_metrics) = match &eval_mode {
                    EvalMode::Backtest {
                        data_dict,
                        template,
                        settings,
                    } => {
                        let summary =
                            execute_single_backtest(data_dict, &current_set, template, settings)?;
                        let val = summary
                            .performance
                            .as_ref()
                            .and_then(|p| p.get(optimize_metric))
                            .cloned()
                            .unwrap_or(0.0);

                        // 提取所有已计算的指标
                        let mut metrics = HashMap::new();
                        if let Some(perf) = &summary.performance {
                            for (k, v) in perf {
                                metrics.insert(k.clone(), *v);
                            }
                        }
                        (val, metrics)
                    }
                    EvalMode::BenchmarkFunction { function } => {
                        // 基准函数是求最小值，优化器默认是求最大值
                        // 因此这取负值，将其转换为最大化问题
                        let val = function.evaluate(&vals);
                        (-val, HashMap::new())
                    }
                };

                Ok(SamplePoint {
                    values: vals,
                    metric_value: metric_value,
                    all_metrics: all_metrics,
                })
            })
            .collect();

        // 收集结果，任何错误直接传播
        let successful_samples: Vec<SamplePoint> =
            round_results.into_iter().collect::<Result<Vec<_>, _>>()?;

        if successful_samples.is_empty() {
            return Err(
                OptimizerError::SamplingFailed("All samples in round failed".into()).into(),
            );
        }

        total_samples += successful_samples.len();

        // 排序
        let mut successful_samples = successful_samples;
        successful_samples.sort_by(|a, b| {
            b.metric_value
                .partial_cmp(&a.metric_value)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let round_best = successful_samples[0].metric_value;
        let round_median = successful_samples[successful_samples.len() / 2].metric_value;

        // 合并 TopK（累积历史最优）
        let k = ((n_samples as f64 * config.top_k_ratio) as usize).max(1);
        top_k_samples = merge_top_k(&top_k_samples, &successful_samples, k);

        // 更新全局最优
        if best_all_time
            .as_ref()
            .map_or(true, |b| round_best > b.metric_value)
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
            best_value: max_seen, // 累积最佳，用于停止条件
            median_value: round_median,
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

    // 重建完整的最优参数集
    let best_param_set = rebuild_param_set(param, &flat_params, &best.values);

    // 构建 Top K 参数集
    let top_k_params: Vec<SingleParamSet> = top_k_samples
        .iter()
        .take(if config.return_top_k > 0 {
            config.return_top_k
        } else {
            0
        })
        .map(|s| rebuild_param_set(param, &flat_params, &s.values))
        .collect();

    Ok(OptimizationResult {
        best_params: best_param_set,
        optimize_metric: config.optimize_metric.as_str().to_string(),
        optimize_value: best.metric_value,
        metrics: best.all_metrics.clone(),
        total_samples,
        rounds: history.len(),
        history,
        top_k_params,
        top_k_samples,
    })
}

/// 运行参数优化 (Backtest Wrapper)
pub fn run_optimization(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &OptimizerConfig,
) -> Result<OptimizationResult, QuantError> {
    run_optimization_generic(
        EvalMode::Backtest {
            data_dict,
            template,
            settings,
        },
        param,
        config,
    )
}
