use super::super::current_bar_data::CurrentBarData;
use crate::data_conversion::BacktestParams;

/// 计算离场价格的工具函数
///
/// # 参数
/// * `sl_pct_price` - 百分比止损价格
/// * `sl_atr_price` - ATR止损价格
/// * `tp_pct_price` - 百分比止盈价格
/// * `tp_atr_price` - ATR止盈价格
/// * `is_long_position` - 是否为多头仓位
///
/// # 返回值
/// * `Option<f64>` - 如果有有效价格则返回最合适的离场价格，否则返回 None
pub fn calculate_risk_price(
    sl_pct_price: Option<f64>,
    sl_atr_price: Option<f64>,
    tp_pct_price: Option<f64>,
    tp_atr_price: Option<f64>,
    tsl_pct_price: Option<f64>,
    tsl_atr_price: Option<f64>,
    tsl_psar_price: Option<f64>,
    is_long_position: bool,
) -> Option<f64> {
    // 收集所有有效价格
    let prices: Vec<f64> = [
        sl_pct_price,
        sl_atr_price,
        tp_pct_price,
        tp_atr_price,
        tsl_pct_price,
        tsl_atr_price,
        tsl_psar_price,
    ]
    .into_iter()
    .flatten()
    .collect();

    if prices.is_empty() {
        return None;
    }

    // 根据仓位类型选择合适的价格
    if is_long_position {
        // 多头仓位：选择最小的价格（最保守的离场点）
        Some(prices.iter().fold(f64::MAX, |a, &b| a.min(b)))
    } else {
        // 空头仓位：选择最大的价格（最保守的离场点）
        Some(prices.iter().fold(f64::MIN, |a, &b| a.max(b)))
    }
}

/// 获取 next_bar 模式下用于检查离场条件的价格
///
/// # 参数
/// * `current_bar` - 当前K线数据
/// * `params` - 回测参数
/// * `is_long_position` - 是否为多头仓位
///
/// # 返回值
/// * `(f64, f64)` - (用于检查止损的价格, 用于检查止盈的价格)
pub fn switch_prices_next_bar(
    current_bar: &CurrentBarData,
    params: &BacktestParams,
    is_long_position: bool,
) -> (f64, f64) {
    if params.use_extrema_for_exit {
        if is_long_position {
            // 多头：用最低价检查止损，用最高价检查止盈
            (current_bar.low, current_bar.high)
        } else {
            // 空头：用最高价检查止损，用最低价检查止盈
            (current_bar.high, current_bar.low)
        }
    } else {
        // 不使用 fallback，都用收盘价
        (current_bar.close, current_bar.close)
    }
}

/// 获取 in_bar 模式下用于检查离场条件的价格
///
/// # 参数
/// * `current_bar` - 当前K线数据
/// * `is_long_position` - 是否为多头仓位
///
/// # 返回值
/// * `(f64, f64)` - (用于检查止损的价格, 用于检查止盈的价格)
pub fn switch_prices_in_bar(current_bar: &CurrentBarData, is_long_position: bool) -> (f64, f64) {
    if is_long_position {
        // 多头：用最低价检查止损，用最高价检查止盈
        (current_bar.low, current_bar.high)
    } else {
        // 空头：用最高价检查止损，用最低价检查止盈
        (current_bar.high, current_bar.low)
    }
}
