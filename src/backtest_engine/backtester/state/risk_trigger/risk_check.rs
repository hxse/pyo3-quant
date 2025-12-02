use super::super::backtest_state::BacktestState;
use super::price_utils::{calculate_risk_price, switch_prices_in_bar, switch_prices_next_bar};
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
            self.risk_state.sl_pct_price = Some(calculated_sl_price);
        }

        // 检查百分比止盈
        if params.is_tp_pct_param_valid() && is_first_entry {
            let tp_pct = params.tp_pct.as_ref().unwrap().value;
            // Long: entry * (1 + pct)
            // Short: entry * (1 - pct)
            // 通用公式: entry * (1.0 + sign * tp_pct)
            let calculated_tp_price = entry_price * (1.0 + sign * tp_pct);
            self.risk_state.tp_pct_price = Some(calculated_tp_price);
        }

        // 检查 ATR 止损
        if params.is_sl_atr_param_valid() && is_atr_valid && is_first_entry {
            let sl_atr = params.sl_atr.as_ref().unwrap().value;
            // Long: entry - atr * k
            // Short: entry + atr * k
            // 通用公式: entry - sign * atr * k
            let calculated_sl_price = entry_price - sign * current_atr.unwrap() * sl_atr;
            self.risk_state.sl_atr_price = Some(calculated_sl_price);
        }

        // 检查 ATR 止盈
        if params.is_tp_atr_param_valid() && is_atr_valid && is_first_entry {
            let tp_atr = params.tp_atr.as_ref().unwrap().value;
            // Long: entry + atr * k
            // Short: entry - atr * k
            // 通用公式: entry + sign * atr * k
            let calculated_tp_price = entry_price + sign * current_atr.unwrap() * tp_atr;
            self.risk_state.tp_atr_price = Some(calculated_tp_price);
        }

        // 检查跟踪止损 (PCT & ATR)
        self.update_tsl_thresholds(params, entry_price, is_first_entry, current_atr, direction);
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

        let extremum = if is_first_entry {
            entry_price
        } else {
            let prev = stored_extremum.unwrap_or(entry_price);
            match direction {
                Direction::Long => prev.max(current_extremum),
                Direction::Short => prev.min(current_extremum),
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
            // Long: high * (1 - pct)
            // Short: low * (1 + pct)
            // 通用: extremum * (1.0 - sign * tsl_pct)
            let calculated_tsl_price = extremum * (1.0 - sign * tsl_pct);
            self.risk_state.tsl_pct_price = Some(calculated_tsl_price);
        }

        // ATR TSL
        if params.is_tsl_atr_param_valid() && current_atr.is_some() {
            let tsl_atr = params.tsl_atr.as_ref().unwrap().value;
            // Long: high - atr * k
            // Short: low + atr * k
            // 通用: extremum - sign * atr * k
            let calculated_tsl_price = extremum - sign * current_atr.unwrap() * tsl_atr;
            self.risk_state.tsl_atr_price = Some(calculated_tsl_price);
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

        // 检查 SL
        // Long: price <= sl  => price * 1 <= sl * 1
        // Short: price >= sl => price * -1 <= sl * -1
        // 通用: price * sign <= sl * sign
        let sl_triggered = (self.risk_state.sl_pct_price.is_some()
            && price_for_sl * sign <= self.risk_state.sl_pct_price.unwrap() * sign)
            || (self.risk_state.sl_atr_price.is_some()
                && price_for_sl * sign <= self.risk_state.sl_atr_price.unwrap() * sign);

        // 检查 TP
        // Long: price >= tp => price * 1 >= tp * 1
        // Short: price <= tp => price * -1 >= tp * -1
        // 通用: price * sign >= tp * sign
        let tp_triggered = (self.risk_state.tp_pct_price.is_some()
            && price_for_tp * sign >= self.risk_state.tp_pct_price.unwrap() * sign)
            || (self.risk_state.tp_atr_price.is_some()
                && price_for_tp * sign >= self.risk_state.tp_atr_price.unwrap() * sign);

        // 检查 TSL
        let (price_for_tsl, _) = switch_prices_next_bar(&self.current_bar, params, is_long);
        // TSL 逻辑同 SL
        let tsl_triggered = (self.risk_state.tsl_pct_price.is_some()
            && price_for_tsl * sign <= self.risk_state.tsl_pct_price.unwrap() * sign)
            || (self.risk_state.tsl_atr_price.is_some()
                && price_for_tsl * sign <= self.risk_state.tsl_atr_price.unwrap() * sign);

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
            let exit_price = calculate_risk_price(
                self.risk_state.sl_pct_price,
                self.risk_state.sl_atr_price,
                self.risk_state.tp_pct_price,
                self.risk_state.tp_atr_price,
                is_long,
            );

            match direction {
                Direction::Long => self.risk_state.exit_long_price = exit_price,
                Direction::Short => self.risk_state.exit_short_price = exit_price,
            }

            self.risk_state.exit_in_bar = params.exit_in_bar && (sl_triggered || tp_triggered);
        } else {
            match direction {
                Direction::Long => self.risk_state.exit_long_price = None,
                Direction::Short => self.risk_state.exit_short_price = None,
            }
            self.risk_state.exit_in_bar = false;
        }
    }
}
