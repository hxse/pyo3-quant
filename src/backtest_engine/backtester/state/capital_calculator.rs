use super::{backtest_state::BacktestState, position_state::Position};
use crate::data_conversion::BacktestParams;

impl BacktestState {
    /// 计算并更新账户资金状态
    ///
    /// 根据当前仓位、价格和手续费计算账户余额和净值
    ///
    /// # 参数
    /// * `params` - 回测参数，包含手续费等信息
    pub fn calculate_capital(&mut self, params: &BacktestParams) {
        // 重置当前交易的手续费
        self.capital_state.fee = 0.0;

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

        // 计算总回报率（相对于初始资金）
        self.capital_state.total_return_pct =
            self.capital_state.equity / self.capital_state.initial_capital - 1.0;
    }

    /// 计算已实现盈亏 (Realized PnL)
    ///
    /// 处理离场交易，计算已实现盈亏和手续费，并更新账户余额。
    ///
    /// # 核心机制说明
    /// ## 双层状态系统
    /// - **previous_position**: **信号状态**，表示基于信号判断应该执行的操作
    /// - **current_position**: **执行状态**，表示实际发生的操作
    /// - **risk_in_bar**: 风险离场标志，表示风险机制触发的离场在当前bar内实际执行
    ///
    /// ## 处理逻辑
    /// 1. **信号离场**: `previous_position.is_exit_long/short()` - 处理信号触发的离场
    /// 2. **风险离场**: `current_position.is_exit_long/short() && risk_in_bar` - 处理风险触发的离场
    ///    - 必须同时满足：仓位状态是离场 + 风险离场在当前bar执行
    ///    - `risk_in_bar` 确保只有实际发生的离场才计算盈亏
    ///
    /// # 核心假设 (Core Assumptions)
    /// 1. **全仓交易:** 每次开仓都假定使用当前的**全部余额** (`initial_balance`) 进行购买或做空。
    /// 2. **单仓位模型:** 始终只持有一个仓位（多头或空头）。不需要考虑多仓位, 不需要考虑杠杆。
    /// 3. **单次费用结算:** 交易费用仅在**平仓离场时**一次性计算和扣除。
    ///
    /// # 费用模型 (Fee Model)
    /// `params.fee_fixed` 和 `params.fee_pct` 代表了综合性的、悲观预估的交易成本，
    /// 包括但不限于：传统手续费、滑点、价差、网络波动影响等, 应该由用户根据实际情况决定。
    /// 百分比费用 (`fee_pct`) 被拆分为基于开仓名义价值和基于平仓名义价值的往返成本。
    fn calculate_realized_pnl(&mut self, params: &BacktestParams) {
        // ===== 信号离场处理 =====
        // previous_position 是信号状态，表示基于信号判断应该离场
        // 这种离场通常是策略信号驱动的，如技术指标信号等
        if self.action.previous_position.is_exit_long() && !self.action.previous_risk_in_bar {
            self.calculate_long_exit_pnl(params);
        } else if self.action.previous_position.is_exit_short() && !self.action.previous_risk_in_bar
        {
            self.calculate_short_exit_pnl(params);
        }

        // ===== 风险离场处理 =====
        // current_position 是执行状态，risk_in_bar 确保风险离场实际发生
        // 这种离场是风控系统触发的，如止损、止盈等
        // 注意：必须同时满足仓位状态和风险执行标志
        if self.action.current_position.is_exit_long() && self.action.risk_in_bar {
            self.calculate_long_exit_pnl(params);
        } else if self.action.current_position.is_exit_short() && self.action.risk_in_bar {
            self.calculate_short_exit_pnl(params);
        }
    }

    /// 计算多头离场盈亏
    ///
    /// 处理多头仓位的离场交易，计算已实现盈亏和手续费，并更新账户余额。
    fn calculate_long_exit_pnl(&mut self, params: &BacktestParams) {
        if let Some(exit_price) = self.action.exit_long_price {
            if let Some(entry_price) = self.action.entry_long_price {
                // --- 1. 提取旧状态 ---
                let initial_balance = self.capital_state.balance;

                // --- 2. 原始交易计算 ---
                // 交易百分比盈亏 (Pnl_Raw_Pct)
                let pnl_raw_pct = (exit_price - entry_price) / entry_price;

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

                // 计算单笔盈亏百分比（扣除手续费后的净回报）
                // (新余额 / 旧余额) - 1.0
                self.capital_state.trade_pnl_pct = new_balance / initial_balance - 1.0;

                // 更新账户余额
                self.capital_state.balance = new_balance;

                // 更新费用累计
                self.capital_state.fee = fee_amount;
                self.capital_state.fee_cum += fee_amount;
            }
        }
    }

    /// 计算空头离场盈亏
    ///
    /// 处理空头仓位的离场交易，计算已实现盈亏和手续费，并更新账户余额。
    fn calculate_short_exit_pnl(&mut self, params: &BacktestParams) {
        if let Some(exit_price) = self.action.exit_short_price {
            if let Some(entry_price) = self.action.entry_short_price {
                // --- 1. 提取旧状态 ---
                let initial_balance = self.capital_state.balance;

                // --- 2. 原始交易计算 ---
                // 交易百分比盈亏 (Pnl_Raw_Pct)
                let pnl_raw_pct = (entry_price - exit_price) / entry_price;

                // 原始平仓名义价值 (包括盈亏，未扣费)
                let realized_value = initial_balance * (1.0 + pnl_raw_pct);

                // --- 3. 费用计算
                let fee_amount = params.fee_fixed
                    + initial_balance * params.fee_pct / 2.0
                    + realized_value * params.fee_pct / 2.0;

                // --- 4. 净值结算
                let new_balance = realized_value - fee_amount;

                // --- 5. 更新状态
                self.capital_state.trade_pnl_pct = new_balance / initial_balance - 1.0;
                self.capital_state.balance = new_balance;
                self.capital_state.fee = fee_amount;
                self.capital_state.fee_cum += fee_amount;
            }
        }
    }

    /// 计算未实现盈亏
    ///
    /// 计算当前持仓的浮动盈亏
    fn calculate_unrealized_pnl(&self) -> f64 {
        let current_price = self.current_bar.close;
        let mut unrealized_pnl = 0.0;

        // 计算多头未实现盈亏
        if self.action.current_position == Position::HoldLong {
            if let Some(entry_price) = self.action.entry_long_price {
                unrealized_pnl += (current_price - entry_price) / entry_price;
            }
        }

        // 计算空头未实现盈亏
        if self.action.current_position == Position::HoldShort {
            if let Some(entry_price) = self.action.entry_short_price {
                unrealized_pnl += (entry_price - current_price) / entry_price;
            }
        }

        unrealized_pnl
    }
}
