use super::backtest_state::BacktestState;
use super::current_bar_data::CurrentBarData;
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
fn calculate_exit_price(
    sl_pct_price: Option<f64>,
    sl_atr_price: Option<f64>,
    tp_pct_price: Option<f64>,
    tp_atr_price: Option<f64>,
    is_long_position: bool,
) -> Option<f64> {
    // 收集所有有效价格
    let prices: Vec<f64> = [sl_pct_price, sl_atr_price, tp_pct_price, tp_atr_price]
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
fn get_next_bar_prices(
    current_bar: &CurrentBarData,
    params: &BacktestParams,
    is_long_position: bool,
) -> (f64, f64) {
    if params.exit_in_bar_fallback {
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
fn get_in_bar_prices(current_bar: &CurrentBarData, is_long_position: bool) -> (f64, f64) {
    if is_long_position {
        // 多头：用最低价检查止损，用最高价检查止盈
        (current_bar.low, current_bar.high)
    } else {
        // 空头：用最高价检查止损，用最低价检查止盈
        (current_bar.high, current_bar.low)
    }
}

impl BacktestState {
    /// 判断是否应该触发多头离场（止损/止盈/跟踪止损）
    /// 返回 (should_exit, exit_price)
    pub(super) fn should_exit_long(
        &self,
        current_bar: &CurrentBarData,
        params: &BacktestParams,
        current_atr: Option<f64>,
    ) -> (bool, Option<f64>) {
        // 内联条件判断：如果不是多头仓位或者没有入场价格，直接返回false
        if !self.position.is_long() || self.entry_price.is_none() {
            return (false, None);
        }

        let entry_price = self.entry_price.unwrap();

        // 统一检查 ATR 是否有效, (其实前面已经检查过了, 这里是保守检查)
        let is_atr_valid = current_atr.is_some() && !current_atr.unwrap().is_nan();

        // 收集所有可能的止损/止盈价格（分为6个变量）
        let mut sl_pct_price: Option<f64> = None;
        let mut sl_atr_price: Option<f64> = None;
        let mut tp_pct_price: Option<f64> = None;
        let mut tp_atr_price: Option<f64> = None;
        let mut tsl_pct_price: Option<f64> = None;
        let mut tsl_atr_price: Option<f64> = None;

        // 检查百分比止损
        if params.is_sl_pct_param_valid() {
            let sl_pct = params.sl_pct.as_ref().unwrap().value;
            let calculated_sl_price = entry_price * (1.0 - sl_pct);
            sl_pct_price = Some(calculated_sl_price);
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            let calculated_tp_price = entry_price * (1.0 + tp_pct);
            tp_pct_price = Some(calculated_tp_price);
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid {
            let sl_atr = params.sl_atr.as_ref().unwrap().value;
            let calculated_sl_price = entry_price - current_atr.unwrap() * sl_atr;
            sl_atr_price = Some(calculated_sl_price);
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid {
            let tp_atr = params.tp_atr.as_ref().unwrap().value;
            let calculated_tp_price = entry_price + current_atr.unwrap() * tp_atr;
            tp_atr_price = Some(calculated_tp_price);
        }

        // 检查跟踪止损
        if (params.is_tsl_pct_param_valid() || params.is_tsl_atr_param_valid())
            && (self.current_tsl_pct_price > 0.0 || self.current_tsl_atr_price > 0.0)
        {
            //具体计算, 暂时留空
            if self.current_tsl_pct_price > 0.0 {
                tsl_pct_price = Some(self.current_tsl_pct_price);
            }
            if self.current_tsl_atr_price > 0.0 {
                tsl_atr_price = Some(self.current_tsl_atr_price);
            }
        }

        // 检查是否触发离场条件
        let should_exit = if params.exit_in_bar {
            // in_bar 模式
            let (price_for_sl, price_for_tp) = get_in_bar_prices(current_bar, true);
            (sl_pct_price.is_some() && price_for_sl <= sl_pct_price.unwrap())
                || (tp_pct_price.is_some() && price_for_tp >= tp_pct_price.unwrap())
                || (sl_atr_price.is_some() && price_for_sl <= sl_atr_price.unwrap())
                || (tp_atr_price.is_some() && price_for_tp >= tp_atr_price.unwrap())
        } else {
            // next_bar 模式
            let (price_for_sl, price_for_tp) = get_next_bar_prices(current_bar, params, true);

            (sl_pct_price.is_some() && price_for_sl <= sl_pct_price.unwrap())
                || (tp_pct_price.is_some() && price_for_tp >= tp_pct_price.unwrap())
                || (tsl_pct_price.is_some() && price_for_sl <= tsl_pct_price.unwrap())
                || (sl_atr_price.is_some() && price_for_sl <= sl_atr_price.unwrap())
                || (tp_atr_price.is_some() && price_for_tp >= tp_atr_price.unwrap())
                || (tsl_atr_price.is_some() && price_for_sl <= tsl_atr_price.unwrap())
        };

        // 返回结果和最悲观的离场价格
        let exit_price = if should_exit && params.exit_in_bar {
            calculate_exit_price(sl_pct_price, sl_atr_price, tp_pct_price, tp_atr_price, true)
        // 多头仓位
        } else {
            None
        };

        (should_exit, exit_price)
    }

    /// 判断是否应该触发空头离场（止损/止盈/跟踪止损）
    /// 返回 (should_exit, exit_price)
    pub(super) fn should_exit_short(
        &self,
        current_bar: &CurrentBarData,
        params: &BacktestParams,
        current_atr: Option<f64>,
    ) -> (bool, Option<f64>) {
        // 内联条件判断：如果不是空头仓位或者没有入场价格，直接返回false
        if !self.position.is_short() || self.entry_price.is_none() {
            return (false, None);
        }

        let entry_price = self.entry_price.unwrap();

        // 统一检查 ATR 是否有效
        let is_atr_valid = current_atr.is_some() && !current_atr.unwrap().is_nan();

        // 收集所有可能的止损/止盈价格（分为6个变量）
        let mut sl_pct_price: Option<f64> = None;
        let mut sl_atr_price: Option<f64> = None;
        let mut tp_pct_price: Option<f64> = None;
        let mut tp_atr_price: Option<f64> = None;
        let mut tsl_pct_price: Option<f64> = None;
        let mut tsl_atr_price: Option<f64> = None;

        // 检查百分比止损
        if params.is_sl_pct_param_valid() {
            let sl_pct = params.sl_pct.as_ref().unwrap().value;
            let calculated_sl_price = entry_price * (1.0 + sl_pct);
            sl_pct_price = Some(calculated_sl_price);
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            let calculated_tp_price = entry_price * (1.0 - tp_pct);
            tp_pct_price = Some(calculated_tp_price);
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid {
            let sl_atr = params.sl_atr.as_ref().unwrap().value;
            let calculated_sl_price = entry_price + current_atr.unwrap() * sl_atr;
            sl_atr_price = Some(calculated_sl_price);
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid {
            let tp_atr = params.tp_atr.as_ref().unwrap().value;
            let calculated_tp_price = entry_price - current_atr.unwrap() * tp_atr;
            tp_atr_price = Some(calculated_tp_price);
        }

        // 检查跟踪止损
        if (params.is_tsl_pct_param_valid() || params.is_tsl_atr_param_valid())
            && (self.current_tsl_pct_price > 0.0 || self.current_tsl_atr_price > 0.0)
        {
            //具体计算, 暂时留空
            if self.current_tsl_pct_price > 0.0 {
                tsl_pct_price = Some(self.current_tsl_pct_price);
            }
            if self.current_tsl_atr_price > 0.0 {
                tsl_atr_price = Some(self.current_tsl_atr_price);
            }
        }

        // 检查是否触发离场条件
        let should_exit = if params.exit_in_bar {
            // in_bar 模式 - 空头用高价触发止损，低价触发止盈
            let (price_for_sl, price_for_tp) = get_in_bar_prices(current_bar, false);
            (sl_pct_price.is_some() && price_for_sl >= sl_pct_price.unwrap())
                || (tp_pct_price.is_some() && price_for_tp <= tp_pct_price.unwrap())
                || (sl_atr_price.is_some() && price_for_sl >= sl_atr_price.unwrap())
                || (tp_atr_price.is_some() && price_for_tp <= tp_atr_price.unwrap())
        } else {
            // next_bar 模式
            let (price_for_sl, price_for_tp) = get_next_bar_prices(current_bar, params, false);

            (sl_pct_price.is_some() && price_for_sl >= sl_pct_price.unwrap())
                || (tp_pct_price.is_some() && price_for_tp <= tp_pct_price.unwrap())
                || (tsl_pct_price.is_some() && price_for_sl >= tsl_pct_price.unwrap())
                || (sl_atr_price.is_some() && price_for_sl >= sl_atr_price.unwrap())
                || (tp_atr_price.is_some() && price_for_tp <= tp_atr_price.unwrap())
                || (tsl_atr_price.is_some() && price_for_sl >= tsl_atr_price.unwrap())
        };

        // 返回结果和最小的价格
        let exit_price = if should_exit && params.exit_in_bar {
            calculate_exit_price(
                sl_pct_price,
                sl_atr_price,
                tp_pct_price,
                tp_atr_price,
                false,
            ) // 空头仓位
        } else {
            None
        };

        (should_exit, exit_price)
    }
}
