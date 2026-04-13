use crate::backtest_engine::backtester;
use crate::backtest_engine::indicators::calculate_indicators;
use crate::backtest_engine::performance_analyzer::analyze_performance;
use crate::backtest_engine::signal_generator::generate_signals;
use crate::error::QuantError;
use crate::types::{
    DataPack, PerformanceMetrics, SingleParamSet, TemplateContainer,
};

use super::types::{PipelineOutput, PipelineRequest};
use super::validation::{
    normalize_indicator_results, validate_frame_height, validate_raw_indicators,
};

pub fn execute_single_pipeline(
    data: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
    request: PipelineRequest,
) -> Result<PipelineOutput, QuantError> {
    match request {
        PipelineRequest::ScratchToIndicator => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            Ok(PipelineOutput::IndicatorsOnly { indicators_raw })
        }
        PipelineRequest::ScratchToSignalsStopStageOnly => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            Ok(PipelineOutput::SignalsOnly { signals })
        }
        PipelineRequest::ScratchToSignalsAllCompletedStages => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            Ok(PipelineOutput::IndicatorsSignals {
                indicators_raw,
                signals,
            })
        }
        PipelineRequest::ScratchToBacktestStopStageOnly => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            Ok(PipelineOutput::BacktestOnly { backtest })
        }
        PipelineRequest::ScratchToBacktestAllCompletedStages => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            Ok(PipelineOutput::IndicatorsSignalsBacktest {
                indicators_raw,
                signals,
                backtest,
            })
        }
        PipelineRequest::ScratchToPerformanceStopStageOnly => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::PerformanceOnly { performance })
        }
        PipelineRequest::ScratchToPerformanceAllCompletedStages => {
            let indicators_raw =
                normalize_indicator_results(calculate_indicators(data, &param.indicators)?);
            let signals = generate_signals(
                data,
                &indicators_raw,
                &param.signal,
                &template.signal,
            )?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::IndicatorsSignalsBacktestPerformance {
                indicators_raw,
                signals,
                backtest,
                performance,
            })
        }
        PipelineRequest::SignalsToBacktestStopStageOnly { signals } => {
            validate_frame_height(data, &signals, "PipelineRequest.signals")?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            Ok(PipelineOutput::BacktestOnly { backtest })
        }
        PipelineRequest::SignalsToBacktestAllCompletedStages {
            indicators_raw,
            signals,
        } => {
            validate_raw_indicators(data, &indicators_raw)?;
            validate_frame_height(data, &signals, "PipelineRequest.signals")?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            Ok(PipelineOutput::IndicatorsSignalsBacktest {
                indicators_raw,
                signals,
                backtest,
            })
        }
        PipelineRequest::SignalsToPerformanceStopStageOnly { signals } => {
            validate_frame_height(data, &signals, "PipelineRequest.signals")?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::PerformanceOnly { performance })
        }
        PipelineRequest::SignalsToPerformanceAllCompletedStages {
            indicators_raw,
            signals,
        } => {
            validate_raw_indicators(data, &indicators_raw)?;
            validate_frame_height(data, &signals, "PipelineRequest.signals")?;
            let backtest = backtester::run_backtest(data, &signals, &param.backtest)?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::IndicatorsSignalsBacktestPerformance {
                indicators_raw,
                signals,
                backtest,
                performance,
            })
        }
        PipelineRequest::BacktestToPerformanceStopStageOnly { backtest } => {
            validate_frame_height(data, &backtest, "PipelineRequest.backtest")?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::PerformanceOnly { performance })
        }
        PipelineRequest::BacktestToPerformanceAllCompletedStages {
            indicators_raw,
            signals,
            backtest,
        } => {
            validate_raw_indicators(data, &indicators_raw)?;
            validate_frame_height(data, &signals, "PipelineRequest.signals")?;
            validate_frame_height(data, &backtest, "PipelineRequest.backtest")?;
            let performance = analyze_performance(data, &backtest, &param.performance)?;
            Ok(PipelineOutput::IndicatorsSignalsBacktestPerformance {
                indicators_raw,
                signals,
                backtest,
                performance,
            })
        }
    }
}

pub fn evaluate_param_set(
    data: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
) -> Result<PerformanceMetrics, QuantError> {
    let output = execute_single_pipeline(
        data,
        param,
        template,
        PipelineRequest::ScratchToPerformanceStopStageOnly,
    )?;
    match output {
        PipelineOutput::PerformanceOnly { performance } => Ok(performance),
        _ => Err(QuantError::InvalidParam(
            "evaluate_param_set(...) 必须返回 PerformanceOnly".to_string(),
        )),
    }
}
