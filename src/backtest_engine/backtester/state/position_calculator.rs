use super::backtest_state::BacktestState;
use super::current_bar_data::CurrentBarData;
use super::exit_mode::ExitMode;
use super::position::Position;
use crate::data_conversion::BacktestParams;

impl BacktestState {
    /// 计算并更新仓位状态
    ///
    /// 根据当前价格、信号和状态，计算下一时刻的仓位状态
    ///
    /// # 参数
    /// * `prepared_data` - 准备好的数据，包含 OHLCV 和信号数据
    /// * `params` - 回测参数
    /// * `index` - 当前处理的索引
    /// * `current_atr` - 当前 ATR 值（如果存在）
    pub fn calculate_position(&mut self, params: &BacktestParams, current_bar: CurrentBarData) {
        // 检查 ATR 是否为 NaN（如果使用了 ATR 相关的止损/止盈）
        if let Some(atr_value) = current_bar.atr {
            if atr_value.is_nan() {
                // ATR 为 NaN，跳过开仓，直接更新状态为无仓位
                self.position = Position::None;
                return;
            }
        }

        // 检查余额或净值是否归零
        if self.balance <= 0.0 || self.equity <= 0.0 {
            // 余额或净值归零，禁止开仓，直接更新状态为无仓位
            self.position = Position::None;
            return;
        }

        // 检查是否允许开仓（根据止损后暂停/恢复逻辑）
        if !self.trading_allowed && self.position == Position::None {
            // 不允许开仓且当前无仓位，保持无仓位
            return;
        }

        // * 举例, 复杂的反手可以是在同一个bar触发三次操作
        // * 先触发一次exit_price设置成开盘价, 平仓前一个仓位
        // * 再触发一次entry_price设置成开盘价, 进场新仓位
        // * 再触发一次exit_price_in_bar设置成实际止盈止损价, 平仓当前仓位(in_bar)
        // * 还有就是如果前一个exit_price_in_bar触发过了, 新的exit_price就不触发了

        // 如果上一个仓位是离场(is_exit), 并且上一个in_bar离场价格是none, 那么设置离场价格
        if self.position.is_exit() && self.exit_price_in_bar.is_none() {
            self.exit_price = Some(current_bar.open);
        }

        // 如果上一个仓位是进场信号, 设置进场价格, 不允许hold
        if self.position.is_entry() {
            self.entry_price = Some(current_bar.open);
        }

        // 在循环中前值依赖： 持仓状态转换（优先处理）
        // 必须放在设置开仓价之后, 设置离场价之前, 因为设置开仓价不需要检查hold, 离场价需要
        self.position = match self.position {
            Position::EnterLong | Position::ExitShortEnterLong | Position::HoldLong => {
                Position::HoldLong
            } // 进多或平空进多 -> 持多
            Position::EnterShort | Position::ExitLongEnterShort | Position::HoldShort => {
                Position::HoldShort
            } // 进空或平多进空 -> 持空
            Position::ExitLong | Position::ExitShort => Position::None, // 平多或平空 -> 无仓位
            _ => self.position,                                         // 其他状态保持不变
        };

        // 第一个bool是是否触发了止损, 第二个会返回最悲观的离场价格
        // 只有在in_bar模式, 并且成功触发止损, 第二个价格才会返回非none值
        let (should_exit_long, exit_price_long) =
            self.should_exit_long(&current_bar, params, current_bar.atr);

        let (should_exit_short, exit_price_short) =
            self.should_exit_short(&current_bar, params, current_bar.atr);

        // 设置离场价格
        if should_exit_long {
            if let Some(price) = exit_price_long {
                self.exit_price_in_bar = Some(price);
            }
        }
        if should_exit_short {
            if let Some(price) = exit_price_short {
                self.exit_price_in_bar = Some(price);
            }
        }

        // 根据信号优先级处理
        // 1. 反手信号（平空进多）
        if self.position.is_short()
            && current_bar.enter_long
            && !current_bar.exit_long
            && !current_bar.enter_short
            && (current_bar.exit_short || should_exit_short)
        {
            // 持空 + 进多信号 + (离场信号或止损触发) = 平空进多
            self.position = Position::ExitShortEnterLong;
            return;
        }

        // 2. 反手信号（平多进空）
        if self.position.is_long()
            && current_bar.enter_short
            && !current_bar.exit_short
            && !current_bar.enter_long
            && (current_bar.exit_long || should_exit_long)
        {
            // 持多 + 进空信号 + (离场信号或止损触发) = 平多进空
            self.position = Position::ExitLongEnterShort;
            return;
        }

        // 3. 多头离场信号
        if self.position.is_long() && (current_bar.exit_long || should_exit_long) {
            self.position = Position::ExitLong;
            return;
        }

        // 4. 空头离场信号
        if self.position.is_short() && (current_bar.exit_short || should_exit_short) {
            self.position = Position::ExitShort;
            return;
        }

        // 5. 多头进场信号
        if self.position == Position::None
            && current_bar.enter_long
            && !current_bar.exit_long
            && !current_bar.enter_short
            && !current_bar.exit_short
        {
            self.position = Position::EnterLong;
            return;
        }

        // 6. 空头进场信号
        if self.position == Position::None
            && current_bar.enter_short
            && !current_bar.exit_short
            && !current_bar.enter_long
            && !current_bar.exit_long
        {
            self.position = Position::EnterShort;
            return;
        }
    }
}
