use super::super::{backtest_state::BacktestState, position_state::Position};
use super::price_utils::{calculate_risk_price, switch_prices_in_bar, switch_prices_next_bar};
use crate::data_conversion::BacktestParams;

impl BacktestState {
    /// 判断是否应该触发空头离场（止损/止盈/跟踪止损）
    /// 返回 (should_exit, exit_price)
    pub(crate) fn risk_exit_short(
        &mut self,
        params: &BacktestParams,
        current_atr: Option<f64>,
    ) -> (bool, Option<f64>) {
        // 统一检查 ATR 是否有效
        let is_atr_valid = current_atr.is_some() && !current_atr.unwrap().is_nan();

        // 方法调用的时候检查过None了
        let entry_price = self.action.entry_short_price.unwrap();

        // 检查百分比止损
        if params.is_sl_pct_param_valid() {
            // 方法调用时已经检查过, 必然是isLong, 这里只需要区分hold就行了
            if self.action.current_position != Position::HoldShort {
                let sl_pct = params.sl_pct.as_ref().unwrap().value;
                let calculated_sl_price = entry_price * (1.0 + sl_pct);
                self.risk_state.sl_pct_price = Some(calculated_sl_price);
            }
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() {
            if self.action.current_position != Position::HoldShort {
                let tp_pct = params.tp_pct.as_ref().unwrap().value;
                let calculated_tp_price = entry_price * (1.0 - tp_pct);
                self.risk_state.tp_pct_price = Some(calculated_tp_price);
            }
        }

        // 检查pct跟踪止损
        if params.is_tsl_pct_param_valid() {
            let lowest = if self.action.current_position != Position::HoldShort {
                entry_price
            } else {
                self.risk_state
                    .lowest_since_entry
                    .unwrap_or(entry_price)
                    .min(self.current_bar.low)
            };

            let tsl_pct = params.tsl_pct.as_ref().unwrap().value;
            let calculated_tsl_price = lowest * (1.0 + tsl_pct);
            self.risk_state.lowest_since_entry = Some(lowest);
            self.risk_state.tsl_pct_price = Some(calculated_tsl_price);
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid {
            if self.action.current_position != Position::HoldShort {
                let sl_atr = params.sl_atr.as_ref().unwrap().value;
                let calculated_sl_price = entry_price + current_atr.unwrap() * sl_atr;
                self.risk_state.sl_atr_price = Some(calculated_sl_price);
            }
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid {
            if self.action.current_position != Position::HoldShort {
                let tp_atr = params.tp_atr.as_ref().unwrap().value;
                let calculated_tp_price = entry_price - current_atr.unwrap() * tp_atr;
                self.risk_state.tp_atr_price = Some(calculated_tp_price);
            }
        }

        // 检查atr跟踪止损
        if params.is_tsl_atr_param_valid() {
            let lowest = if self.action.current_position != Position::HoldShort {
                entry_price
            } else {
                self.risk_state
                    .lowest_since_entry
                    .unwrap_or(entry_price)
                    .min(self.current_bar.low)
            };

            let tsl_atr = params.tsl_atr.as_ref().unwrap().value;
            let calculated_tsl_price = lowest + current_atr.unwrap() * tsl_atr;
            self.risk_state.lowest_since_entry = Some(lowest);
            self.risk_state.tsl_atr_price = Some(calculated_tsl_price);
        }

        // 检查是否触发离场条件，并记录哪些条件触发了
        // 1. 获取用于检查 SL 和 TP 的价格
        let (price_for_sl, price_for_tp) = if params.exit_in_bar {
            switch_prices_in_bar(&self.current_bar, false)
        } else {
            switch_prices_next_bar(&self.current_bar, params, false)
        };

        // 2. 检查 SL 和 TP 是否触发
        let sl_pct_triggered = self.risk_state.sl_pct_price.is_some()
            && price_for_sl >= self.risk_state.sl_pct_price.unwrap();
        let sl_atr_triggered = self.risk_state.sl_atr_price.is_some()
            && price_for_sl >= self.risk_state.sl_atr_price.unwrap();
        let sl_triggered = sl_pct_triggered || sl_atr_triggered;

        let tp_pct_triggered = self.risk_state.tp_pct_price.is_some()
            && price_for_tp <= self.risk_state.tp_pct_price.unwrap();
        let tp_atr_triggered = self.risk_state.tp_atr_price.is_some()
            && price_for_tp <= self.risk_state.tp_atr_price.unwrap();
        let tp_triggered = tp_pct_triggered || tp_atr_triggered;

        // 3. 检查 TSL 是否触发
        // TSL 总是使用 next_bar 逻辑的价格
        let (price_for_tsl, _) = switch_prices_next_bar(&self.current_bar, params, false);
        let tsl_pct_triggered = self.risk_state.tsl_pct_price.is_some()
            && price_for_tsl >= self.risk_state.tsl_pct_price.unwrap();
        let tsl_atr_triggered = self.risk_state.tsl_atr_price.is_some()
            && price_for_tsl >= self.risk_state.tsl_atr_price.unwrap();
        let tsl_triggered = tsl_pct_triggered || tsl_atr_triggered;

        // 4. 确定最终结果
        let should_exit = sl_triggered || tp_triggered || tsl_triggered;

        // 根据触发的条件计算离场价格
        let exit_price = if should_exit && params.exit_in_bar {
            if sl_triggered && tp_triggered {
                // 止损和止盈都触发，选择最保守的（最大价格）
                calculate_risk_price(
                    self.risk_state.sl_pct_price,
                    self.risk_state.sl_atr_price,
                    self.risk_state.tp_pct_price,
                    self.risk_state.tp_atr_price,
                    false,
                )
            } else if sl_triggered {
                // 只有止损触发
                calculate_risk_price(
                    self.risk_state.sl_pct_price,
                    self.risk_state.sl_atr_price,
                    None,
                    None,
                    false,
                )
            } else if tp_triggered {
                // 只有止盈触发
                calculate_risk_price(
                    None,
                    None,
                    self.risk_state.tp_pct_price,
                    self.risk_state.tp_atr_price,
                    false,
                )
            } else {
                // tsl不返回触发价
                None
            }
        } else {
            // 只有exit_in_bar才返回触发价
            None
        };

        (should_exit, exit_price)
    }
}
