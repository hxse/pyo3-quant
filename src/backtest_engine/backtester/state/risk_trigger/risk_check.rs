use super::super::backtest_state::BacktestState;
use super::direction::Direction;
use super::price_utils::{calculate_risk_price, switch_prices_in_bar, switch_prices_next_bar};
use super::tsl_psar::{init_tsl_psar, update_tsl_psar, TslPsarParams};
use crate::data_conversion::BacktestParams;

/// 风控触发状态详细结果
#[derive(Debug, Clone, Copy, Default)]
struct RiskTriggerResult {
    sl_pct_triggered: bool,
    sl_atr_triggered: bool,
    tp_pct_triggered: bool,
    tp_atr_triggered: bool,
    tsl_pct_triggered: bool,
    tsl_atr_triggered: bool,
    tsl_psar_triggered: bool,
}

impl RiskTriggerResult {
    /// 是否有任何止损触发
    fn sl_triggered(&self) -> bool {
        self.sl_pct_triggered || self.sl_atr_triggered
    }

    /// 是否有任何止盈触发
    fn tp_triggered(&self) -> bool {
        self.tp_pct_triggered || self.tp_atr_triggered
    }

    /// 是否有任何跟踪止损触发
    fn tsl_triggered(&self) -> bool {
        self.tsl_pct_triggered || self.tsl_atr_triggered || self.tsl_psar_triggered
    }

    /// 是否有任何风控条件触发
    fn any_triggered(&self) -> bool {
        self.sl_triggered() || self.tp_triggered() || self.tsl_triggered()
    }
}

impl BacktestState {
    /// 通用 Risk 离场检查逻辑
    pub(crate) fn check_risk_exit(
        &mut self,
        params: &BacktestParams,
        current_atr: Option<f64>,
        direction: Direction,
    ) {
        let is_atr_valid = current_atr.map_or(false, |atr| !atr.is_nan());

        // 1. 获取基础数据
        let (entry_price, is_first_entry) = self.get_entry_info(direction);

        // 2. 初始化/更新 Risk 价格
        self.update_risk_thresholds(
            params,
            entry_price,
            is_first_entry,
            current_atr,
            is_atr_valid,
            direction,
        );

        // 3. 检查触发条件
        let trigger_result = self.check_risk_triggers(params, direction);

        // 4. 应用结果
        self.apply_risk_outcome(params, direction, trigger_result);
    }

    /// 获取进场信息
    fn get_entry_info(&self, direction: Direction) -> (f64, bool) {
        match direction {
            Direction::Long => (
                self.action.entry_long_price.unwrap(),
                self.action.is_first_entry_long,
            ),
            Direction::Short => (
                self.action.entry_short_price.unwrap(),
                self.action.is_first_entry_short,
            ),
        }
    }

