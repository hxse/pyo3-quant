use crate::data_conversion::output::PerformanceMetrics;
use crate::data_conversion::ProcessedConfig;
use polars::prelude::*;

pub fn optimize_memory_if_needed(
    config: &ProcessedConfig,
    indicators_df: DataFrame,
    signals_df: DataFrame,
    backtest_result_df: DataFrame,
    performance: PerformanceMetrics,
) -> (
    Option<DataFrame>,
    Option<DataFrame>,
    Option<DataFrame>,
    PerformanceMetrics,
) {
    if config.is_only_performance {
        // 清空所有DataFrame,只保留绩效数据
        (None, None, None, performance)
    } else {
        // 保留所有数据
        (
            Some(indicators_df),
            Some(signals_df),
            Some(backtest_result_df),
            performance,
        )
    }
}
