use super::super::backtest_state::BacktestState;
use super::price_utils::{calculate_risk_price, switch_prices_in_bar, switch_prices_next_bar};
use super::tsl_psar::{init_tsl_psar, update_tsl_psar, TslPsarParams};
use crate::data_conversion::BacktestParams;

#[derive(PartialEq, Clone, Copy)]
pub enum Direction {
    Long,
    Short,
}

impl Direction {
    /// 获取方向符号：Long为1.0，Short为-1.0
    pub fn sign(&self) -> f64 {
        match self {
            Direction::Long => 1.0,
            Direction::Short => -1.0,
        }
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
        let is_atr_valid = current_atr.is_some() && !current_atr.unwrap().is_nan();

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
        let (sl_triggered, tp_triggered, tsl_triggered) =
            self.check_risk_triggers(params, direction);

        // 4. 应用结果
        self.apply_risk_outcome(params, direction, sl_triggered, tp_triggered, tsl_triggered);
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
            // Long: entry * (1 - pct) = entry - entry * pct
            // Short: entry * (1 + pct) = entry - entry * (-pct) = entry - entry * (sign * pct)
            // 通用公式: entry * (1.0 - sign * sl_pct)
            let calculated_sl_price = entry_price * (1.0 - sign * sl_pct);
            match direction {
                Direction::Long => self.risk_state.sl_pct_price_long = Some(calculated_sl_price),
                Direction::Short => self.risk_state.sl_pct_price_short = Some(calculated_sl_price),
            }
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() && is_first_entry {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            // Long: entry * (1 + pct)
            // Short: entry * (1 - pct)
            // 通用公式: entry * (1.0 + sign * tp_pct)
            let calculated_tp_price = entry_price * (1.0 + sign * tp_pct);
            match direction {
                Direction::Long => self.risk_state.tp_pct_price_long = Some(calculated_tp_price),
                Direction::Short => self.risk_state.tp_pct_price_short = Some(calculated_tp_price),
            }
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid && is_first_entry {
            let sl_atr = params.sl_atr.as_ref().unwrap().value;
            // Long: entry - atr * k
            // Short: entry + atr * k
            // 通用公式: entry - sign * atr * k
            let calculated_sl_price = entry_price - sign * current_atr.unwrap() * sl_atr;
            match direction {
                Direction::Long => self.risk_state.sl_atr_price_long = Some(calculated_sl_price),
                Direction::Short => self.risk_state.sl_atr_price_short = Some(calculated_sl_price),
            }
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid && is_first_entry {
            let tp_atr = params.tp_atr.as_ref().unwrap().value;
            // Long: entry + atr * k
            // Short: entry - atr * k
            // 通用公式: entry + sign * atr * k
            let calculated_tp_price = entry_price + sign * current_atr.unwrap() * tp_atr;
            match direction {
                Direction::Long => self.risk_state.tp_atr_price_long = Some(calculated_tp_price),
                Direction::Short => self.risk_state.tp_atr_price_short = Some(calculated_tp_price),
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

        let stored_extremum = match direction {
            Direction::Long => self.risk_state.highest_since_entry,
            Direction::Short => self.risk_state.lowest_since_entry,
        };

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
            match direction {
                Direction::Long => self.risk_state.highest_since_entry = Some(extremum),
                Direction::Short => self.risk_state.lowest_since_entry = Some(extremum),
            }
        }

        // 2. 计算 TSL 价格
        // PCT TSL
        if params.is_tsl_pct_param_valid() {
            let tsl_pct = params.tsl_pct.as_ref().unwrap().value;
            // 通用: extremum * (1.0 - sign * tsl_pct)
            let calculated_tsl_price = extremum * (1.0 - sign * tsl_pct);

            match direction {
                Direction::Long => {
                    // 多头：只升不降
                    let old_price = self.risk_state.tsl_pct_price_long;
                    if old_price.is_none() || calculated_tsl_price > old_price.unwrap() {
                        self.risk_state.tsl_pct_price_long = Some(calculated_tsl_price);
                    }
                }
                Direction::Short => {
                    // 空头：只降不升
                    let old_price = self.risk_state.tsl_pct_price_short;
                    if old_price.is_none() || calculated_tsl_price < old_price.unwrap() {
                        self.risk_state.tsl_pct_price_short = Some(calculated_tsl_price);
                    }
                }
            }
        }

        // ATR TSL
        if params.is_tsl_atr_param_valid() && current_atr.is_some() {
            let tsl_atr = params.tsl_atr.as_ref().unwrap().value;
            // 通用: extremum - sign * current_atr.unwrap() * tsl_atr
            let calculated_tsl_price = extremum - sign * current_atr.unwrap() * tsl_atr;

            // 判断是否应该更新 TSL 价格
            let should_update = if params.tsl_atr_tight {
                // tight 模式：每根K线都尝试更新 (配合方向限制)
                true
            } else {
                // 非 tight 模式：只有极值更新时才尝试更新 (配合方向限制)
                extremum_updated
            };

            if should_update {
                match direction {
                    Direction::Long => {
                        // 多头：只升不降
                        let old_price = self.risk_state.tsl_atr_price_long;
                        if old_price.is_none() || calculated_tsl_price > old_price.unwrap() {
                            self.risk_state.tsl_atr_price_long = Some(calculated_tsl_price);
                        }
                    }
                    Direction::Short => {
                        // 空头：只降不升
                        let old_price = self.risk_state.tsl_atr_price_short;
                        if old_price.is_none() || calculated_tsl_price < old_price.unwrap() {
                            self.risk_state.tsl_atr_price_short = Some(calculated_tsl_price);
                        }
                    }
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
            match direction {
                Direction::Long => {
                    self.risk_state.tsl_psar_state_long = Some(state);
                    self.risk_state.tsl_psar_price_long = Some(price);
                }
                Direction::Short => {
                    self.risk_state.tsl_psar_state_short = Some(state);
                    self.risk_state.tsl_psar_price_short = Some(price);
                }
            }
        } else {
            // 更新 PSAR
            let prev_state = match direction {
                Direction::Long => &self.risk_state.tsl_psar_state_long,
                Direction::Short => &self.risk_state.tsl_psar_state_short,
            };

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

                match direction {
                    Direction::Long => {
                        self.risk_state.tsl_psar_state_long = Some(new_state);
                        self.risk_state.tsl_psar_price_long = Some(new_price);
                    }
                    Direction::Short => {
                        self.risk_state.tsl_psar_state_short = Some(new_state);
                        self.risk_state.tsl_psar_price_short = Some(new_price);
                    }
                }
            }
        }
    }

    /// 检查触发条件
    fn check_risk_triggers(
        &self,
        params: &BacktestParams,
        direction: Direction,
    ) -> (bool, bool, bool) {
        let sign = direction.sign();

        // 获取用于检查 SL 和 TP 的价格
        let is_long = match direction {
            Direction::Long => true,
            Direction::Short => false,
        };
        let (price_for_sl, price_for_tp) = if params.exit_in_bar {
            switch_prices_in_bar(&self.current_bar, is_long)
        } else {
            switch_prices_next_bar(&self.current_bar, params, is_long)
        };

        let (sl_pct_price, sl_atr_price, tp_pct_price, tp_atr_price, tsl_pct_price, tsl_atr_price) =
            match direction {
                Direction::Long => (
                    self.risk_state.sl_pct_price_long,
                    self.risk_state.sl_atr_price_long,
                    self.risk_state.tp_pct_price_long,
                    self.risk_state.tp_atr_price_long,
                    self.risk_state.tsl_pct_price_long,
                    self.risk_state.tsl_atr_price_long,
                ),
                Direction::Short => (
                    self.risk_state.sl_pct_price_short,
                    self.risk_state.sl_atr_price_short,
                    self.risk_state.tp_pct_price_short,
                    self.risk_state.tp_atr_price_short,
                    self.risk_state.tsl_pct_price_short,
                    self.risk_state.tsl_atr_price_short,
                ),
            };

        // 检查 SL
        let sl_triggered = (sl_pct_price.is_some()
            && price_for_sl * sign <= sl_pct_price.unwrap() * sign)
            || (sl_atr_price.is_some() && price_for_sl * sign <= sl_atr_price.unwrap() * sign);

        // 检查 TP
        let tp_triggered = (tp_pct_price.is_some()
            && price_for_tp * sign >= tp_pct_price.unwrap() * sign)
            || (tp_atr_price.is_some() && price_for_tp * sign >= tp_atr_price.unwrap() * sign);

        // 检查 TSL
        let (price_for_tsl, _) = switch_prices_next_bar(&self.current_bar, params, is_long);
        // TSL 逻辑同 SL
        let tsl_pct_triggered =
            (tsl_pct_price.is_some() && price_for_tsl * sign <= tsl_pct_price.unwrap() * sign);
        let tsl_atr_triggered =
            (tsl_atr_price.is_some() && price_for_tsl * sign <= tsl_atr_price.unwrap() * sign);

        // PSAR TSL 触发检查
        let tsl_psar_price = match direction {
            Direction::Long => self.risk_state.tsl_psar_price_long,
            Direction::Short => self.risk_state.tsl_psar_price_short,
        };
        let tsl_psar_triggered =
            tsl_psar_price.is_some() && price_for_tsl * sign <= tsl_psar_price.unwrap() * sign;

        let tsl_triggered = tsl_pct_triggered || tsl_atr_triggered || tsl_psar_triggered;

        (sl_triggered, tp_triggered, tsl_triggered)
    }

    /// 应用 Risk 结果
    fn apply_risk_outcome(
        &mut self,
        params: &BacktestParams,
        direction: Direction,
        sl_triggered: bool,
        tp_triggered: bool,
        tsl_triggered: bool,
    ) {
        let should_exit = sl_triggered || tp_triggered || tsl_triggered;

        if should_exit {
            let is_long = match direction {
                Direction::Long => true,
                Direction::Short => false,
            };

            let (sl_pct, sl_atr, tp_pct, tp_atr, tsl_pct, tsl_atr, tsl_psar) = match direction {
                Direction::Long => (
                    self.risk_state.sl_pct_price_long,
                    self.risk_state.sl_atr_price_long,
                    self.risk_state.tp_pct_price_long,
                    self.risk_state.tp_atr_price_long,
                    self.risk_state.tsl_pct_price_long,
                    self.risk_state.tsl_atr_price_long,
                    self.risk_state.tsl_psar_price_long,
                ),
                Direction::Short => (
                    self.risk_state.sl_pct_price_short,
                    self.risk_state.sl_atr_price_short,
                    self.risk_state.tp_pct_price_short,
                    self.risk_state.tp_atr_price_short,
                    self.risk_state.tsl_pct_price_short,
                    self.risk_state.tsl_atr_price_short,
                    self.risk_state.tsl_psar_price_short,
                ),
            };

            // 根据触发状态过滤价格，避免未触发的优良价格掩盖已触发的离场价格
            let sl_pct_eff = if sl_triggered { sl_pct } else { None };
            let sl_atr_eff = if sl_triggered { sl_atr } else { None };
            let tp_pct_eff = if tp_triggered { tp_pct } else { None };
            let tp_atr_eff = if tp_triggered { tp_atr } else { None };
            let tsl_pct_eff = if tsl_triggered { tsl_pct } else { None };
            let tsl_atr_eff = if tsl_triggered { tsl_atr } else { None };
            let tsl_psar_eff = if tsl_triggered { tsl_psar } else { None };

            let exit_price = calculate_risk_price(
                sl_pct_eff,
                sl_atr_eff,
                tp_pct_eff,
                tp_atr_eff,
                tsl_pct_eff,
                tsl_atr_eff,
                tsl_psar_eff,
                is_long,
            );

            match direction {
                Direction::Long => self.risk_state.exit_long_price = exit_price,
                Direction::Short => self.risk_state.exit_short_price = exit_price,
            }

            self.risk_state.in_bar_direction =
                if params.exit_in_bar && (sl_triggered || tp_triggered) {
                    match direction {
                        Direction::Long => 1,
                        Direction::Short => -1,
                    }
                } else {
                    0
                };
        } else {
            match direction {
                Direction::Long => self.risk_state.exit_long_price = None,
                Direction::Short => self.risk_state.exit_short_price = None,
            }
            self.risk_state.in_bar_direction = 0;
        }
    }
}
