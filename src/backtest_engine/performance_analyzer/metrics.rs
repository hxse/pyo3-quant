use crate::types::PerformanceMetric;
use polars::prelude::*;

/// 计算年化收益指标
pub fn calculate_annualized_return(total_return_pct: f64, time_span_years: f64) -> f64 {
    if time_span_years > 0.0 {
        (1.0 + total_return_pct).powf(1.0 / time_span_years) - 1.0
    } else {
        total_return_pct
    }
}

/// 计算风险指标（夏普、索提诺、卡尔马及其原始版本）
///
/// # 参数
/// * `metric` - 要计算的指标类型
/// * `annualization_factor` - 年化因子（每年K线数）
/// * `rf` - 无风险利率
/// * `mean_ret` - 平均收益率（每K线）
/// * `std_ret` - 收益率标准差（每K线）
/// * `annualized_return` - 年化收益率
/// * `total_return_pct` - 总回报率（非年化）
/// * `returns` - 收益率序列
/// * `current_drawdown` - 回撤序列
pub fn calculate_risk_metrics(
    metric: &PerformanceMetric,
    annualization_factor: f64,
    rf: f64,
    mean_ret: f64,
    std_ret: f64,
    annualized_return: f64,
    total_return_pct: f64,
    returns: &ChunkedArray<Float64Type>,
    current_drawdown: &ChunkedArray<Float64Type>,
) -> f64 {
    match metric {
        // === 年化版本 ===
        PerformanceMetric::SharpeRatio => {
            if std_ret > 0.0 {
                (mean_ret * annualization_factor - rf) / (std_ret * annualization_factor.sqrt())
            } else {
                0.0
            }
        }
        PerformanceMetric::SortinoRatio => {
            let downside_returns: Vec<f64> =
                returns.into_iter().flatten().filter(|&r| r < 0.0).collect();

            if !downside_returns.is_empty() {
                let sum_sq: f64 = downside_returns.iter().map(|&r| r * r).sum();
                let downside_std = (sum_sq / (returns.len() as f64)).sqrt();
                if downside_std > 0.0 {
                    (mean_ret * annualization_factor - rf)
                        / (downside_std * annualization_factor.sqrt())
                } else {
                    0.0
                }
            } else {
                0.0
            }
        }
        PerformanceMetric::CalmarRatio => {
            let mdd = current_drawdown.max().unwrap_or(0.0).abs();
            if mdd > 0.0 {
                annualized_return / mdd
            } else {
                0.0
            }
        }
        // === 非年化版本（Raw）===
        PerformanceMetric::SharpeRatioRaw => {
            // 非年化夏普 = (平均收益 - 无风险) / 标准差
            // 注意：无风险利率也需要调整为每K线的无风险收益
            let rf_per_bar = rf / annualization_factor;
            if std_ret > 0.0 {
                (mean_ret - rf_per_bar) / std_ret
            } else {
                0.0
            }
        }
        PerformanceMetric::SortinoRatioRaw => {
            let rf_per_bar = rf / annualization_factor;
            let downside_returns: Vec<f64> =
                returns.into_iter().flatten().filter(|&r| r < 0.0).collect();

            if !downside_returns.is_empty() {
                let sum_sq: f64 = downside_returns.iter().map(|&r| r * r).sum();
                let downside_std = (sum_sq / (returns.len() as f64)).sqrt();
                if downside_std > 0.0 {
                    (mean_ret - rf_per_bar) / downside_std
                } else {
                    0.0
                }
            } else {
                0.0
            }
        }
        PerformanceMetric::CalmarRatioRaw => {
            // 非年化卡尔马 = 总回报率 / 最大回撤
            let mdd = current_drawdown.max().unwrap_or(0.0).abs();
            if mdd > 0.0 {
                total_return_pct / mdd
            } else {
                0.0
            }
        }
        _ => 0.0,
    }
}
