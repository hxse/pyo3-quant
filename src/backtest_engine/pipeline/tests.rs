use super::{
    compile_public_setting_to_request, validate_mode_settings, PipelineRequest,
};
use crate::types::{ArtifactRetention, ExecutionStage, SettingContainer};

#[test]
fn test_compile_public_setting_to_request_contract() {
    let indicator_all = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Indicator,
        ArtifactRetention::AllCompletedStages,
    ))
    .expect("Indicator + AllCompletedStages 应成功");
    assert!(matches!(indicator_all, PipelineRequest::ScratchToIndicator));

    let indicator_stop = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Indicator,
        ArtifactRetention::StopStageOnly,
    ))
    .expect("Indicator + StopStageOnly 应成功");
    assert!(matches!(indicator_stop, PipelineRequest::ScratchToIndicator));

    let signals_all = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Signals,
        ArtifactRetention::AllCompletedStages,
    ))
    .expect("Signals + AllCompletedStages 应成功");
    assert!(matches!(
        signals_all,
        PipelineRequest::ScratchToSignalsAllCompletedStages
    ));

    let signals_stop = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Signals,
        ArtifactRetention::StopStageOnly,
    ))
    .expect("Signals + StopStageOnly 应成功");
    assert!(matches!(
        signals_stop,
        PipelineRequest::ScratchToSignalsStopStageOnly
    ));

    let backtest_all = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Backtest,
        ArtifactRetention::AllCompletedStages,
    ))
    .expect("Backtest + AllCompletedStages 应成功");
    assert!(matches!(
        backtest_all,
        PipelineRequest::ScratchToBacktestAllCompletedStages
    ));

    let backtest_stop = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Backtest,
        ArtifactRetention::StopStageOnly,
    ))
    .expect("Backtest + StopStageOnly 应成功");
    assert!(matches!(
        backtest_stop,
        PipelineRequest::ScratchToBacktestStopStageOnly
    ));

    let performance_all = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Performance,
        ArtifactRetention::AllCompletedStages,
    ))
    .expect("Performance + AllCompletedStages 应成功");
    assert!(matches!(
        performance_all,
        PipelineRequest::ScratchToPerformanceAllCompletedStages
    ));

    let performance_stop = compile_public_setting_to_request(&SettingContainer::new(
        ExecutionStage::Performance,
        ArtifactRetention::StopStageOnly,
    ))
    .expect("Performance + StopStageOnly 应成功");
    assert!(matches!(
        performance_stop,
        PipelineRequest::ScratchToPerformanceStopStageOnly
    ));
}

#[test]
fn test_validate_mode_settings_contract() {
    let valid_settings = SettingContainer::new(
        ExecutionStage::Performance,
        ArtifactRetention::StopStageOnly,
    );
    validate_mode_settings(
        &valid_settings,
        "run_optimization(...)",
        ExecutionStage::Performance,
        ArtifactRetention::StopStageOnly,
    )
    .expect("合法 mode settings 应通过");

    let invalid_settings = SettingContainer::new(
        ExecutionStage::Performance,
        ArtifactRetention::AllCompletedStages,
    );
    assert!(validate_mode_settings(
        &invalid_settings,
        "run_optimization(...)",
        ExecutionStage::Performance,
        ArtifactRetention::StopStageOnly,
    )
    .is_err());
}
