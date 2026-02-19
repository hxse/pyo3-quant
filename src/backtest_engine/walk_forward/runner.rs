use crate::backtest_engine::data_ops::{
    concat_backtest_summaries, rebuild_capital_columns_for_stitched_backtest,
    slice_backtest_summary_by_base_window, slice_data_container_by_base_window,
};
use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::run_optimization;
use crate::backtest_engine::utils::BacktestContext;
use crate::backtest_engine::walk_forward::data_splitter::generate_windows;
use crate::error::{OptimizerError, QuantError};
use crate::types::WalkForwardConfig;
use crate::types::{
    DataContainer, ExecutionStage, NextWindowHint, SettingContainer, SingleParamSet,
    StitchedArtifact, TemplateContainer, WalkForwardResult, WindowArtifact,
};
use polars::prelude::*;
use pyo3::prelude::*;

const MS_PER_DAY: f64 = 86_400_000.0;
const DAYS_PER_MONTH: f64 = 30.44;

/// 运行向前滚动优化（完整产物返回）
pub fn run_walk_forward(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError> {
    let base_times = extract_base_times(data_dict)?;
    let total_bars = base_times.len();

    let windows = generate_windows(total_bars, config)?;
    if windows.is_empty() {
        return Err(
            OptimizerError::InvalidConfig("No walk-forward windows generated".into()).into(),
        );
    }

    // 中文注释：训练优化阶段统一只保留最终绩效，降低并发内存占用。
    let mut optimize_settings = settings.clone();
    optimize_settings.execution_stage = ExecutionStage::Performance;
    optimize_settings.return_only_final = true;

    let mut window_results: Vec<WindowArtifact> = Vec::new();
    let mut prev_top_k: Option<Vec<Vec<f64>>> = None;

    for window in &windows {
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

        let train_result = run_optimization(
            &train_data,
            param,
            template,
            &optimize_settings,
            &opt_config,
        )?;

        let eval_start = window.transition_range.0;
        let eval_len = window.test_range.1 - window.transition_range.0;
        let transition_len = window.transition_range.1 - window.transition_range.0;
        let test_len = window.test_range.1 - window.test_range.0;

        let eval_data = slice_data_container_by_base_window(data_dict, eval_start, eval_len)?;

        // 中文注释：第一次评估只需要到回测阶段，拿到完整 indicators/signals/backtest 给二次注入评估使用。
        let mut eval_settings = settings.clone();
        eval_settings.execution_stage = ExecutionStage::Backtest;
        eval_settings.return_only_final = false;

        let first_eval_summary = execute_single_backtest(
            &eval_data,
            &train_result.best_params,
            template,
            &eval_settings,
        )?;

        let first_eval_backtest_df = first_eval_summary.backtest.clone().ok_or_else(|| {
            OptimizerError::SamplingFailed(
                "Walk-forward first evaluation requires full backtest dataframe".into(),
            )
        })?;
        let first_eval_signals_df = first_eval_summary.signals.clone().ok_or_else(|| {
            OptimizerError::SamplingFailed(
                "Walk-forward first evaluation requires full signals dataframe".into(),
            )
        })?;

        let (injected_signals_df, has_cross_boundary_position) = build_injected_signals_for_window(
            &first_eval_signals_df,
            &first_eval_backtest_df,
            transition_len,
            test_len,
        )?;

        // 中文注释：第二次评估手动链路，复用第一次 indicators，只替换注入后的 signals。
        let mut second_ctx = BacktestContext::new();
        second_ctx.indicator_dfs = first_eval_summary.indicators.clone();
        second_ctx.signals_df = Some(injected_signals_df);
        second_ctx.execute_backtest_if_needed(
            ExecutionStage::Backtest,
            false,
            &eval_data,
            &train_result.best_params.backtest,
        )?;
        let second_eval_summary = second_ctx.into_summary(false, ExecutionStage::Backtest);

        // 中文注释：窗口级对象只保留 test 段，summary 切片后强制重算 performance。
        let test_data =
            slice_data_container_by_base_window(data_dict, window.test_range.0, test_len)?;
        let mut test_summary = slice_backtest_summary_by_base_window(
            &second_eval_summary,
            &eval_data,
            transition_len,
            test_len,
        )?;

        let test_backtest_df = test_summary.backtest.as_ref().ok_or_else(|| {
            OptimizerError::SamplingFailed(
                "Walk-forward test summary requires full backtest dataframe".into(),
            )
        })?;
        validate_window_capital_series(test_backtest_df)?;

        let test_metrics = crate::backtest_engine::performance_analyzer::analyze_performance(
            &test_data,
            test_backtest_df,
            &param.performance,
        )?;
        test_summary.performance = Some(test_metrics);

        let (time_range, span_ms, span_days, span_months, bars) =
            build_range_identity(&test_data, window.test_range)?;

        window_results.push(WindowArtifact {
            data: test_data,
            summary: test_summary,
            time_range,
            bar_range: window.test_range,
            span_ms,
            span_days,
            span_months,
            bars,
            window_id: window.id,
            train_range: window.train_range,
            transition_range: window.transition_range,
            test_range: window.test_range,
            best_params: train_result.best_params,
            optimize_metric: config.optimizer_config.optimize_metric,
            has_cross_boundary_position,
        });

        let current_top_k: Vec<Vec<f64>> = train_result
            .top_k_samples
            .iter()
            .map(|s| s.values.clone())
            .collect();
        prev_top_k = Some(current_top_k);

        println!("Window {} Finished.", window.id);
    }

    let stitched_result =
        build_stitched_artifact(data_dict, param, &base_times, &windows, &window_results)?;

    Ok(WalkForwardResult {
        optimize_metric: config.optimizer_config.optimize_metric,
        window_results,
        stitched_result,
    })
}

fn build_stitched_artifact(
    data_dict: &DataContainer,
    param: &SingleParamSet,
    base_times: &[i64],
    windows: &[crate::backtest_engine::walk_forward::data_splitter::WindowSpec],
    window_results: &[WindowArtifact],
) -> Result<StitchedArtifact, QuantError> {
    let first = windows
        .first()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;
    let last = windows
        .last()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;

    let stitched_start = first.test_range.0;
    let stitched_end = last.test_range.1;
    let stitched_len = stitched_end - stitched_start;

    let stitched_data =
        slice_data_container_by_base_window(data_dict, stitched_start, stitched_len)?;
    let stitched_times = extract_base_times(&stitched_data)?;
    assert_time_strictly_increasing(&stitched_times)?;

    let summaries: Vec<crate::types::BacktestSummary> =
        window_results.iter().map(|w| w.summary.clone()).collect();
    let mut stitched_summary = concat_backtest_summaries(&summaries)?;

    let stitched_backtest_local = stitched_summary.backtest.as_ref().ok_or_else(|| {
        OptimizerError::SamplingFailed("stitched summary missing backtest dataframe".into())
    })?;
    if stitched_backtest_local.height() != stitched_len {
        return Err(OptimizerError::InvalidConfig(format!(
            "stitched backtest length mismatch: backtest={}, expected={}",
            stitched_backtest_local.height(),
            stitched_len
        ))
        .into());
    }

    let rebuilt_backtest = rebuild_capital_columns_for_stitched_backtest(
        stitched_backtest_local,
        param.backtest.initial_capital,
    )?;
    let stitched_metrics = crate::backtest_engine::performance_analyzer::analyze_performance(
        &stitched_data,
        &rebuilt_backtest,
        &param.performance,
    )?;

    stitched_summary.backtest = Some(rebuilt_backtest);
    stitched_summary.performance = Some(stitched_metrics);

    let time_range = (
        *stitched_times
            .first()
            .ok_or_else(|| OptimizerError::InvalidConfig("stitched time empty".into()))?,
        *stitched_times
            .last()
            .ok_or_else(|| OptimizerError::InvalidConfig("stitched time empty".into()))?,
    );
    let span_ms = time_range.1 - time_range.0;
    let span_days = span_ms as f64 / MS_PER_DAY;
    let span_months = span_days / DAYS_PER_MONTH;

    let next_window_hint = build_next_window_hint(base_times, windows)?;
    let rolling_every_days = next_window_hint.eta_days;

    Ok(StitchedArtifact {
        data: stitched_data,
        summary: stitched_summary,
        time_range,
        bar_range: (stitched_start, stitched_end),
        span_ms,
        span_days,
        span_months,
        bars: stitched_len,
        window_count: windows.len(),
        first_test_time_ms: time_range.0,
        last_test_time_ms: time_range.1,
        rolling_every_days,
        next_window_hint,
    })
}

fn build_next_window_hint(
    base_times: &[i64],
    windows: &[crate::backtest_engine::walk_forward::data_splitter::WindowSpec],
) -> Result<NextWindowHint, QuantError> {
    let last_window = windows
        .last()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;

    let train_start = time_at(base_times, last_window.train_range.0)?;
    let train_end = time_at(base_times, last_window.train_range.1 - 1)?;
    let transition_start = time_at(base_times, last_window.transition_range.0)?;
    let transition_end = time_at(base_times, last_window.transition_range.1 - 1)?;
    let test_start = time_at(base_times, last_window.test_range.0)?;
    let test_end = time_at(base_times, last_window.test_range.1 - 1)?;

    let train_span_ms = (train_end - train_start).max(0);
    let transition_span_ms = (transition_end - transition_start).max(0);
    let rolling_span_ms = (test_end - test_start).max(0);

    let expected_test_start_time_ms = test_end;
    let expected_test_end_time_ms = test_end + rolling_span_ms;
    let expected_transition_start_time_ms = expected_test_start_time_ms - transition_span_ms;
    let expected_train_start_time_ms = expected_transition_start_time_ms - train_span_ms;
    let expected_window_ready_time_ms = expected_test_end_time_ms;
    let eta_days = rolling_span_ms as f64 / MS_PER_DAY;

    Ok(NextWindowHint {
        expected_train_start_time_ms,
        expected_transition_start_time_ms,
        expected_test_start_time_ms,
        expected_test_end_time_ms,
        expected_window_ready_time_ms,
        eta_days,
        based_on_window_id: last_window.id,
    })
}

fn time_at(times: &[i64], idx: usize) -> Result<i64, QuantError> {
    times.get(idx).copied().ok_or_else(|| {
        OptimizerError::InvalidConfig(format!(
            "time index out of bounds: idx={idx}, len={}",
            times.len()
        ))
        .into()
    })
}

fn build_range_identity(
    data: &DataContainer,
    bar_range: (usize, usize),
) -> Result<((i64, i64), i64, f64, f64, usize), QuantError> {
    let base_times = extract_base_times(data)?;
    let start = *base_times
        .first()
        .ok_or_else(|| OptimizerError::InvalidConfig("base times empty".into()))?;
    let end = *base_times
        .last()
        .ok_or_else(|| OptimizerError::InvalidConfig("base times empty".into()))?;
    let span_ms = end - start;
    let span_days = span_ms as f64 / MS_PER_DAY;
    let span_months = span_days / DAYS_PER_MONTH;
    let bars = bar_range.1 - bar_range.0;
    Ok(((start, end), span_ms, span_days, span_months, bars))
}

fn extract_base_times(data: &DataContainer) -> Result<Vec<i64>, QuantError> {
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| OptimizerError::NoData)?;
    let time_col = base_df.column("time")?.i64()?;

    let mut out = Vec::with_capacity(time_col.len());
    for v in time_col.into_iter() {
        let ts = v.ok_or_else(|| {
            OptimizerError::InvalidConfig("base time column contains null".into())
        })?;
        out.push(ts);
    }
    Ok(out)
}

