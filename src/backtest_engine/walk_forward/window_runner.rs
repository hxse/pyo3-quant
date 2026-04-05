use crate::backtest_engine::data_ops::{
    build_result_pack, extract_active, slice_data_pack_by_base_window, strip_indicator_time_columns,
};
use crate::backtest_engine::execute_single_backtest;
use crate::backtest_engine::optimizer::run_optimization;
use crate::backtest_engine::performance_analyzer::analyze_performance;
use crate::backtest_engine::utils::BacktestContext;
use crate::backtest_engine::walk_forward::data_splitter::WindowPlan;
use crate::backtest_engine::walk_forward::injection::{
    build_carry_only_signals_for_window, build_final_signals_for_window, detect_last_bar_position,
    CrossSide,
};
use crate::backtest_engine::walk_forward::time_ranges::build_window_time_ranges;
use crate::error::{OptimizerError, QuantError};
use crate::types::{
    DataPack, ExecutionStage, ResultPack, SettingContainer, SingleParamSet, TemplateContainer,
    WalkForwardConfig, WindowArtifact, WindowMeta,
};
use polars::prelude::*;

pub(crate) struct CompletedWindow {
    pub public_artifact: WindowArtifact,
    pub test_active_result: ResultPack,
}

pub(crate) struct WindowExecutionOutput {
    pub completed_window: CompletedWindow,
    pub next_top_k: Vec<Vec<f64>>,
    pub next_test_last_position: Option<CrossSide>,
}

