use crate::data_conversion::input::settings::ExecutionStage;
use crate::data_conversion::output::PerformanceMetrics;
use crate::data_conversion::ProcessedSettings;
use polars::prelude::*;

use std::collections::HashMap;

pub fn optimize_memory_by_stage(
    settings: &ProcessedSettings,
    indicator_dfs: Option<HashMap<String, Vec<DataFrame>>>,
    signals: Option<DataFrame>,
    backtest: Option<DataFrame>,
    performance: Option<PerformanceMetrics>,
) -> (
    Option<HashMap<String, Vec<DataFrame>>>,
    Option<DataFrame>,
    Option<DataFrame>,
    Option<PerformanceMetrics>,
) {
    let stop_stage = settings.execution_stage;

    if settings.return_only_final {
        match stop_stage {
            ExecutionStage::Indicator => (indicator_dfs, None, None, None),
            ExecutionStage::Signals => (None, signals, None, None),
            ExecutionStage::Backtest => (None, None, backtest, None),
            ExecutionStage::Performance => (None, None, None, performance),
        }
    } else {
        // 情况二：保留直到目标阶段为止的所有结果 (累进式 match)
        match stop_stage {
            ExecutionStage::Indicator => (indicator_dfs, None, None, None),
            ExecutionStage::Signals => (indicator_dfs, signals, None, None),
            ExecutionStage::Backtest => (indicator_dfs, signals, backtest, None),
            ExecutionStage::Performance => (indicator_dfs, signals, backtest, performance),
        }
    }
}
