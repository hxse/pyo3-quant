mod metrics;
mod stats;

use crate::backtest_engine::utils::get_ohlcv_dataframe;
use crate::error::QuantError;
use crate::types::DataContainer;
use crate::types::{PerformanceMetric, PerformanceMetrics, PerformanceParams};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

/// 绩效分析引擎执行器
///
/// 负责根据回测结果数据（equity, drawdown, trade_pnl 等）计算一系列量化评估指标。
/// 该过程高度矢量化，利用 Polars 提高计算效率。
pub fn analyze_performance(
    processed_data: &DataContainer,
    backtest_df: &DataFrame,
    performance_params: &PerformanceParams,
) -> Result<PerformanceMetrics, QuantError> {
    let has_leading_nan_count = backtest_df
        .column("has_leading_nan")
        .ok()
        .and_then(|col| col.bool().ok())
        .map(|bool_col| bool_col.sum().unwrap_or(0));

    let mut result = HashMap::new();

    // 1. 数据准备
    // 从原始 DataContainer 获取 time 列计算时间跨度
    let ohlcv_df = get_ohlcv_dataframe(processed_data)?;
    let time = ohlcv_df.column("time")?.i64()?;

    // 提取回测输出列
    let equity = backtest_df.column("equity")?.f64()?;
    let trade_pnl_pct = backtest_df.column("trade_pnl_pct")?.f64()?;
    let current_drawdown = backtest_df.column("current_drawdown")?.f64()?;
    let entry_long = backtest_df.column("entry_long_price")?.f64()?;
    let entry_short = backtest_df.column("entry_short_price")?.f64()?;
    let total_return_pct_col = backtest_df.column("total_return_pct")?.f64()?;

    let n = backtest_df.height();
    if n < 2 {
        return Ok(result);
    }

    // 2. 时间统计与年化推断
    let time_first = time.get(0).unwrap_or(0);
    let time_last = time.get(n - 1).unwrap_or(0);
    let time_span_ms = (time_last - time_first) as f64;
    let ms_per_year = 365.25 * 24.0 * 3600.0 * 1000.0;
    let time_span_years = time_span_ms / ms_per_year;

    // 年化因子：反映样本密度
    let annualization_factor = if time_span_years > 0.0 {
        (n as f64) / time_span_years
    } else {
        1.0
    };

    // 3. 基础统计
    let initial_capital = equity.get(0).unwrap_or(1.0);
    let final_equity = equity.get(n - 1).unwrap_or(0.0);
    let total_return_pct = if initial_capital > 0.0 {
        (final_equity / initial_capital) - 1.0
    } else {
        0.0
    };

    let annualized_return = metrics::calculate_annualized_return(total_return_pct, time_span_years);
    let rf = performance_params.risk_free_rate;

    // 计算收益率序列及矩统计
    let equity_col = backtest_df.column("equity")?;
    let returns_series = (equity_col / &equity_col.shift(1))? - 1.0;
    let returns = returns_series.f64()?;
    let mean_ret = returns.mean().unwrap_or(0.0);
    let std_ret = returns.std(1).unwrap_or(0.0);

    // 4. 时长统计（持仓、空仓、回撤时长）
    let dur_stats = stats::calculate_duration_stats(n, entry_long, entry_short, current_drawdown);

    // 5. 交易细节统计
    let trade_stats = stats::calculate_trade_stats(trade_pnl_pct);

    // 6. 构造最终指标映射
    for metric in performance_params.metrics.iter() {
        let key = metric.as_str().to_string();
        let value = match metric {
            PerformanceMetric::TotalReturn => total_return_pct_col.get(n - 1).unwrap_or(0.0),
            PerformanceMetric::MaxDrawdown => current_drawdown.max().unwrap_or(0.0),
            PerformanceMetric::MaxDrawdownDuration => dur_stats.max_drawdown_duration,

            // 风险调整收益指标（年化和非年化）
            PerformanceMetric::SharpeRatio
            | PerformanceMetric::SortinoRatio
            | PerformanceMetric::CalmarRatio
            | PerformanceMetric::SharpeRatioRaw
            | PerformanceMetric::SortinoRatioRaw
            | PerformanceMetric::CalmarRatioRaw => metrics::calculate_risk_metrics(
                metric,
                annualization_factor,
                rf,
                mean_ret,
                std_ret,
                annualized_return,
                total_return_pct,
                returns,
                current_drawdown,
                trade_stats.total_trades,
            ),

            // 交易统计
            PerformanceMetric::TotalTrades => trade_stats.total_trades,
            PerformanceMetric::AvgDailyTrades => {
                let days = (time_span_years * 365.25).max(1.0);
                trade_stats.total_trades / days
            }
            PerformanceMetric::WinRate => trade_stats.win_rate,
            PerformanceMetric::ProfitLossRatio => trade_stats.profit_loss_ratio,

            // 持仓时长
            PerformanceMetric::AvgHoldingDuration => dur_stats.avg_holding_duration,
            PerformanceMetric::MaxHoldingDuration => dur_stats.max_holding_duration,
            PerformanceMetric::AvgEmptyDuration => dur_stats.avg_empty_duration,
            PerformanceMetric::MaxEmptyDuration => dur_stats.max_empty_duration,
            PerformanceMetric::MaxSafeLeverage => {
                let mdd = current_drawdown.max().unwrap_or(0.0);
                let safety = performance_params.leverage_safety_factor.unwrap_or(0.8);
                if mdd > 0.0 {
                    safety / mdd
                } else {
                    0.0
                }
            }
            PerformanceMetric::AnnualizationFactor => annualization_factor,
            PerformanceMetric::HasLeadingNanCount => {
                // 使用提前计算的 has_leading_nan 计数
                has_leading_nan_count.unwrap_or(0) as f64
            }
        };
        result.insert(key, value);
    }

    Ok(result)
}

#[pyfunction(name = "analyze_performance")]
pub fn py_analyze_performance(
    data_dict: DataContainer,
    backtest_df_py: PyDataFrame,
    performance_params: PerformanceParams,
) -> PyResult<HashMap<String, f64>> {
    // 1. 将 Python 对象转换为 Rust 类型
    let backtest_df: DataFrame = backtest_df_py.into();

    // 2. 调用原始的 analyze_performance 函数
    let result = analyze_performance(&data_dict, &backtest_df, &performance_params)?;

    // 3. PyO3 会自动将 PerformanceMetrics (HashMap<String, f64>) 转换为 Python 字典
    Ok(result)
}
