use super::super::backtest_state::BacktestState;
use super::risk_price_calc::{
    calc_sl_atr_price, calc_sl_pct_price, calc_tp_atr_price, calc_tp_pct_price, calc_tsl_atr_price,
    calc_tsl_pct_price, get_sl_anchor, get_tp_anchor, get_tsl_anchor,
};
use super::tsl_psar::{init_tsl_psar, TslPsarParams};
use super::Direction;
use crate::data_conversion::BacktestParams;

impl<'a> BacktestState<'a> {
    /// 检查价格是否跳空穿过阈值，如果安全则存储
    ///
    /// # 参数
    /// * `price` - 计算出的风控价格
    /// * `direction` - 持仓方向
    /// * `is_stop_loss` - true=止损/跟踪止损, false=止盈
    /// * `setter` - 用于存储价格的函数
    ///
    /// # 返回
    /// * `true` - 检查通过（安全）
    /// * `false` - 检查失败（跳空穿过）
    fn check_gap_and_store(
        &mut self,
        price: f64,
        direction: Direction,
        is_stop_loss: bool,
        setter: impl FnOnce(&mut Self, Direction, Option<f64>),
    ) -> bool {
        let open = self.current_bar.open;

        // 检查是否跳空穿过
        let is_safe = match (direction, is_stop_loss) {
            (Direction::Long, true) => open >= price, // 多头止损：开盘 >= 止损价
            (Direction::Long, false) => open <= price, // 多头止盈：开盘 <= 止盈价
            (Direction::Short, true) => open <= price, // 空头止损：开盘 <= 止损价
            (Direction::Short, false) => open >= price, // 空头止盈：开盘 >= 止盈价
        };

        if is_safe {
            setter(self, direction, Some(price));
        }

        is_safe
    }

