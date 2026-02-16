//! 优化器运行器模块
//!
//! 主入口函数和并行调度逻辑

mod rebuild;
mod sampling;

use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::optimizer_core::{
    merge_top_k, should_stop_patience, validate_config,
};
use crate::backtest_engine::optimizer::param_extractor::{
    apply_values_to_param, extract_optimizable_params,
};
use crate::backtest_engine::utils;
use crate::error::{OptimizerError, QuantError};
use crate::types::{
    BenchmarkFunction, DataContainer, OptimizationResult, OptimizerConfig, RoundSummary,
    SamplePoint, SettingContainer, SingleParamSet, TemplateContainer,
};
use rand::rngs::StdRng;
use rand::SeedableRng;
use rayon::prelude::*;
use std::collections::HashMap;

use rebuild::rebuild_param_set;
use sampling::generate_samples;

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

/// 运行参数优化 (通用版本)
pub fn run_optimization_generic(
    eval_mode: EvalMode,
    param: &SingleParamSet,
    config: &OptimizerConfig,
) -> Result<OptimizationResult, QuantError> {
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

    let mut rng = match config.seed {
        Some(s) => StdRng::seed_from_u64(s),
        None => StdRng::from_os_rng(),
    };

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
    let mut max_seen: f64 = f64::NEG_INFINITY;
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

        let round_results: Vec<Result<SamplePoint, QuantError>> = next_round_vals
            .into_par_iter()
            .map(|vals| {
                let mut current_set = param.clone();
                apply_values_to_param(&mut current_set, &flat_params, &vals);

                let (metric_value, all_metrics) = match &eval_mode {
                    EvalMode::Backtest {
                        data_dict,
                        template,
                        settings,
                    } => {
                        // 单任务内部强制 Polars 单线程，避免双层并行冲突
                        let summary = utils::process_param_in_single_thread(|| {
                            execute_single_backtest(data_dict, &current_set, template, settings)
                        })?;
                        let val = summary
                            .performance
                            .as_ref()
                            .and_then(|p| p.get(optimize_metric))
                            .cloned()
                            .unwrap_or(0.0);

                        let mut metrics = HashMap::new();
                        if let Some(perf) = &summary.performance {
                            for (k, v) in perf {
                                metrics.insert(k.clone(), *v);
                            }
                        }
                        (val, metrics)
                    }
                    EvalMode::BenchmarkFunction { function } => {
                        // 基准函数默认最小化，优化器统一最大化，因此取负
                        let val = function.evaluate(&vals);
                        (-val, HashMap::new())
                    }
                };

                Ok(SamplePoint {
                    values: vals,
                    metric_value,
                    all_metrics,
                })
            })
            .collect();

        let successful_samples: Vec<SamplePoint> =
            round_results.into_iter().collect::<Result<Vec<_>, _>>()?;

        if successful_samples.is_empty() {
            return Err(
                OptimizerError::SamplingFailed("All samples in round failed".into()).into(),
            );
        }

        total_samples += successful_samples.len();

        let mut successful_samples = successful_samples;
        successful_samples.sort_by(|a, b| {
            b.metric_value
                .partial_cmp(&a.metric_value)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let round_best = successful_samples[0].metric_value;
        let round_median = successful_samples[successful_samples.len() / 2].metric_value;

        let k = ((n_samples as f64 * config.top_k_ratio) as usize).max(1);
        top_k_samples = merge_top_k(&top_k_samples, &successful_samples, k);

        if best_all_time
            .as_ref()
            .is_none_or(|b| round_best > b.metric_value)
        {
            best_all_time = Some(successful_samples[0].clone());
        }

        if round_best > max_seen {
            max_seen = round_best;
        }

        history.push(RoundSummary {
            round,
            best_value: max_seen,
            median_value: round_median,
            sample_count: successful_samples.len(),
        });

        if total_samples >= config.min_samples
            && should_stop_patience(&history, config.stop_patience)
        {
            break;
        }
    }

    let best = best_all_time
        .ok_or_else(|| OptimizerError::SamplingFailed("No samples succeeded".into()))?;

    let best_param_set = rebuild_param_set(param, &flat_params, &best.values);

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
        optimize_metric: config.optimize_metric,
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
