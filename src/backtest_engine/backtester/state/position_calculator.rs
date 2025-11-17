use super::backtest_state::BacktestState;
use super::position_state::Position;
use super::risk_trigger::risk_state::RiskState;
use crate::data_conversion::BacktestParams;

impl BacktestState {
    /// 检查是否应该跳过当前bar
    ///
    /// # 返回值
    /// * `bool` - 如果应该跳过当前bar返回true，否则返回false
    pub fn should_skip_current_bar(&mut self) -> bool {
        // 检查 ATR 是否为 NaN（如果使用了 ATR 相关的止损/止盈）
        if let Some(atr_value) = self.current_bar.atr {
            if atr_value.is_nan() {
                // ATR 为 NaN，跳过开仓，直接更新状态为无仓位
                self.action.current_position = Position::None;
                self.action.previous_position = Position::None;
                self.action.risk_in_bar = false;
                self.action.risk_long_trigger = false;
                self.action.risk_short_trigger = false;
                self.risk_state = RiskState::default();
                return true;
            }
        }

        // 检查余额或净值是否归零
        if self.capital_state.balance <= 0.0 || self.capital_state.equity <= 0.0 {
            // 余额或净值归零，禁止开仓，直接更新状态为无仓位
            self.action.current_position = Position::None;
            self.action.previous_position = Position::None;
            self.action.risk_in_bar = false;
            self.action.risk_long_trigger = false;
            self.action.risk_short_trigger = false;
            self.risk_state = RiskState::default();
            return true;
        }

        false
    }

    /// 计算并更新仓位状态
    ///
    /// 根据当前价格、信号和状态，计算下一时刻的仓位状态
    ///
    /// # 参数
    /// * `prepared_data` - 准备好的数据，包含 OHLCV 和信号数据
    /// * `params` - 回测参数
    /// * `index` - 当前处理的索引
    /// * `current_atr` - 当前 ATR 值（如果存在）
    pub fn calculate_position(&mut self, params: &BacktestParams) {
        // 保存前一个仓位状态
        self.action.previous_position = self.action.current_position;

        // 在循环中前值依赖： 持仓状态转换
        // 按照上一个仓位的信号执行, 而不是当前仓位信号
        self.action.current_position = match self.action.current_position {
            pos if pos.is_long() => Position::HoldLong, // 多头相关 -> 持多
            pos if pos.is_short() => Position::HoldShort, // 空头相关 -> 持空
            pos if pos.is_exit() => Position::None,     // 离场 -> 无仓位
            _ => self.action.current_position,          // 其他状态保持不变
        };

        // * 举例, 复杂的反手可以是在同一个bar触发三次操作
        // * 先触发一次exit_price设置成开盘价, 平仓前一个仓位
        // * 再触发一次entry_price设置成开盘价, 进场新仓位
        // * 再触发一次exit_price_in_bar设置成实际止盈止损价, 平仓当前仓位(in_bar)
        // * 还有就是如果前一个exit_price_in_bar触发过了, 新的exit_price就不触发了

        // 这个决策链使用 match 语句更清晰地表达互斥逻辑
        match self.action.previous_position {
            // 如果上一个仓位是None, 进场价和离场价设为none
            Position::None => {
                self.action.entry_long_price = None;
                self.action.entry_short_price = None;
                self.action.exit_long_price = None;
                self.action.exit_short_price = None;
                self.action.risk_in_bar = false;
            }
            // 反手, 平空进多, 设置空头离场价, 设置多头进场价
            Position::ExitShortEnterLong => {
                if !self.action.risk_in_bar {
                    self.action.exit_short_price = Some(self.current_bar.open);
                }
                self.action.entry_long_price = Some(self.current_bar.open);
            }
            // 反手, 平多进空, 设置多头离场价, 设置空头进场价
            Position::ExitLongEnterShort => {
                if !self.action.risk_in_bar {
                    self.action.exit_long_price = Some(self.current_bar.open);
                }
                self.action.entry_short_price = Some(self.current_bar.open);
            }
            // 如果上一个仓位是多头离场信号, 那么设置离场价格
            Position::ExitLong => {
                if !self.action.risk_in_bar {
                    self.action.exit_long_price = Some(self.current_bar.open);
                }
            }
            // 如果上一个仓位是空头离场信号, 那么设置离场价格
            Position::ExitShort => {
                if !self.action.risk_in_bar {
                    self.action.exit_short_price = Some(self.current_bar.open);
                }
            }
            // 如果上一个仓位是多头信号, 那么设置进场价格
            Position::EnterLong => {
                self.action.entry_long_price = Some(self.current_bar.open);
            }
            // 如果上一个仓位是空头信号, 那么设置进场价格
            Position::EnterShort => {
                self.action.entry_short_price = Some(self.current_bar.open);
            }
            // 其他情况（HoldLong, HoldShort）不做处理
            _ => {}
        }

        // 第一个bool是是否触发了止损, 第二个会返回最悲观的离场价格
        // next_bar模式,bool会触发, 但是price会返回none, in_bar模式price才会返回非none值
        // 没有多头仓位, 或者没有进场价, 跳过
        // risk_exit_long和risk_exit_short内部无任何仓位状态更新
        self.action.risk_in_bar = false;
        self.action.risk_long_trigger = false;
        self.action.risk_short_trigger = false;

        // 使用 match 语句处理风险触发逻辑
        match (
            self.action.previous_position.is_long(),
            self.action.previous_position.is_short(),
            self.action.entry_long_price.is_some(),
            self.action.entry_short_price.is_some(),
        ) {
            // 多头仓位且有进场价
            (true, false, true, _) => {
                let (should_exit_long, exit_price_long) =
                    self.risk_exit_long(params, self.current_bar.atr);
                if should_exit_long && exit_price_long.is_some() {
                    self.action.exit_long_price = exit_price_long;
                    self.action.risk_in_bar = true;
                }
                self.action.risk_long_trigger = should_exit_long;
            }
            // 空头仓位且有进场价
            (false, true, _, true) => {
                let (should_exit_short, exit_price_short) =
                    self.risk_exit_short(params, self.current_bar.atr);
                if should_exit_short && exit_price_short.is_some() {
                    self.action.exit_short_price = exit_price_short;
                    self.action.risk_in_bar = true;
                }
                self.action.risk_short_trigger = should_exit_short;
            }
            // 其他情况：没有仓位或没有进场价
            _ => {
                self.risk_state = RiskState::default();
            }
        }

        // 更新当前仓位状态
        self.action.current_position = match self.action.previous_position {
            // 持空头仓位的情况
            pos if pos.is_short() && self.should_reverse_to_long() => {
                // 1. 反手信号（平空进多）- 最高优先级
                Position::ExitShortEnterLong
            }
            // 持多头仓位的情况
            pos if pos.is_long() && self.should_reverse_to_short() => {
                // 2. 反手信号（平多进空）- 最高优先级
                Position::ExitLongEnterShort
            }
            pos if pos.is_long() && self.should_exit_long() => Position::ExitLong,
            pos if pos.is_short() && self.should_exit_short() => Position::ExitShort,
            pos if pos.is_none() && self.should_enter_long() => Position::EnterLong,
            pos if pos.is_none() && self.should_enter_short() => Position::EnterShort,
            pos => pos,
        };
    }
}
