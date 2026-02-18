use crate::backtest_engine::data_ops::slice_data_container_by_base_window;
use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::run_optimization;
use crate::backtest_engine::walk_forward::data_splitter::generate_windows;
use crate::error::{OptimizerError, QuantError};
use crate::types::WalkForwardConfig;
use crate::types::{
    DataContainer, ExecutionStage, MetricDistributionStats, OptimizeMetric, SettingContainer,
    SingleParamSet, TemplateContainer,
};
use crate::types::{WalkForwardResult, WindowResult};
use polars::prelude::*;
use pyo3::prelude::*;
use std::cmp::Ordering;
use std::collections::HashMap;

/// 运行向前滚动优化
pub fn run_walk_forward(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError> {
    let total_bars = data_dict
        .source
        .get(&data_dict.base_data_key)
        .ok_or(OptimizerError::NoData)?
        .height();

    let windows = generate_windows(total_bars, config)?;
    if windows.is_empty() {
        return Err(
            OptimizerError::InvalidConfig("No walk-forward windows generated".into()).into(),
        );
    }

    let mut window_results = Vec::new();
    let mut prev_top_k: Option<Vec<Vec<f64>>> = None;

    let mut stitched_time: Vec<i64> = Vec::new();
    let mut stitched_equity: Vec<f64> = Vec::new();
    let mut last_global_equity = 1.0_f64;
    let mut last_time: Option<i64> = None;

    for window in windows {
        let train_len = window.train_range.1 - window.train_range.0;
        let train_data =
            slice_data_container_by_base_window(data_dict, window.train_range.0, train_len)?;

        let mut opt_config = config.optimizer_config.clone();
        if config.inherit_prior {
            if let Some(ref priors) = prev_top_k {
                if !priors.is_empty() {
                    opt_config.init_samples = Some(priors.clone());
                }
            }
        }

        let train_result = run_optimization(&train_data, param, template, settings, &opt_config)?;

        let eval_start = window.transition_range.0;
        let eval_len = window.test_range.1 - window.transition_range.0;
        let transition_len = window.transition_range.1 - window.transition_range.0;
        let test_len = window.test_range.1 - window.test_range.0;

        let eval_data = slice_data_container_by_base_window(data_dict, eval_start, eval_len)?;

        let mut eval_settings = settings.clone();
        eval_settings.execution_stage = ExecutionStage::Performance;
        eval_settings.return_only_final = false;

        let eval_summary = execute_single_backtest(
            &eval_data,
            &train_result.best_params,
            template,
            &eval_settings,
        )?;

        let eval_backtest_df = eval_summary.backtest.ok_or_else(|| {
            OptimizerError::SamplingFailed(
                "Walk-forward evaluation requires full backtest dataframe".into(),
            )
        })?;

        let test_backtest_df = eval_backtest_df.slice(transition_len as i64, test_len);
        let test_data =
            slice_data_container_by_base_window(data_dict, window.test_range.0, test_len)?;

        let test_metrics = crate::backtest_engine::performance_analyzer::analyze_performance(
            &test_data,
            &test_backtest_df,
            &train_result.best_params.performance,
        )?;

        let train_test_gap_metrics =
            build_train_test_gap_metrics(&train_result.metrics, &test_metrics);

        let test_times = extract_base_times(&eval_data)?
            .into_iter()
            .skip(transition_len)
            .take(test_len)
            .collect::<Vec<_>>();
        let test_equity = extract_equity_series(&test_backtest_df)?;
        let test_returns = compute_returns_from_equity(&test_equity);

        append_to_stitched_curve(
            &test_times,
            &test_equity,
            &mut stitched_time,
            &mut stitched_equity,
            &mut last_global_equity,
            &mut last_time,
        )?;

        window_results.push(WindowResult {
            window_id: window.id,
            train_range: window.train_range,
            transition_range: window.transition_range,
            test_range: window.test_range,
            best_params: train_result.best_params,
            optimize_metric: config.optimizer_config.optimize_metric,
            train_metrics: train_result.metrics,
            test_metrics,
            train_test_gap_metrics,
            test_times,
            test_returns,
            history: Some(train_result.history.clone()),
        });

        let current_top_k: Vec<Vec<f64>> = train_result
            .top_k_samples
            .iter()
            .map(|s| s.values.clone())
            .collect();
        prev_top_k = Some(current_top_k);

        println!("Window {} Finished.", window.id);
    }

    let aggregate_test_metrics =
        compute_stitched_aggregate_metrics(&stitched_time, &stitched_equity);
    let window_metric_stats = compute_window_metric_stats(&window_results);
    let (best_window_id, worst_window_id) =
        select_best_worst_window(&window_results, config.optimizer_config.optimize_metric)?;

    Ok(WalkForwardResult {
        windows: window_results,
        optimize_metric: config.optimizer_config.optimize_metric,
        aggregate_test_metrics,
        window_metric_stats,
        stitched_time,
        stitched_equity,
        best_window_id,
        worst_window_id,
    })
}

fn select_best_worst_window(
    windows: &[WindowResult],
    optimize_metric: OptimizeMetric,
) -> Result<(usize, usize), QuantError> {
    let key = optimize_metric.as_str();
    let mut scored: Vec<(usize, f64)> = windows
        .iter()
        .map(|w| {
            let score = w
                .test_metrics
                .get(key)
                .copied()
                .or_else(|| w.test_metrics.get("total_return").copied())
                .unwrap_or(0.0);
            (w.window_id, score)
        })
        .collect();

    if scored.is_empty() {
        return Err(OptimizerError::SamplingFailed("No windows for scoring".into()).into());
    }

    scored.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));
    let worst = scored
        .first()
        .map(|x| x.0)
        .ok_or_else(|| OptimizerError::SamplingFailed("No worst window".into()))?;
    let best = scored
        .last()
        .map(|x| x.0)
        .ok_or_else(|| OptimizerError::SamplingFailed("No best window".into()))?;

    Ok((best, worst))
}

