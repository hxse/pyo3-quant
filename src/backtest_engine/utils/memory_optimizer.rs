use crate::types::IndicatorResults;
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
