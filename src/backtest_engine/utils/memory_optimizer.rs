use crate::data_conversion::types::backtest_summary::{
    BacktestSummary, IndicatorResults, PerformanceMetrics,
};
use crate::data_conversion::types::settings::ExecutionStage;
use polars::prelude::DataFrame;

/// 在return_only_final模式下，信号计算完成后释放指标数据
pub fn maybe_release_indicators(
    return_only_final: bool,
    indicator_dfs: &mut Option<IndicatorResults>,
) {
    if return_only_final {
        drop(indicator_dfs.take()); // 直接 take() 并 drop(), 简洁高效
    }
}

/// 在return_only_final模式下，回测计算完成后释放信号数据
pub fn maybe_release_signals(return_only_final: bool, signals_df: &mut Option<DataFrame>) {
    if return_only_final {
        drop(signals_df.take()); // 直接 take() 并 drop(), 简洁高效
    }
}

/// 在return_only_final模式下，绩效计算完成后释放回测数据
pub fn maybe_release_backtest(return_only_final: bool, backtest_df: &mut Option<DataFrame>) {
    if return_only_final {
        drop(backtest_df.take()); // 直接 take() 并 drop(), 简洁高效
    }
}

/// 根据配置决定返回哪些结果
pub fn create_backtest_summary(
    return_only_final: bool,
    stop_stage: ExecutionStage,
    indicator_dfs: Option<IndicatorResults>,
    signals_df: Option<DataFrame>,
    backtest_df: Option<DataFrame>,
    performance: Option<PerformanceMetrics>,
) -> BacktestSummary {
    if return_only_final {
        // 只返回最终阶段的结果
        match stop_stage {
            ExecutionStage::None => BacktestSummary {
                indicators: None,
                signals: None,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Indicator => BacktestSummary {
                indicators: indicator_dfs,
                signals: None,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Signals => BacktestSummary {
                indicators: None,
                signals: signals_df,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Backtest => BacktestSummary {
                indicators: None,
                signals: None,
                backtest: backtest_df,
                performance: None,
            },
            ExecutionStage::Performance => BacktestSummary {
                indicators: None,
                signals: None,
                backtest: None,
                performance,
            },
        }
    } else {
        // 保留所有中间结果
        match stop_stage {
            ExecutionStage::None => BacktestSummary {
                indicators: None,
                signals: None,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Indicator => BacktestSummary {
                indicators: indicator_dfs,
                signals: None,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Signals => BacktestSummary {
                indicators: indicator_dfs,
                signals: signals_df,
                backtest: None,
                performance: None,
            },
            ExecutionStage::Backtest => BacktestSummary {
                indicators: indicator_dfs,
                signals: signals_df,
                backtest: backtest_df,
                performance: None,
            },
            ExecutionStage::Performance => BacktestSummary {
                indicators: indicator_dfs,
                signals: signals_df,
                backtest: backtest_df,
                performance,
            },
        }
    }
}
