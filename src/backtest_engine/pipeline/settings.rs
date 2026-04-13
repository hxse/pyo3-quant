use crate::error::QuantError;
use crate::types::{ArtifactRetention, ExecutionStage, SettingContainer};

use super::types::PipelineRequest;

pub fn compile_public_setting_to_request(
    settings: &SettingContainer,
) -> Result<PipelineRequest, QuantError> {
    match (settings.stop_stage, settings.artifact_retention) {
        (ExecutionStage::Indicator, _) => Ok(PipelineRequest::ScratchToIndicator),
        (ExecutionStage::Signals, ArtifactRetention::StopStageOnly) => {
            Ok(PipelineRequest::ScratchToSignalsStopStageOnly)
        }
        (ExecutionStage::Signals, ArtifactRetention::AllCompletedStages) => {
            Ok(PipelineRequest::ScratchToSignalsAllCompletedStages)
        }
        (ExecutionStage::Backtest, ArtifactRetention::StopStageOnly) => {
            Ok(PipelineRequest::ScratchToBacktestStopStageOnly)
        }
        (ExecutionStage::Backtest, ArtifactRetention::AllCompletedStages) => {
            Ok(PipelineRequest::ScratchToBacktestAllCompletedStages)
        }
        (ExecutionStage::Performance, ArtifactRetention::StopStageOnly) => {
            Ok(PipelineRequest::ScratchToPerformanceStopStageOnly)
        }
        (ExecutionStage::Performance, ArtifactRetention::AllCompletedStages) => {
            Ok(PipelineRequest::ScratchToPerformanceAllCompletedStages)
        }
    }
}

pub fn validate_mode_settings(
    settings: &SettingContainer,
    mode_name: &str,
    expected_stage: ExecutionStage,
    expected_retention: ArtifactRetention,
) -> Result<(), QuantError> {
    if settings.stop_stage != expected_stage || settings.artifact_retention != expected_retention {
        return Err(QuantError::InvalidParam(format!(
            "{mode_name} 只接受 SettingContainer {{ stop_stage: {}, artifact_retention: {} }}，当前为 stop_stage={}, artifact_retention={}",
            expected_stage.as_str(),
            expected_retention.as_str(),
            settings.stop_stage.as_str(),
            settings.artifact_retention.as_str(),
        )));
    }
    Ok(())
}
