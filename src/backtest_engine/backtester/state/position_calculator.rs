use super::backtest_state::BacktestState;
use super::risk_trigger;
use crate::data_conversion::BacktestParams;

impl<'a> BacktestState<'a> {
    pub fn reset_position_on_skip(&mut self) {
        self.action.reset_prices();

        self.risk_state.reset_all();
    }

    /// 计算并更新仓位状态（价格驱动版本）
    ///
    /// 基于价格组合而非Position枚举来管理状态
    /// 核心逻辑：
    /// 1. 重置价格（如果上一bar离场完成）
    /// 2. 处理i-1的策略信号（next_bar模式）
    /// 3. 处理i的risk触发（in_bar模式）
    pub fn calculate_position(&mut self, params: &BacktestParams) {
        // === 1. 价格重置逻辑（区分方向） ===
        // 如果上一bar多头离场完成，本bar重置多头价格和风险状态
        if self.action.exit_long_price.is_some() {
            self.action.entry_long_price = None;
            self.action.exit_long_price = None;
            self.risk_state.reset_long_state();
        }
        // 如果上一bar空头离场完成，本bar重置空头价格和风险状态
        if self.action.exit_short_price.is_some() {
            self.action.entry_short_price = None;
            self.action.exit_short_price = None;
            self.risk_state.reset_short_state();
        }

        // === 2. 处理bar(i-1)的策略信号（next_bar模式） ===
        //
        // 执行顺序说明（同bar最复杂场景）：
        // 1. 先策略离场（开盘价平掉上一根K线信号的仓位）
        // 2. 再策略进场（开盘价按上一根K线信号反手开仓）
        // 3. 最后risk检查（可能在SL/TP价格触发新仓位的离场）
        //
        // 这样 can_entry_long() 检查 is_exiting_short() 时，exit_short_price 已经设置。

        // 2.1 策略离场检查
        if self.has_long_position()
            && (self.prev_bar.exit_long || self.risk_state.should_exit_next_bar_long())
            && !self.risk_state.should_exit_in_bar_long()
        {
            self.action.exit_long_price = Some(self.current_bar.open);
        }
        if self.has_short_position()
            && (self.prev_bar.exit_short || self.risk_state.should_exit_next_bar_short())
            && !self.risk_state.should_exit_in_bar_short()
        {
            self.action.exit_short_price = Some(self.current_bar.open);
        }

        // 2.2 进场检查（含反手逻辑）
        // 重置首次进场标志
        self.action.first_entry_side = 0;

        if self.can_entry_long() && self.prev_bar.entry_long {
            // [Gap Protection] 检查进场是否安全
            let is_safe = self.init_entry_with_safety_check(params, risk_trigger::Direction::Long);
            if is_safe {
                self.action.entry_long_price = Some(self.current_bar.open);
                self.action.first_entry_side = 1;
            }
        }
        if self.can_entry_short() && self.prev_bar.entry_short {
            // [Gap Protection] 检查进场是否安全
            let is_safe = self.init_entry_with_safety_check(params, risk_trigger::Direction::Short);
            if is_safe {
                self.action.entry_short_price = Some(self.current_bar.open);
                self.action.first_entry_side = -1;
            }
        }

        // === 3. 处理bar(i)的risk触发（可能in_bar模式） ===
        // 重置 risk 触发状态
        self.risk_state.reset_exit_state();

        if self.has_long_position() {
            self.check_risk_exit(params, risk_trigger::Direction::Long);
            // 如果 in_bar 模式触发，设置 exit_long_price
            if self.risk_state.should_exit_in_bar_long() {
                self.action.exit_long_price =
                    self.risk_state.exit_price(risk_trigger::Direction::Long);
            }
        }
        if self.has_short_position() {
            self.check_risk_exit(params, risk_trigger::Direction::Short);
            // 如果 in_bar 模式触发，设置 exit_short_price
            if self.risk_state.should_exit_in_bar_short() {
                self.action.exit_short_price =
                    self.risk_state.exit_price(risk_trigger::Direction::Short);
            }
        }
    }
}
