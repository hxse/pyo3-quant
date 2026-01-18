use super::super::backtest_state::BacktestState;
use super::risk_price_calc::{
    calc_sl_atr_price, calc_sl_pct_price, calc_tp_atr_price, calc_tp_pct_price, calc_tsl_atr_price,
    calc_tsl_pct_price, get_sl_anchor, get_tp_anchor, get_tsl_anchor,
};
use super::tsl_psar::{init_tsl_psar, TslPsarParams};
use super::Direction;
use crate::backtest_engine::indicators::psar::psar_core::PsarState;
use crate::types::BacktestParams;

#[derive(Default)]
struct GapCheckResult {
    sl_pct_price: Option<f64>,
    sl_atr_price: Option<f64>,
    tp_pct_price: Option<f64>,
    tp_atr_price: Option<f64>,
    tsl_pct_price: Option<f64>,
    tsl_pct_anchor: Option<f64>,
    tsl_atr_price: Option<f64>,
    tsl_atr_anchor: Option<f64>,
    tsl_psar_price: Option<f64>,
    tsl_psar_state: Option<PsarState>,
}

/// 检查价格是否跳空穿过阈值
///
/// # 返回
/// * `true` - 检查通过（安全）
/// * `false` - 检查失败（跳空穿过）
fn check_gap(open: f64, price: f64, direction: Direction, is_stop_loss: bool) -> bool {
    match (direction, is_stop_loss) {
        (Direction::Long, true) => open > price, // 多头止损：开盘 > 止损价
        (Direction::Long, false) => open < price, // 多头止盈：开盘 < 止盈价
        (Direction::Short, true) => open < price, // 空头止损：开盘 < 止损价
        (Direction::Short, false) => open > price, // 空头止盈：开盘 > 止盈价
    }
}

impl<'a> BacktestState<'a> {
    /// 应用检查结果到 risk_state
    fn apply_gap_check_result(&mut self, direction: Direction, result: GapCheckResult) {
        if let Some(price) = result.sl_pct_price {
            self.risk_state.set_sl_pct_price(direction, Some(price));
        }
        if let Some(price) = result.sl_atr_price {
            self.risk_state.set_sl_atr_price(direction, Some(price));
        }
        if let Some(price) = result.tp_pct_price {
            self.risk_state.set_tp_pct_price(direction, Some(price));
        }
        if let Some(price) = result.tp_atr_price {
            self.risk_state.set_tp_atr_price(direction, Some(price));
        }
        if let Some(price) = result.tsl_pct_price {
            self.risk_state.set_tsl_pct_price(direction, Some(price));
            self.risk_state
                .set_anchor_since_entry(direction, result.tsl_pct_anchor);
        }
        if let Some(price) = result.tsl_atr_price {
            self.risk_state.set_tsl_atr_price(direction, Some(price));
            self.risk_state
                .set_anchor_since_entry(direction, result.tsl_atr_anchor);
        }
        if let Some(price) = result.tsl_psar_price {
            self.risk_state.set_tsl_psar_price(direction, Some(price));
        }
        if let Some(state) = result.tsl_psar_state {
            self.risk_state.set_tsl_psar_state(direction, Some(state));
        }
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
        let mut result = GapCheckResult::default();
        let open = self.current_bar.open;

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
            let price = calc_sl_pct_price(anchor, sl_pct, direction);

            if !check_gap(open, price, direction, true) {
                return false;
            }
            result.sl_pct_price = Some(price);
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
                let price = calc_sl_atr_price(anchor, atr, sl_atr_k, direction);

                if !check_gap(open, price, direction, true) {
                    return false;
                }
                result.sl_atr_price = Some(price);
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
            let price = calc_tp_pct_price(anchor, tp_pct, direction);

            if !check_gap(open, price, direction, false) {
                return false;
            }
            result.tp_pct_price = Some(price);
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
                let price = calc_tp_atr_price(anchor, atr, tp_atr_k, direction);

                if !check_gap(open, price, direction, false) {
                    return false;
                }
                result.tp_atr_price = Some(price);
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
            let price = calc_tsl_pct_price(anchor, tsl_pct, direction);

            if !check_gap(open, price, direction, true) {
                return false;
            }
            result.tsl_pct_price = Some(price);
            result.tsl_pct_anchor = Some(anchor);
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
                let price = calc_tsl_atr_price(anchor, atr, tsl_atr_k, direction);

                if !check_gap(open, price, direction, true) {
                    return false;
                }
                result.tsl_atr_price = Some(price);
                result.tsl_atr_anchor = Some(anchor);
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
                        if open < psar_price {
                            return false;
                        }
                    }
                    Direction::Short => {
                        if open > psar_price {
                            return false;
                        }
                    }
                }

                result.tsl_psar_price = Some(psar_price);
                result.tsl_psar_state = Some(psar_state);
            }
        }

        // ✅ 所有检查通过，统一存储
        self.apply_gap_check_result(direction, result);
        true
    }
}