    /// 更新 Risk 阈值 (SL/TP/TSL)
    fn update_risk_thresholds(
        &mut self,
        params: &BacktestParams,
        entry_price: f64,
        is_first_entry: bool,
        current_atr: Option<f64>,
        is_atr_valid: bool,
        direction: Direction,
    ) {
        let sign = direction.sign();

        // 检查百分比止损
        if params.is_sl_pct_param_valid() && is_first_entry {
            let sl_pct = params.sl_pct.as_ref().unwrap().value;
            let calculated_sl_price = entry_price * (1.0 - sign * sl_pct);
            self.risk_state
                .set_sl_pct_price(direction, Some(calculated_sl_price));
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() && is_first_entry {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            let calculated_tp_price = entry_price * (1.0 + sign * tp_pct);
            self.risk_state
                .set_tp_pct_price(direction, Some(calculated_tp_price));
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid && is_first_entry {
            if let Some(atr) = current_atr {
                let sl_atr = params.sl_atr.as_ref().unwrap().value;
                let calculated_sl_price = entry_price - sign * atr * sl_atr;
                self.risk_state
                    .set_sl_atr_price(direction, Some(calculated_sl_price));
            }
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid && is_first_entry {
            if let Some(atr) = current_atr {
                let tp_atr = params.tp_atr.as_ref().unwrap().value;
                let calculated_tp_price = entry_price + sign * atr * tp_atr;
                self.risk_state
                    .set_tp_atr_price(direction, Some(calculated_tp_price));
            }
        }

        // 检查跟踪止损 (PCT & ATR)
        self.update_tsl_thresholds(params, entry_price, is_first_entry, current_atr, direction);

        // 检查 PSAR 跟踪止损
        self.update_tsl_psar_thresholds(params, is_first_entry, direction);
    }

    /// 更新跟踪止损阈值
    fn update_tsl_thresholds(
        &mut self,
        params: &BacktestParams,
        entry_price: f64,
        is_first_entry: bool,
        current_atr: Option<f64>,
        direction: Direction,
    ) {
        let sign = direction.sign();

        // 1. 计算极值 (Highest for Long, Lowest for Short)
        let current_extremum = match direction {
            Direction::Long => self.current_bar.high,
            Direction::Short => self.current_bar.low,
        };

        let stored_extremum = self.risk_state.extremum_since_entry(direction);

        let mut extremum_updated = false;
        let extremum = if is_first_entry {
            extremum_updated = true;
            entry_price
        } else {
            let prev = stored_extremum.unwrap_or(entry_price);
            match direction {
                Direction::Long => {
                    if current_extremum > prev {
                        extremum_updated = true;
                        current_extremum
                    } else {
                        prev
                    }
                }
                Direction::Short => {
                    if current_extremum < prev {
                        extremum_updated = true;
                        current_extremum
                    } else {
                        prev
                    }
                }
            }
        };

        // 更新极值状态
        if params.is_tsl_pct_param_valid() || params.is_tsl_atr_param_valid() {
            self.risk_state
                .set_extremum_since_entry(direction, Some(extremum));
        }

        // 2. 计算 TSL 价格
        // PCT TSL
        if params.is_tsl_pct_param_valid() {
            let tsl_pct = params.tsl_pct.as_ref().unwrap().value;
            let calculated_tsl_price = extremum * (1.0 - sign * tsl_pct);
            let old_price = self.risk_state.tsl_pct_price(direction);
            let new_price = update_price_one_direction(old_price, calculated_tsl_price, direction);
            self.risk_state.set_tsl_pct_price(direction, new_price);
        }

        // ATR TSL
        if params.is_tsl_atr_param_valid() {
            if let Some(atr) = current_atr {
                let tsl_atr = params.tsl_atr.as_ref().unwrap().value;
                let calculated_tsl_price = extremum - sign * atr * tsl_atr;

                // 判断是否应该更新 TSL 价格
                let should_update = if params.tsl_atr_tight {
                    // tight 模式：每根K线都尝试更新 (配合方向限制)
                    true
                } else {
                    // 非 tight 模式：只有极值更新时才尝试更新 (配合方向限制)
                    extremum_updated
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

    /// 更新 PSAR 跟踪止损阈值
    fn update_tsl_psar_thresholds(
        &mut self,
        params: &BacktestParams,
        is_first_entry: bool,
        direction: Direction,
    ) {
        if !params.is_tsl_psar_param_valid() {
            return;
        }

        // 检查 prev_prev_bar 是否有有效数据（i >= 2 时才有）
        // 如果 prev_prev_bar 是默认值（close=0），则无法正确初始化 PSAR
        let has_valid_prev_prev_bar = self.prev_prev_bar.close > 0.0;
        let psar_params = TslPsarParams {
            af0: params.tsl_psar_af0.as_ref().unwrap().value,
            af_step: params.tsl_psar_af_step.as_ref().unwrap().value,
            max_af: params.tsl_psar_max_af.as_ref().unwrap().value,
        };

        if is_first_entry && has_valid_prev_prev_bar {
            // 初始化 PSAR
            // 使用 bar[i-2] 和 bar[i-1] 初始化，得到 bar[i] 的 PSAR 值
            let (state, price) = init_tsl_psar(
                self.prev_prev_bar.high,
                self.prev_prev_bar.low,
                self.prev_prev_bar.close,
                self.prev_bar.high,
                self.prev_bar.low,
                self.prev_bar.close,
                direction,
                &psar_params,
                params.use_extrema_for_exit,
            );

            // 存储状态
            self.risk_state.set_tsl_psar_state(direction, Some(state));
            self.risk_state.set_tsl_psar_price(direction, Some(price));
        } else {
            // 更新 PSAR
            let prev_state = self.risk_state.tsl_psar_state(direction);

            if let Some(state) = prev_state {
                let (new_state, new_price) = update_tsl_psar(
                    state,
                    self.current_bar.high,
                    self.current_bar.low,
                    self.current_bar.close,
                    self.prev_bar.high,
                    self.prev_bar.low,
                    self.prev_bar.close,
                    direction,
                    &psar_params,
                    params.use_extrema_for_exit,
                );

                self.risk_state
                    .set_tsl_psar_state(direction, Some(new_state));
                self.risk_state
                    .set_tsl_psar_price(direction, Some(new_price));
            }
        }
    }

    /// 检查触发条件
    fn check_risk_triggers(
        &self,
        params: &BacktestParams,
        direction: Direction,
    ) -> RiskTriggerResult {
        let sign = direction.sign();

        let is_long = match direction {
            Direction::Long => true,
            Direction::Short => false,
        };
        let (price_for_sl, price_for_tp) = if params.exit_in_bar {
            switch_prices_in_bar(&self.current_bar, is_long)
        } else {
            switch_prices_next_bar(&self.current_bar, params, is_long)
        };

        let sl_pct_price = self.risk_state.sl_pct_price(direction);
        let sl_atr_price = self.risk_state.sl_atr_price(direction);
        let tp_pct_price = self.risk_state.tp_pct_price(direction);
        let tp_atr_price = self.risk_state.tp_atr_price(direction);
        let tsl_pct_price = self.risk_state.tsl_pct_price(direction);
        let tsl_atr_price = self.risk_state.tsl_atr_price(direction);
        let tsl_psar_price = self.risk_state.tsl_psar_price(direction);

        // 检查 SL
        let sl_pct_triggered =
            sl_pct_price.is_some() && price_for_sl * sign <= sl_pct_price.unwrap() * sign;
        let sl_atr_triggered =
            sl_atr_price.is_some() && price_for_sl * sign <= sl_atr_price.unwrap() * sign;

        // 检查 TP
        let tp_pct_triggered =
            tp_pct_price.is_some() && price_for_tp * sign >= tp_pct_price.unwrap() * sign;
        let tp_atr_triggered =
            tp_atr_price.is_some() && price_for_tp * sign >= tp_atr_price.unwrap() * sign;

        // 检查 TSL
        let (price_for_tsl, _) = switch_prices_next_bar(&self.current_bar, params, is_long);
        let tsl_pct_triggered =
            tsl_pct_price.is_some() && price_for_tsl * sign <= tsl_pct_price.unwrap() * sign;
        let tsl_atr_triggered =
            tsl_atr_price.is_some() && price_for_tsl * sign <= tsl_atr_price.unwrap() * sign;
        let tsl_psar_triggered =
            tsl_psar_price.is_some() && price_for_tsl * sign <= tsl_psar_price.unwrap() * sign;

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

    /// 应用 Risk 结果
    fn apply_risk_outcome(
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
            let is_in_bar_exit =
                params.exit_in_bar && (result.sl_triggered() || result.tp_triggered());

            let exit_price = if is_in_bar_exit {
                // 1. In-Bar 模式：只包含触发的 SL/TP 价格。
                // TSL/PSAR 始终为 Next-Bar，不参与 In-Bar 的悲观结算价格计算。
                calculate_risk_price(
                    sl_pct_eff, sl_atr_eff, tp_pct_eff, tp_atr_eff, None, None, None, is_long,
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

/// 单向更新价格（多头只升不降，空头只降不升）
fn update_price_one_direction(
    old_price: Option<f64>,
    new_price: f64,
    direction: Direction,
) -> Option<f64> {
    match (old_price, direction) {
        (None, _) => Some(new_price),
        (Some(old), Direction::Long) if new_price > old => Some(new_price),
        (Some(old), Direction::Short) if new_price < old => Some(new_price),
        (old, _) => old,
    }
}
