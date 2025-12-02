use super::backtest_state::BacktestState;
use super::risk_trigger::risk_check::Direction;
use super::risk_trigger::risk_state::RiskState;
use crate::data_conversion::BacktestParams;

impl BacktestState {
    pub fn reset_position_on_skip(&mut self) {
        self.action.reset_prices();

        self.risk_state = RiskState::default();
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
        // 如果上一bar多头离场完成，本bar重置多头价格
        if self.action.exit_long_price.is_some() {
            self.action.entry_long_price = None;
            self.action.exit_long_price = None;
        }
        // 如果上一bar空头离场完成，本bar重置空头价格
        if self.action.exit_short_price.is_some() {
            self.action.entry_short_price = None;
            self.action.exit_short_price = None;
        }

        // === 2. 处理bar(i-1)的策略信号（next_bar模式） ===

        // 重置首次进场标志（默认为 false，只有在发生进场时才设为 true）
        self.action.is_first_entry_long = false;
        self.action.is_first_entry_short = false;

        // 2.1 进场检查（含反手逻辑）
        if self.can_enter_long() && self.prev_bar.enter_long {
            self.action.entry_long_price = Some(self.current_bar.open);
            self.action.is_first_entry_long = true;
        }
        if self.can_enter_short() && self.prev_bar.enter_short {
            self.action.entry_short_price = Some(self.current_bar.open);
            self.action.is_first_entry_short = true;
        }

        // 2.2 策略离场检查
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

        // === 3. 处理bar(i)的risk触发（可能in_bar模式） ===
        // 重置 risk 触发状态
        self.risk_state.reset_exit_state();

        if self.has_long_position() {
            self.check_risk_exit(params, self.current_bar.atr, Direction::Long);
            // 如果 in_bar 模式触发，设置 exit_long_price
            if self.risk_state.should_exit_in_bar_long() {
                self.action.exit_long_price = self.risk_state.exit_long_price;
            }
        }
        if self.has_short_position() {
            self.check_risk_exit(params, self.current_bar.atr, Direction::Short);
            // 如果 in_bar 模式触发，设置 exit_short_price
            if self.risk_state.should_exit_in_bar_short() {
                self.action.exit_short_price = self.risk_state.exit_short_price;
            }
        }
    }
}