fn assert_time_strictly_increasing(times: &[i64]) -> Result<(), QuantError> {
    if times.is_empty() {
        return Err(OptimizerError::InvalidConfig("stitched time is empty".into()).into());
    }
    for i in 1..times.len() {
        if times[i] <= times[i - 1] {
            return Err(OptimizerError::InvalidConfig(format!(
                "stitched time must be strictly increasing: idx={} {} <= {}",
                i,
                times[i],
                times[i - 1]
            ))
            .into());
        }
    }
    Ok(())
}

fn validate_window_capital_series(backtest_df: &DataFrame) -> Result<(), QuantError> {
    let equity = backtest_df.column("equity")?.f64()?;
    if equity.is_empty() {
        return Err(OptimizerError::InvalidConfig("test equity is empty".into()).into());
    }
    for (idx, v) in equity.into_iter().enumerate() {
        let value = v.unwrap_or(f64::NAN);
        validate_capital_value(value, idx)?;
    }
    Ok(())
}

fn validate_capital_value(v: f64, idx: usize) -> Result<(), QuantError> {
    if !v.is_finite() {
        return Err(
            OptimizerError::InvalidConfig(format!("equity non-finite at idx={idx}: {v}")).into(),
        );
    }
    if v < 0.0 {
        return Err(
            OptimizerError::InvalidConfig(format!("equity negative at idx={idx}: {v}")).into(),
        );
    }
    Ok(())
}