    /// [Gap Protection] 检查进场安全性并初始化风控价格
    ///
    /// 在确认进场前，检查进场 Bar 的开盘价是否已经穿过基于信号 Bar 计算出的风控价格。
    /// 检查范围：SL PCT/ATR、TP PCT/ATR、TSL PCT/ATR、TSL PSAR（共7种）
    /// 如果检查通过，直接存储计算出的风控价格，避免重复计算。
    pub fn init_entry_with_safety_check(
        &mut self,
        params: &BacktestParams,
        direction: Direction,
    ) -> bool {
        // 1. 检查 SL PCT
        if params.is_sl_pct_param_valid() {
            let sl_pct = params.sl_pct.as_ref().unwrap().value;
            let anchor = get_sl_anchor(
                self.prev_bar.close,
                self.prev_bar.low,
                self.prev_bar.high,
                params.sl_anchor_mode,
                direction,
            );
            let sl_price = calc_sl_pct_price(anchor, sl_pct, direction);

            let is_safe =
                self.check_gap_and_store(sl_price, direction, true, |state, dir, price| {
                    state.risk_state.set_sl_pct_price(dir, price);
                });
            if !is_safe {
                return false;
            }
        }

        // 2. 检查 SL ATR
        if params.is_sl_atr_param_valid() {
            if let Some(atr) = self.prev_bar.atr {
                let sl_atr_k = params.sl_atr.as_ref().unwrap().value;
                let anchor = get_sl_anchor(
                    self.prev_bar.close,
                    self.prev_bar.low,
                    self.prev_bar.high,
                    params.sl_anchor_mode,
                    direction,
                );
                let sl_price = calc_sl_atr_price(anchor, atr, sl_atr_k, direction);

                let is_safe =
                    self.check_gap_and_store(sl_price, direction, true, |state, dir, price| {
                        state.risk_state.set_sl_atr_price(dir, price);
                    });
                if !is_safe {
                    return false;
                }
            }
        }

        // 3. 检查 TP PCT
        if params.is_tp_pct_param_valid() {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            let anchor = get_tp_anchor(
                self.prev_bar.close,
                self.prev_bar.low,
                self.prev_bar.high,
                params.tp_anchor_mode,
                direction,
            );
            let tp_price = calc_tp_pct_price(anchor, tp_pct, direction);

            let is_safe =
                self.check_gap_and_store(tp_price, direction, false, |state, dir, price| {
                    state.risk_state.set_tp_pct_price(dir, price);
                });
            if !is_safe {
                return false;
            }
        }

        // 4. 检查 TP ATR
        if params.is_tp_atr_param_valid() {
            if let Some(atr) = self.prev_bar.atr {
                let tp_atr_k = params.tp_atr.as_ref().unwrap().value;
                let anchor = get_tp_anchor(
                    self.prev_bar.close,
                    self.prev_bar.low,
                    self.prev_bar.high,
                    params.tp_anchor_mode,
                    direction,
                );
                let tp_price = calc_tp_atr_price(anchor, atr, tp_atr_k, direction);

                let is_safe =
                    self.check_gap_and_store(tp_price, direction, false, |state, dir, price| {
                        state.risk_state.set_tp_atr_price(dir, price);
                    });
                if !is_safe {
                    return false;
                }
            }
        }

        // 5. 检查 TSL PCT
        if params.is_tsl_pct_param_valid() {
            let tsl_pct = params.tsl_pct.as_ref().unwrap().value;
            let anchor = get_tsl_anchor(
                self.prev_bar.close,
                self.prev_bar.low,
                self.prev_bar.high,
                params.tsl_anchor_mode,
                direction,
            );
            let tsl_price = calc_tsl_pct_price(anchor, tsl_pct, direction);

            let is_safe =
                self.check_gap_and_store(tsl_price, direction, true, |state, dir, price| {
                    state.risk_state.set_tsl_pct_price(dir, price);
                    // 用 anchor 初始化（仅首次）
                    state.risk_state.set_anchor_since_entry(dir, Some(anchor));
                });
            if !is_safe {
                return false;
            }
        }

        // 6. 检查 TSL ATR
        if params.is_tsl_atr_param_valid() {
            if let Some(atr) = self.prev_bar.atr {
                let tsl_atr_k = params.tsl_atr.as_ref().unwrap().value;
                let anchor = get_tsl_anchor(
                    self.prev_bar.close,
                    self.prev_bar.low,
                    self.prev_bar.high,
                    params.tsl_anchor_mode,
                    direction,
                );
                let tsl_price = calc_tsl_atr_price(anchor, atr, tsl_atr_k, direction);

                let is_safe =
                    self.check_gap_and_store(tsl_price, direction, true, |state, dir, price| {
                        state.risk_state.set_tsl_atr_price(dir, price);
                        // 用 anchor 初始化（仅首次）
                        state.risk_state.set_anchor_since_entry(dir, Some(anchor));
                    });
                if !is_safe {
                    return false;
                }
            }
        }

        // 7. 检查 TSL PSAR
        if params.is_tsl_psar_param_valid() {
            if let Some(bar_i_minus_2) = self.get_bar(2) {
                let psar_params = TslPsarParams {
                    af0: params.tsl_psar_af0.as_ref().unwrap().value,
                    af_step: params.tsl_psar_af_step.as_ref().unwrap().value,
                    max_af: params.tsl_psar_max_af.as_ref().unwrap().value,
                };

                let (psar_state, psar_price) = init_tsl_psar(
                    bar_i_minus_2.high,
                    bar_i_minus_2.low,
                    bar_i_minus_2.close,
                    self.prev_bar.high,
                    self.prev_bar.low,
                    self.prev_bar.close,
                    direction,
                    &psar_params,
                    params.tsl_anchor_mode,
                );

                match direction {
                    Direction::Long => {
                        if self.current_bar.open < psar_price {
                            return false;
                        }
                    }
                    Direction::Short => {
                        if self.current_bar.open > psar_price {
                            return false;
                        }
                    }
                }

                // ✅ 检查通过，存储价格和状态
                self.risk_state
                    .set_tsl_psar_price(direction, Some(psar_price));
                self.risk_state
                    .set_tsl_psar_state(direction, Some(psar_state));
            }
        }

        // ✅ 所有检查通过
        true
    }
}
