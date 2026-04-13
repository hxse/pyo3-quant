use crate::types::{IndicatorResults, PerformanceMetrics};
use polars::prelude::DataFrame;

#[allow(dead_code)]
#[derive(Debug, Clone)]
pub enum PipelineRequest {
    ScratchToIndicator,
    ScratchToSignalsStopStageOnly,
    ScratchToSignalsAllCompletedStages,
    ScratchToBacktestStopStageOnly,
    ScratchToBacktestAllCompletedStages,
    ScratchToPerformanceStopStageOnly,
    ScratchToPerformanceAllCompletedStages,
    SignalsToBacktestStopStageOnly {
        signals: DataFrame,
    },
    SignalsToBacktestAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
    },
    SignalsToPerformanceStopStageOnly {
        signals: DataFrame,
    },
    SignalsToPerformanceAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
    },
    BacktestToPerformanceStopStageOnly {
        backtest: DataFrame,
    },
    BacktestToPerformanceAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
    },
}

#[derive(Debug, Clone)]
pub enum PipelineOutput {
    IndicatorsOnly {
        indicators_raw: IndicatorResults,
    },
    SignalsOnly {
        signals: DataFrame,
    },
    IndicatorsSignals {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
    },
    BacktestOnly {
        backtest: DataFrame,
    },
    IndicatorsSignalsBacktest {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
    },
    PerformanceOnly {
        performance: PerformanceMetrics,
    },
    IndicatorsSignalsBacktestPerformance {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
        performance: PerformanceMetrics,
    },
}