fn compute_window_metric_stats(
    windows: &[WindowResult],
) -> HashMap<String, MetricDistributionStats> {
    let mut metric_values: HashMap<String, Vec<f64>> = HashMap::new();

    for window in windows {
        for (k, v) in &window.test_metrics {
            metric_values.entry(k.clone()).or_default().push(*v);
        }
    }

    metric_values
        .into_iter()
        .map(|(k, values)| (k, summarize_distribution(&values)))
        .collect()
}

fn summarize_distribution(values: &[f64]) -> MetricDistributionStats {
    if values.is_empty() {
        return MetricDistributionStats {
            mean: 0.0,
            median: 0.0,
            std: 0.0,
            min: 0.0,
            max: 0.0,
            p05: 0.0,
            p95: 0.0,
        };
    }

    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let var = if values.len() > 1 {
        values
            .iter()
            .map(|v| {
                let d = *v - mean;
                d * d
            })
            .sum::<f64>()
            / n
    } else {
        0.0
    };

    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));

    MetricDistributionStats {
        mean,
        median: percentile_linear(&sorted, 0.50),
        std: var.sqrt(),
        min: *sorted.first().unwrap_or(&0.0),
        max: *sorted.last().unwrap_or(&0.0),
        p05: percentile_linear(&sorted, 0.05),
        p95: percentile_linear(&sorted, 0.95),
    }
}

fn percentile_linear(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    if sorted.len() == 1 {
        return sorted[0];
    }

    let rank = p.clamp(0.0, 1.0) * (sorted.len() as f64 - 1.0);
    let lo = rank.floor() as usize;
    let hi = rank.ceil() as usize;
    if lo == hi {
        return sorted[lo];
    }
    let weight = rank - lo as f64;
    sorted[lo] * (1.0 - weight) + sorted[hi] * weight
}

fn build_train_test_gap_metrics(
    train_metrics: &HashMap<String, f64>,
    test_metrics: &HashMap<String, f64>,
) -> HashMap<String, f64> {
    let mut gap = HashMap::new();
    for (k, test_val) in test_metrics {
        let train_val = train_metrics.get(k).copied().unwrap_or(0.0);
        gap.insert(k.clone(), train_val - test_val);
    }
    gap
}

fn extract_base_times(data: &DataContainer) -> Result<Vec<i64>, QuantError> {
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| OptimizerError::NoData)?;
    let time_col = base_df.column("time")?.i64()?;

    let mut out = Vec::with_capacity(time_col.len());
    for v in time_col.into_iter() {
        out.push(v.unwrap_or(0));
    }
    Ok(out)
}

