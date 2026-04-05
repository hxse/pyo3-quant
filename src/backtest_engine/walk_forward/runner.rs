use crate::backtest_engine::data_ops::build_warmup_requirements;
use crate::backtest_engine::walk_forward::data_splitter::build_window_indices;
use crate::backtest_engine::walk_forward::injection::CrossSide;
use crate::backtest_engine::walk_forward::stitch::build_stitched_artifact;
use crate::backtest_engine::walk_forward::window_runner::execute_window;
use crate::error::{OptimizerError, QuantError};
use crate::types::WalkForwardConfig;
use crate::types::{
    DataPack, ExecutionStage, SettingContainer, SingleParamSet, TemplateContainer,
    WalkForwardResult, WindowArtifact,
};
use pyo3::prelude::*;

/// 运行向前滚动优化（完整产物返回）
pub fn run_walk_forward(
    data_pack: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError> {
    let source_keys = data_pack.source.keys().cloned().collect::<Vec<_>>();
    let warmup_requirements = build_warmup_requirements(
        &source_keys,
        &data_pack.base_data_key,
        &param.indicators,
        config.ignore_indicator_warmup,
        &param.backtest,
    )?;
    let plan = build_window_indices(
        data_pack,
        config,
        &warmup_requirements.required_warmup_by_key,
    )?;
    if plan.windows.is_empty() {
        return Err(
            OptimizerError::InvalidConfig("No walk-forward windows generated".into()).into(),
        );
    }

    // 中文注释：训练优化阶段统一只保留最终绩效，降低并发内存占用。
    let mut optimize_settings = settings.clone();
    optimize_settings.execution_stage = ExecutionStage::Performance;
    optimize_settings.return_only_final = true;

    let mut completed_windows = Vec::new();
    let mut window_results: Vec<WindowArtifact> = Vec::new();
    let mut prev_top_k: Option<Vec<Vec<f64>>> = None;
    let mut prev_test_last_position: Option<CrossSide> = None;

    for window in &plan.windows {
        let window_output = execute_window(
            data_pack,
            param,
            template,
            settings,
            &optimize_settings,
            config,
            window,
            prev_top_k.as_deref(),
            prev_test_last_position,
        )?;
        prev_top_k = Some(window_output.next_top_k);
        prev_test_last_position = window_output.next_test_last_position;
        window_results.push(window_output.completed_window.public_artifact.clone());
        completed_windows.push(window_output.completed_window);
    }

    let stitched_result =
        build_stitched_artifact(data_pack, param, config, &plan.windows, &completed_windows)?;

    Ok(WalkForwardResult {
        optimize_metric: config.optimizer_config.optimize_metric,
        window_results,
        stitched_result,
    })
}

use pyo3_stub_gen::derive::*;

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.walk_forward",
    python = r#"
import pyo3_quant

def run_walk_forward(
    data: pyo3_quant.DataPack,
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
    data: DataPack,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    config: WalkForwardConfig,
) -> PyResult<WalkForwardResult> {
    run_walk_forward(&data, &param, &template, &engine_settings, &config).map_err(|e| e.into())
}