/// 中文注释：单窗执行统一收敛到这里，runner 只负责窗口遍历与 stitched 调度。
pub(crate) fn execute_window(
    data_pack: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    optimize_settings: &SettingContainer,
    config: &WalkForwardConfig,
    window: &WindowPlan,
    prev_top_k: Option<&[Vec<f64>]>,
    prev_test_last_position: Option<CrossSide>,
) -> Result<WindowExecutionOutput, QuantError> {
    let train_pack_data = slice_data_pack_by_base_window(data_pack, &window.indices.train_pack)?;

    let mut opt_config = config.optimizer_config.clone();
    // 中文注释：固定启用上一窗 top-k 先验。
    if let Some(priors) = prev_top_k {
        if !priors.is_empty() {
            opt_config.init_samples = Some(priors.to_vec());
        }
    }

    let train_result = run_optimization(
        &train_pack_data,
        param,
        template,
        optimize_settings,
        &opt_config,
    )?;

    let test_pack_data = slice_data_pack_by_base_window(data_pack, &window.indices.test_pack)?;
    let test_warmup_bars = test_pack_data.ranges[&test_pack_data.base_data_key].warmup_bars;
    let test_active_bars = test_pack_data.ranges[&test_pack_data.base_data_key].active_bars;

    // 中文注释：第一次评估只跑到 Signals，作为跨窗注入前的正式信号基线。
    let mut eval_settings = settings.clone();
    eval_settings.execution_stage = ExecutionStage::Signals;
    eval_settings.return_only_final = false;

    let first_eval_result = execute_single_backtest(
        &test_pack_data,
        &train_result.best_params,
        template,
        &eval_settings,
    )?;

    let first_eval_signals_df = first_eval_result.signals.clone().ok_or_else(|| {
        OptimizerError::SamplingFailed(
            "Walk-forward first evaluation requires full signals dataframe".into(),
        )
    })?;
    let first_eval_raw_indicators = first_eval_result
        .indicators
        .as_ref()
        .map(strip_indicator_time_columns)
        .transpose()?;

    let carry_only_signals_df = build_carry_only_signals_for_window(
        &first_eval_signals_df,
        test_warmup_bars,
        test_active_bars,
        prev_test_last_position,
    )?;

    // 中文注释：自然回放只注入 carry，不追加尾部强平；跨窗状态只能从这条链读取。
    let mut natural_ctx = BacktestContext::new();
    natural_ctx.indicator_dfs = first_eval_raw_indicators.clone();
    natural_ctx.signals_df = Some(carry_only_signals_df.clone());
    natural_ctx.execute_backtest_if_needed(
        ExecutionStage::Backtest,
        false,
        &test_pack_data,
        &train_result.best_params.backtest,
    )?;
    let natural_test_pack_result = build_result_pack(
        &test_pack_data,
        None,
        None,
        natural_ctx.backtest_df.clone(),
        None,
    )?;
    let natural_backtest_df = natural_test_pack_result.backtest.as_ref().ok_or_else(|| {
        OptimizerError::SamplingFailed(
            "Walk-forward natural test ResultPack requires full backtest dataframe".into(),
        )
    })?;
    let next_test_last_position = detect_last_bar_position(natural_backtest_df)?;
    let has_cross_boundary_position = next_test_last_position.is_some();

    let final_signals_df =
        build_final_signals_for_window(&carry_only_signals_df, test_warmup_bars, test_active_bars)?;

    // 中文注释：正式窗口结果在自然回放基础上追加尾部强平，仍复用第一次评估出的 indicators。
    let mut final_ctx = BacktestContext::new();
    final_ctx.indicator_dfs = first_eval_raw_indicators;
    final_ctx.signals_df = Some(final_signals_df);
    final_ctx.execute_backtest_if_needed(
        ExecutionStage::Backtest,
        false,
        &test_pack_data,
        &train_result.best_params.backtest,
    )?;
    let final_eval_result =
        final_ctx.into_result_pack(&test_pack_data, false, ExecutionStage::Backtest)?;
    // 中文注释：ResultPack 持有的是带 time 的正式 indicators；
    // 窗口内部回到 ResultPack builder 时，必须显式降级回 raw indicators。
    let raw_indicators = final_eval_result
        .indicators
        .as_ref()
        .map(strip_indicator_time_columns)
        .transpose()?;
    let full_signals = final_eval_result.signals.clone();
    let full_backtest = final_eval_result.backtest.clone();
    let test_backtest_df = full_backtest.as_ref().ok_or_else(|| {
        OptimizerError::SamplingFailed(
            "Walk-forward test ResultPack requires full backtest dataframe".into(),
        )
    })?;
    validate_window_capital_series(test_backtest_df)?;
    let test_metrics = analyze_performance(&test_pack_data, test_backtest_df, &param.performance)?;
    let test_pack_result = build_result_pack(
        &test_pack_data,
        raw_indicators,
        full_signals,
        full_backtest,
        Some(test_metrics),
    )?;
    let (_test_active_data, test_active_result) =
        extract_active(&test_pack_data, &test_pack_result)?;

    let time_ranges = build_window_time_ranges(&train_pack_data, &test_pack_data)?;
    let meta = WindowMeta {
        window_id: window.window_idx,
        best_params: train_result.best_params,
        has_cross_boundary_position,
        test_active_base_row_range: window.indices.test_active_base_row_range,
        train_warmup_time_range: time_ranges.train_warmup_time_range,
        train_active_time_range: time_ranges.train_active_time_range,
        train_pack_time_range: time_ranges.train_pack_time_range,
        test_warmup_time_range: time_ranges.test_warmup_time_range,
        test_active_time_range: time_ranges.test_active_time_range,
        test_pack_time_range: time_ranges.test_pack_time_range,
    };

    let artifact = WindowArtifact {
        train_pack_data,
        test_pack_data,
        test_pack_result: test_pack_result.clone(),
        meta,
    };

    let next_top_k = train_result
        .top_k_samples
        .iter()
        .map(|sample| sample.values.clone())
        .collect::<Vec<_>>();

    Ok(WindowExecutionOutput {
        completed_window: CompletedWindow {
            public_artifact: artifact,
            test_active_result,
        },
        next_top_k,
        next_test_last_position,
    })
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
