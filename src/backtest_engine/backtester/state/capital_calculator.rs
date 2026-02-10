use super::backtest_state::BacktestState;
use super::risk_trigger::risk_price_calc::Direction;
use crate::types::BacktestParams;

impl<'a> BacktestState<'a> {
    /// 计算并更新账户资金状态
    ///
    /// 根据当前仓位、价格和手续费计算账户余额和净值
    ///
    /// # 参数
    /// * `params` - 回测参数，包含手续费等信息
    pub fn calculate_capital(&mut self, params: &BacktestParams) {
        if self.should_skip_current_bar() {
            self.reset_capital_on_skip();
            return;
        }

        // 重置当前 bar 的交易状态
        self.capital_state.fee = 0.0;
        self.capital_state.trade_pnl_pct = 0.0;

        // 计算已实现盈亏（通过处理离场交易）
        self.calculate_realized_pnl(params);

        // 计算未实现盈亏（当前持仓的浮动盈亏百分比）
        let unrealized_pnl = self.calculate_unrealized_pnl();

        // 更新净值 = 余额 * (1 + 未实现盈亏百分比)
        // 假设全仓模式：当前余额全部用于持仓
        self.capital_state.equity = self.capital_state.balance * (1.0 + unrealized_pnl);

        // === 余额和净值归零保护 ===
        // 确保余额不会变为负数
        if self.capital_state.balance < 0.0 {
            self.capital_state.balance = 0.0;
        }

        // 确保净值不会变为负数
        if self.capital_state.equity < 0.0 {
            self.capital_state.equity = 0.0;
        }

        // 更新历史最高净值
        if self.capital_state.equity > self.capital_state.peak_equity {
            self.capital_state.peak_equity = self.capital_state.equity;
        }

        // 计算当前回撤
        self.capital_state.current_drawdown = if self.capital_state.peak_equity > 0.0 {
            (self.capital_state.peak_equity - self.capital_state.equity)
                / self.capital_state.peak_equity
        } else {
            0.0
        };

        // 计算总回报率（相对于初始资金）
        self.capital_state.total_return_pct =
            self.capital_state.equity / self.capital_state.initial_capital - 1.0;
    }

    /// 计算已实现盈亏（价格驱动版本）
    ///
    /// 基于价格组合和risk_in_bar状态机管理结算顺序
    ///
    /// 结算顺序（复杂反手场景）：
    /// 1. 先结算 risk_in_bar == 0 的离场（策略信号，next_bar）
    /// 2. 后结算 risk_in_bar != 0 的离场（risk触发，in_bar）
    ///
    /// 核心假设：
    /// - 全仓交易，单仓位模型
    /// - 费用仅在平仓时结算
    fn calculate_realized_pnl(&mut self, params: &BacktestParams) {
        // 记录 bar 开始时的 balance，用于计算综合 trade_pnl_pct
        let bar_start_balance = self.capital_state.balance;

        // === 第一轮：策略离场（next_bar） ===
        if self.is_exiting_long() && !self.risk_state.should_exit_in_bar_long() {
            self.calculate_exit_pnl(params, Direction::Long);
        }
        if self.is_exiting_short() && !self.risk_state.should_exit_in_bar_short() {
            self.calculate_exit_pnl(params, Direction::Short);
        }

        // === 第二轮：risk离场（in_bar） ===
        if self.is_exiting_long() && self.risk_state.should_exit_in_bar_long() {
            self.calculate_exit_pnl(params, Direction::Long);
        }
        if self.is_exiting_short() && self.risk_state.should_exit_in_bar_short() {
            self.calculate_exit_pnl(params, Direction::Short);
        }

        // === 计算综合 trade_pnl_pct ===
        // 反映整个 bar 的总回报率，使得 balance = prev_balance * (1 + trade_pnl_pct)始终成立
        self.capital_state.trade_pnl_pct = self.capital_state.balance / bar_start_balance - 1.0;
    }

    /// 计算指定方向的离场盈亏
    ///
    /// 处理仓位的离场交易，计算已实现盈亏和手续费，并更新账户余额。
    fn calculate_exit_pnl(&mut self, params: &BacktestParams, direction: Direction) {
        let (exit_price, entry_price) = match direction {
            Direction::Long => (self.action.exit_long_price, self.action.entry_long_price),
            Direction::Short => (self.action.exit_short_price, self.action.entry_short_price),
        };

        if let (Some(exit_price), Some(entry_price)) = (exit_price, entry_price) {
            // --- 1. 提取旧状态 ---
            let initial_balance = self.capital_state.balance;

            // --- 2. 原始交易计算 ---
            // 交易百分比盈亏 (Pnl_Raw_Pct)
            // 多头: (exit - entry) / entry
            // 空头: (entry - exit) / entry
            let pnl_raw_pct = direction.sign() * (exit_price - entry_price) / entry_price;

            // 原始平仓名义价值 (包括盈亏，未扣费)
            let realized_value = initial_balance * (1.0 + pnl_raw_pct);

            // --- 3. 费用计算 ---
            // 费用基数：固定费用 + 往返交易的名义价值百分比费用
            let fee_amount = params.fee_fixed
                // 假设开仓成本基于 initial_balance
                + initial_balance * params.fee_pct / 2.0
                // 假设平仓成本基于 realized_value
                + realized_value * params.fee_pct / 2.0;

            // --- 4. 净值结算 ---
            let new_balance = realized_value - fee_amount;

            // --- 5. 更新状态 ---
            // 更新账户余额
            self.capital_state.balance = new_balance;

            // 更新费用（累加，支持同 bar 多次结算）
            self.capital_state.fee += fee_amount;
            self.capital_state.fee_cum += fee_amount;
        }
    }

    /// 计算未实现盈亏（价格驱动版本）
    ///
    /// 基于价格判断当前持仓状态
    fn calculate_unrealized_pnl(&self) -> f64 {
        let current_price = self.current_bar.close;
        let mut unrealized_pnl = 0.0;

        // 持有多头（有entry_long无exit_long）
        if self.has_long_position() {
            if let Some(entry_price) = self.action.entry_long_price {
                unrealized_pnl = (current_price - entry_price) / entry_price;
            }
        }

        // 持有空头（有entry_short无exit_short）
        if self.has_short_position() {
            if let Some(entry_price) = self.action.entry_short_price {
                unrealized_pnl = (entry_price - current_price) / entry_price;
            }
        }

        unrealized_pnl
    }

    /// 判断是否应该跳过当前 bar 的计算（资金归零）
    pub fn should_skip_current_bar(&self) -> bool {
        self.capital_state.balance <= 0.0 || self.capital_state.equity <= 0.0
    }

    /// 当跳过计算时重置资金相关状态
    fn reset_capital_on_skip(&mut self) {
        self.capital_state.fee = 0.0;
        self.capital_state.trade_pnl_pct = 0.0;
        // 净值和归一化处理，确保不会产生负数或 NaN
        if self.capital_state.balance < 0.0 {
            self.capital_state.balance = 0.0;
        }
        if self.capital_state.equity < 0.0 {
            self.capital_state.equity = 0.0;
        }
        self.capital_state.current_drawdown = 1.0; // 资金归零视为 100% 回撤
        self.capital_state.total_return_pct = -1.0; // 资金归零视为 -100% 回报
    }
}
