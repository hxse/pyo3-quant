use super::super::risk_price_calc::{
    is_sl_triggered, is_tp_triggered, is_tsl_triggered, Direction,
};
use super::super::trigger_price_utils::{switch_prices_in_bar, switch_prices_next_bar};
use super::RiskTriggerResult;
use crate::backtest_engine::backtester::state::backtest_state::BacktestState;
use crate::types::BacktestParams;

impl<'a> BacktestState<'a> {
    /// 检查触发条件
    pub(super) fn check_risk_triggers(
        &self,
        params: &BacktestParams,
        direction: Direction,
    ) -> RiskTriggerResult {
        let is_long = match direction {
            Direction::Long => true,
            Direction::Short => false,
        };
        let (sl_in_bar, tp_in_bar) = switch_prices_in_bar(&self.current_bar, is_long);
        let (sl_next_bar, tp_next_bar) = switch_prices_next_bar(&self.current_bar, params, is_long);

        let price_for_sl = if params.sl_exit_in_bar {
            sl_in_bar
        } else {
            sl_next_bar
        };

        let price_for_tp = if params.tp_exit_in_bar {
            tp_in_bar
        } else {
            tp_next_bar
        };

        let sl_pct_price = self.risk_state.sl_pct_price(direction);
        let sl_atr_price = self.risk_state.sl_atr_price(direction);
        let tp_pct_price = self.risk_state.tp_pct_price(direction);
        let tp_atr_price = self.risk_state.tp_atr_price(direction);
        let tsl_pct_price = self.risk_state.tsl_pct_price(direction);
        let tsl_atr_price = self.risk_state.tsl_atr_price(direction);
        let tsl_psar_price = self.risk_state.tsl_psar_price(direction);

        // 检查 SL
        let sl_pct_triggered = is_sl_triggered(price_for_sl, sl_pct_price, direction);
        let sl_atr_triggered = is_sl_triggered(price_for_sl, sl_atr_price, direction);

        //检查 TP
        let tp_pct_triggered = is_tp_triggered(price_for_tp, tp_pct_price, direction);
        let tp_atr_triggered = is_tp_triggered(price_for_tp, tp_atr_price, direction);

        // 检查 TSL
        let price_for_tsl = super::super::trigger_price_utils::get_tsl_check_price(
            &self.current_bar,
            params,
            is_long,
        );
        let tsl_pct_triggered = is_tsl_triggered(price_for_tsl, tsl_pct_price, direction);
        let tsl_atr_triggered = is_tsl_triggered(price_for_tsl, tsl_atr_price, direction);
        let tsl_psar_triggered = is_tsl_triggered(price_for_tsl, tsl_psar_price, direction);

        RiskTriggerResult {
            sl_pct_triggered,
            sl_atr_triggered,
            tp_pct_triggered,
            tp_atr_triggered,
            tsl_pct_triggered,
            tsl_atr_triggered,
            tsl_psar_triggered,
        }
    }
}