fn build_injected_signals_for_window(
    signals_df: &DataFrame,
    backtest_df: &DataFrame,
    transition_len: usize,
    test_len: usize,
) -> Result<(DataFrame, bool), QuantError> {
    if transition_len < 2 {
        return Err(OptimizerError::InvalidConfig(
            "transition_len must be >= 2 for boundary signal injection".into(),
        )
        .into());
    }
    if test_len < 2 {
        return Err(OptimizerError::InvalidConfig(
            "test_len must be >= 2 for boundary signal injection".into(),
        )
        .into());
    }

    let expected_len = transition_len + test_len;
    if signals_df.height() != expected_len || backtest_df.height() != expected_len {
        return Err(OptimizerError::InvalidConfig(format!(
            "eval length mismatch: signals={}, backtest={}, expected={}",
            signals_df.height(),
            backtest_df.height(),
            expected_len
        ))
        .into());
    }

    let mut entry_long = bool_vec_from_column(signals_df, "entry_long")?;
    let mut exit_long = bool_vec_from_column(signals_df, "exit_long")?;
    let mut entry_short = bool_vec_from_column(signals_df, "entry_short")?;
    let mut exit_short = bool_vec_from_column(signals_df, "exit_short")?;

    // 中文注释：过渡期开仓钳制是强制规则，先清零整个 transition 段进场信号。
    for i in 0..transition_len {
        entry_long[i] = false;
        entry_short[i] = false;
    }

    let transition_exit_idx = transition_len - 2;
    let test_exit_idx = transition_len + test_len - 2;

    // 中文注释：离场注入采用全平语义，不依赖当前方向。
    exit_long[transition_exit_idx] = true;
    exit_short[transition_exit_idx] = true;
    exit_long[test_exit_idx] = true;
    exit_short[test_exit_idx] = true;

    let transition_last_idx = transition_len - 1;
    let cross_side = detect_cross_boundary_side(backtest_df, transition_last_idx)?;
    if let Some(ref side) = cross_side {
        // 中文注释：跨边界持仓只允许同向进场。
        match side {
            CrossSide::Long => {
                entry_long[transition_last_idx] = true;
                entry_short[transition_last_idx] = false;
            }
            CrossSide::Short => {
                entry_long[transition_last_idx] = false;
                entry_short[transition_last_idx] = true;
            }
        }
    }

    let mut out = signals_df.clone();
    out.with_column(Series::new("entry_long".into(), entry_long))?;
    out.with_column(Series::new("exit_long".into(), exit_long))?;
    out.with_column(Series::new("entry_short".into(), entry_short))?;
    out.with_column(Series::new("exit_short".into(), exit_short))?;
    Ok((out, cross_side.is_some()))
}