fn extract_equity_series(backtest_df: &DataFrame) -> Result<Vec<f64>, QuantError> {
    let equity_col = backtest_df.column("equity")?.f64()?;
    let mut out = Vec::with_capacity(equity_col.len());
    for v in equity_col.into_iter() {
        out.push(v.unwrap_or(0.0));
    }
    Ok(out)
}

fn compute_returns_from_equity(equity: &[f64]) -> Vec<f64> {
    if equity.len() < 2 {
        return Vec::new();
    }
    let mut out = Vec::with_capacity(equity.len() - 1);
    for i in 1..equity.len() {
        let prev = equity[i - 1];
        let curr = equity[i];
        if prev > 0.0 {
            out.push(curr / prev - 1.0);
        } else {
            out.push(0.0);
        }
    }
    out
}

fn append_to_stitched_curve(
    test_times: &[i64],
    test_equity: &[f64],
    stitched_time: &mut Vec<i64>,
    stitched_equity: &mut Vec<f64>,
    last_global_equity: &mut f64,
    last_time: &mut Option<i64>,
) -> Result<(), QuantError> {
    if test_times.len() != test_equity.len() {
        return Err(OptimizerError::InvalidConfig(
            "test_times and test_equity length mismatch".into(),
        )
        .into());
    }

    for idx in 0..test_times.len() {
        let t = test_times[idx];
        if let Some(prev_t) = *last_time {
            if t <= prev_t {
                return Err(OptimizerError::InvalidConfig(format!(
                    "overlapping or non-increasing test time detected: {} <= {}",
                    t, prev_t
                ))
                .into());
            }
        }

        let growth = if idx == 0 {
            1.0
        } else {
            let prev = test_equity[idx - 1];
            let curr = test_equity[idx];
            if prev > 0.0 {
                curr / prev
            } else {
                1.0
            }
        };

        *last_global_equity *= growth;
        stitched_time.push(t);
        stitched_equity.push(*last_global_equity);
        *last_time = Some(t);
    }

    Ok(())
}

fn compute_stitched_aggregate_metrics(
    stitched_time: &[i64],
    stitched_equity: &[f64],
) -> HashMap<String, f64> {
    let mut metrics = HashMap::new();
    if stitched_time.len() < 2 || stitched_equity.len() < 2 {
        return metrics;
    }

    let first = stitched_equity[0];
    let last = stitched_equity[stitched_equity.len() - 1];
    let total_return = if first > 0.0 { last / first - 1.0 } else { 0.0 };

    let mut peak = stitched_equity[0];
    let mut max_drawdown = 0.0;
    for &v in stitched_equity {
        if v > peak {
            peak = v;
        }
        if peak > 0.0 {
            let dd = 1.0 - (v / peak);
            if dd > max_drawdown {
                max_drawdown = dd;
            }
        }
    }

    let n = stitched_time.len();
    let span_ms = (stitched_time[n - 1] - stitched_time[0]) as f64;
    let ms_per_year = 365.25 * 24.0 * 3600.0 * 1000.0;
    let span_years = if span_ms > 0.0 {
        span_ms / ms_per_year
    } else {
        0.0
    };
    let annualization_factor = if span_years > 0.0 {
        n as f64 / span_years
    } else {
        1.0
    };
    let annualized_return = if span_years > 0.0 {
        (1.0 + total_return).powf(1.0 / span_years) - 1.0
    } else {
        total_return
    };

    let calmar_ratio_raw = if max_drawdown > 0.0 {
        total_return / max_drawdown
    } else {
        0.0
    };
    let calmar_ratio = if max_drawdown > 0.0 {
        annualized_return / max_drawdown
    } else {
        0.0
    };

    metrics.insert("total_return".to_string(), total_return);
    metrics.insert("max_drawdown".to_string(), max_drawdown);
    metrics.insert("annualization_factor".to_string(), annualization_factor);
    metrics.insert("annualized_return".to_string(), annualized_return);
    metrics.insert("calmar_ratio_raw".to_string(), calmar_ratio_raw);
    metrics.insert("calmar_ratio".to_string(), calmar_ratio);
    metrics
}

use pyo3_stub_gen::derive::*;

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
