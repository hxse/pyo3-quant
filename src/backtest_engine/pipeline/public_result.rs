use crate::backtest_engine::data_ops::build_result_pack;
use crate::error::QuantError;
use crate::types::{DataPack, ResultPack};

use super::types::PipelineOutput;

pub fn build_public_result_pack(
    data: &DataPack,
    output: PipelineOutput,
) -> Result<ResultPack, QuantError> {
    match output {
        PipelineOutput::IndicatorsOnly { indicators_raw } => {
            build_result_pack(data, Some(indicators_raw), None, None, None)
        }
        PipelineOutput::SignalsOnly { signals } => {
            build_result_pack(data, None, Some(signals), None, None)
        }
        PipelineOutput::IndicatorsSignals {
            indicators_raw,
            signals,
        } => build_result_pack(data, Some(indicators_raw), Some(signals), None, None),
        PipelineOutput::BacktestOnly { backtest } => {
            build_result_pack(data, None, None, Some(backtest), None)
        }
        PipelineOutput::IndicatorsSignalsBacktest {
            indicators_raw,
            signals,
            backtest,
        } => build_result_pack(
            data,
            Some(indicators_raw),
            Some(signals),
            Some(backtest),
            None,
        ),
        PipelineOutput::PerformanceOnly { performance } => {
            build_result_pack(data, None, None, None, Some(performance))
        }
        PipelineOutput::IndicatorsSignalsBacktestPerformance {
            indicators_raw,
            signals,
            backtest,
            performance,
        } => build_result_pack(
            data,
            Some(indicators_raw),
            Some(signals),
            Some(backtest),
            Some(performance),
        ),
    }
}
