use crate::backtest_engine::data_ops::{extract_active, slice_data_pack_by_base_window};
use crate::backtest_engine::{
    build_public_result_pack, execute_single_pipeline, PipelineOutput, PipelineRequest,
};
use crate::backtest_engine::optimizer::run_optimization;
use crate::backtest_engine::walk_forward::data_splitter::WindowPlan;
use crate::backtest_engine::walk_forward::injection::{
    build_carry_only_signals_for_window, build_final_signals_for_window, detect_last_bar_position,
    CrossSide,
};
use crate::backtest_engine::walk_forward::time_ranges::build_window_time_ranges;
use crate::error::{OptimizerError, QuantError};
use crate::types::{
    DataPack, ResultPack, SettingContainer, SingleParamSet, TemplateContainer,
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
    _settings: &SettingContainer,
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

    let first_eval_output = execute_single_pipeline(
        &test_pack_data,
        &train_result.best_params,
        template,
        PipelineRequest::ScratchToSignalsAllCompletedStages,
    )?;
    let (first_eval_raw_indicators, first_eval_signals_df) = match first_eval_output {
        PipelineOutput::IndicatorsSignals {
            indicators_raw,
            signals,
        } => (indicators_raw, signals),
        _ => {
            return Err(OptimizerError::SamplingFailed(
                "Walk-forward first evaluation 必须返回 IndicatorsSignals".into(),
            )
            .into())
        }
    };

    let carry_only_signals_df = build_carry_only_signals_for_window(
        &first_eval_signals_df,
        test_warmup_bars,
        test_active_bars,
        prev_test_last_position,
    )?;

    // 中文注释：自然回放只注入 carry，不追加尾部强平；跨窗状态只能从这条链读取。
    let natural_output = execute_single_pipeline(
        &test_pack_data,
        &train_result.best_params,
        template,
        PipelineRequest::SignalsToBacktestStopStageOnly {
            signals: carry_only_signals_df.clone(),
        },
    )?;
    let natural_backtest_df = match natural_output {
        PipelineOutput::BacktestOnly { ref backtest } => backtest,
        _ => {
            return Err(OptimizerError::SamplingFailed(
                "Walk-forward natural replay 必须返回 BacktestOnly".into(),
            )
            .into())
        }
    };
    let next_test_last_position = detect_last_bar_position(natural_backtest_df)?;
    let has_cross_boundary_position = next_test_last_position.is_some();

    let final_signals_df =
        build_final_signals_for_window(&carry_only_signals_df, test_warmup_bars, test_active_bars)?;

    // 中文注释：正式窗口结果在自然回放基础上追加尾部强平，仍复用第一次评估出的 indicators。
    let final_output = execute_single_pipeline(
        &test_pack_data,
        &train_result.best_params,
        template,
        PipelineRequest::SignalsToPerformanceAllCompletedStages {
            indicators_raw: first_eval_raw_indicators,
            signals: final_signals_df,
        },
    )?;
    let test_backtest_df = match &final_output {
        PipelineOutput::IndicatorsSignalsBacktestPerformance { backtest, .. } => backtest,
        _ => {
            return Err(OptimizerError::SamplingFailed(
                "Walk-forward final evaluation 必须返回 IndicatorsSignalsBacktestPerformance"
                    .into(),
            )
            .into())
        }
    };
    validate_window_capital_series(test_backtest_df)?;
    let test_pack_result = build_public_result_pack(&test_pack_data, final_output)?;
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
