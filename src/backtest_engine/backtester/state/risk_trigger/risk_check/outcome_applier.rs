use super::super::risk_price_calc::Direction;
use super::super::trigger_price_utils::calculate_risk_price;
use super::RiskTriggerResult;
use crate::backtest_engine::backtester::state::backtest_state::BacktestState;
use crate::data_conversion::BacktestParams;

impl<'a> BacktestState<'a> {
    /// 应用 Risk 结果
    pub(super) fn apply_risk_outcome(
        &mut self,
        params: &BacktestParams,
        direction: Direction,
        result: RiskTriggerResult,
    ) {
        let should_exit = result.any_triggered();

        if should_exit {
            let is_long = match direction {
                Direction::Long => true,
                Direction::Short => false,
            };

            let sl_pct = self.risk_state.sl_pct_price(direction);
            let sl_atr = self.risk_state.sl_atr_price(direction);
            let tp_pct = self.risk_state.tp_pct_price(direction);
            let tp_atr = self.risk_state.tp_atr_price(direction);
            let tsl_pct = self.risk_state.tsl_pct_price(direction);
            let tsl_atr = self.risk_state.tsl_atr_price(direction);
            let tsl_psar = self.risk_state.tsl_psar_price(direction);

            // 根据触发状态过滤价格，避免未触发的优良价格掩盖已触发的离场价格
            let sl_pct_eff = if result.sl_pct_triggered {
                sl_pct
            } else {
                None
            };
            let sl_atr_eff = if result.sl_atr_triggered {
                sl_atr
            } else {
                None
            };
            let tp_pct_eff = if result.tp_pct_triggered {
                tp_pct
            } else {
                None
            };
            let tp_atr_eff = if result.tp_atr_triggered {
                tp_atr
            } else {
                None
            };
            let tsl_pct_eff = if result.tsl_pct_triggered {
                tsl_pct
            } else {
                None
            };
            let tsl_atr_eff = if result.tsl_atr_triggered {
                tsl_atr
            } else {
                None
            };
            let tsl_psar_eff = if result.tsl_psar_triggered {
                tsl_psar
            } else {
                None
            };

            // 判断是否为 In-Bar 模式触发 (仅 SL/TP 受 exit_in_bar 影响)
            let is_in_bar_exit = (result.sl_triggered() && params.sl_exit_in_bar)
                || (result.tp_triggered() && params.tp_exit_in_bar);

            let exit_price = if is_in_bar_exit {
                // 1. In-Bar 模式：只包含触发的 SL/TP 价格。
                // TSL/PSAR 始终为 Next-Bar，不参与 In-Bar 的悲观结算价格计算。
                // 如果某一边(SL或TP)配置为Next-Bar，即使触发了(Next-Bar触发)，也不应该参与In-Bar的结算。
                calculate_risk_price(
                    sl_pct_eff.filter(|_| params.sl_exit_in_bar),
                    sl_atr_eff.filter(|_| params.sl_exit_in_bar),
                    tp_pct_eff.filter(|_| params.tp_exit_in_bar),
                    tp_atr_eff.filter(|_| params.tp_exit_in_bar),
                    None,
                    None,
                    None,
                    is_long,
                )
            } else {
                // 2. Next-Bar 模式：包含所有触发的价格（SL/TP/TSL/PSAR）
                // 虽然最终離場價通常是下一根 K 線開盤價，但在這裡記錄最先觸發的那個價格作為參考
                calculate_risk_price(
                    sl_pct_eff,
                    sl_atr_eff,
                    tp_pct_eff,
                    tp_atr_eff,
                    tsl_pct_eff,
                    tsl_atr_eff,
                    tsl_psar_eff,
                    is_long,
                )
            };

            self.risk_state.set_exit_price(direction, exit_price);

            self.risk_state.in_bar_direction = if is_in_bar_exit {
                match direction {
                    Direction::Long => 1,
                    Direction::Short => -1,
                }
            } else {
                0
            };
        } else {
            self.risk_state.set_exit_price(direction, None);
            self.risk_state.in_bar_direction = 0;
        }
    }
}