fn bool_vec_from_column(df: &DataFrame, col_name: &str) -> Result<Vec<bool>, QuantError> {
    let col = df.column(col_name).map_err(|_| {
        OptimizerError::InvalidConfig(format!("signals missing required column: {col_name}"))
    })?;
    let ca = col.bool().map_err(|_| {
        OptimizerError::InvalidConfig(format!("signals column must be bool: {col_name}"))
    })?;
    Ok(ca.into_iter().map(|v| v.unwrap_or(false)).collect())
}

enum CrossSide {
    Long,
    Short,
}

fn detect_cross_boundary_side(
    backtest_df: &DataFrame,
    boundary_idx: usize,
) -> Result<Option<CrossSide>, QuantError> {
    let entry_long = backtest_df.column("entry_long_price")?.f64()?;
    let exit_long = backtest_df.column("exit_long_price")?.f64()?;
    let entry_short = backtest_df.column("entry_short_price")?.f64()?;
    let exit_short = backtest_df.column("exit_short_price")?.f64()?;

    let el = entry_long.get(boundary_idx).unwrap_or(f64::NAN);
    let xl = exit_long.get(boundary_idx).unwrap_or(f64::NAN);
    let es = entry_short.get(boundary_idx).unwrap_or(f64::NAN);
    let xs = exit_short.get(boundary_idx).unwrap_or(f64::NAN);

    let long_cross = !el.is_nan() && xl.is_nan();
    let short_cross = !es.is_nan() && xs.is_nan();

    if long_cross && short_cross {
        return Err(OptimizerError::InvalidConfig(format!(
            "cross-boundary side conflict at idx={boundary_idx}: both long and short active"
        ))
        .into());
    }
    if long_cross {
        return Ok(Some(CrossSide::Long));
    }
    if short_cross {
        return Ok(Some(CrossSide::Short));
    }
    Ok(None)
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
