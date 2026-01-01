use super::super::risk_price_calc::{
    calc_tsl_atr_price, calc_tsl_pct_price, get_tsl_anchor, update_anchor_since_entry,
    update_price_one_direction, Direction,
};
use super::super::tsl_psar::{update_tsl_psar, TslPsarParams};
use crate::backtest_engine::backtester::state::backtest_state::BacktestState;
use crate::types::BacktestParams;

impl<'a> BacktestState<'a> {
    /// 更新 Risk 阈值（仅更新 TSL，SL/TP 在 gap_check 中已初始化）
    pub(super) fn update_risk_thresholds(
        &mut self,
        params: &BacktestParams,
        is_first_entry: bool,
        direction: Direction,
    ) {
        // SL/TP 已在 gap_check 初始化，这里无需重复

        // 仅在后续更新时才更新 TSL（is_first_entry 时已在 gap_check 初始化）
        if !is_first_entry {
            // 检查跟踪止损 (PCT & ATR)
            self.update_tsl_thresholds(params, direction);

            // 检查 PSAR 跟踪止损
            self.update_tsl_psar_thresholds(params, direction);
        }
    }

    /// 更新跟踪止损阈值（仅更新，初始化在 gap_check 完成）
    pub(super) fn update_tsl_thresholds(&mut self, params: &BacktestParams, direction: Direction) {
        // 如果 TSL PCT 和 ATR 都无效，直接返回
        if !params.is_tsl_pct_param_valid() && !params.is_tsl_atr_param_valid() {
            return;
        }

        // 1. 计算当前锚点（使用 prev_bar 避免未来数据泄露）
        // 注意：prev_bar 是 bar[i-1]，在 bar[i] 开盘时已知
        let current_anchor = get_tsl_anchor(
            self.prev_bar.close,
            self.prev_bar.low,
            self.prev_bar.high,
            params.tsl_anchor_mode,
            direction,
        );

        // 获取历史锚点（自进场以来的最值）
        let prev_anchor = self
            .risk_state
            .anchor_since_entry(direction)
            .expect("anchor_since_entry should be initialized in gap_check");

        // 比较当前锚点和历史锚点，取更优值
        let (anchor, anchor_updated) =
            update_anchor_since_entry(current_anchor, prev_anchor, direction);

        // 更新锚点状态
        if params.is_tsl_pct_param_valid() || params.is_tsl_atr_param_valid() {
            self.risk_state
                .set_anchor_since_entry(direction, Some(anchor));
        }

        // 2. 计算 TSL 价格
        // PCT TSL
        if params.is_tsl_pct_param_valid() {
            let tsl_pct = params.tsl_pct.as_ref().unwrap().value;
            let calculated_tsl_price = calc_tsl_pct_price(anchor, tsl_pct, direction);
            let old_price = self.risk_state.tsl_pct_price(direction);
            let new_price = update_price_one_direction(old_price, calculated_tsl_price, direction);
            self.risk_state.set_tsl_pct_price(direction, new_price);
        }

        // ATR TSL
        if params.is_tsl_atr_param_valid() {
            // 使用 prev_bar.atr (Signal Bar ATR) 以避免未来函数

            if let Some(atr) = self.prev_bar.atr {
                let tsl_atr = params.tsl_atr.as_ref().unwrap().value;
                let calculated_tsl_price = calc_tsl_atr_price(anchor, atr, tsl_atr, direction);

                // 判断是否应该更新 TSL 价格
                let should_update = if params.tsl_atr_tight {
                    true // tight 模式：每根K线都尝试更新
                } else {
                    anchor_updated // 非 tight 模式：只有锚点更新时才更新
                };

                if should_update {
                    let old_price = self.risk_state.tsl_atr_price(direction);
                    let new_price =
                        update_price_one_direction(old_price, calculated_tsl_price, direction);
                    self.risk_state.set_tsl_atr_price(direction, new_price);
                }
            }
        }
    }

    /// 更新 PSAR 跟踪止损阈值（仅更新，初始化在 gap_check 完成）
    /// 使用 prev_bar 和 prev_prev_bar 避免未来数据泄露
    pub(super) fn update_tsl_psar_thresholds(
        &mut self,
        params: &BacktestParams,
        direction: Direction,
    ) {
        if !params.is_tsl_psar_param_valid() {
            return;
        }

        // 获取 prev_prev_bar (bar[i-2])
        let prev_prev_bar = match self.get_bar(2) {
            Some(bar) => bar,
            None => return, // 数据不足，跳过
        };

        let psar_params = TslPsarParams {
            af0: params.tsl_psar_af0.as_ref().unwrap().value,
            af_step: params.tsl_psar_af_step.as_ref().unwrap().value,
            max_af: params.tsl_psar_max_af.as_ref().unwrap().value,
        };

        if let Some(old_state) = self.risk_state.tsl_psar_state(direction) {
            // 使用 prev_bar 和 prev_prev_bar 避免未来数据泄露
            let (new_state, psar_price) = update_tsl_psar(
                old_state,
                self.prev_bar.high, // 当前已知的最新 bar (bar[i-1])
                self.prev_bar.low,
                self.prev_bar.close,
                prev_prev_bar.high, // bar[i-2]
                prev_prev_bar.low,
                prev_prev_bar.close,
                direction,
                &psar_params,
                params.tsl_anchor_mode,
            );

            self.risk_state
                .set_tsl_psar_price(direction, Some(psar_price));
            self.risk_state
                .set_tsl_psar_state(direction, Some(new_state));
        }
    }
}
