use super::risk_trigger::risk_state::RiskState;
use super::{action::Action, capital_state::CapitalState, current_bar_data::CurrentBarData};
use crate::data_conversion::BacktestParams;

/// 回测状态管理结构体
/// 用于跟踪回测过程中的动态状态，包括资金、仓位、交易状态等
pub struct BacktestState {
    /// 当前交易动作
    pub action: Action,
    pub risk_state: RiskState,
    pub current_bar: CurrentBarData,
    /// 帐户资金计算
    pub capital_state: CapitalState,
}

impl BacktestState {
    /// 创建新的回测状态实例
    ///
    /// # 参数
    /// * `params` - 回测参数，用于初始化状态
    ///
    /// # 返回
    /// 初始化完成的 BacktestState 实例
    pub fn new(params: &BacktestParams) -> Self {
        Self {
            action: Action::default(),
            risk_state: RiskState::default(),
            current_bar: CurrentBarData::default(),
            capital_state: CapitalState::new(params.initial_capital),
        }
    }

    /// 检查是否触发多头反手信号（平空进多）
    ///
    /// # 返回
    /// 如果满足反手条件返回 true，否则返回 false
    pub fn should_reverse_to_long(&self) -> bool {
        self.current_bar.enter_long
            && !self.current_bar.exit_long
            && !self.current_bar.enter_short
            && (self.current_bar.exit_short || self.action.risk_short_trigger)
    }

    /// 检查是否触发空头反手信号（平多进空）
    ///
    /// # 返回
    /// 如果满足反手条件返回 true，否则返回 false
    pub fn should_reverse_to_short(&self) -> bool {
        self.current_bar.enter_short
            && !self.current_bar.exit_short
            && !self.current_bar.enter_long
            && (self.current_bar.exit_long || self.action.risk_long_trigger)
    }

    /// 检查是否触发多头离场信号
    ///
    /// # 返回
    /// 如果满足离场条件返回 true，否则返回 false
    pub fn should_exit_long(&self) -> bool {
        self.current_bar.exit_long || self.action.risk_long_trigger
    }

    /// 检查是否触发空头离场信号
    ///
    /// # 返回
    /// 如果满足离场条件返回 true，否则返回 false
    pub fn should_exit_short(&self) -> bool {
        self.current_bar.exit_short || self.action.risk_short_trigger
    }

    /// 检查是否触发多头进场信号
    ///
    /// # 返回
    /// 如果满足进场条件返回 true，否则返回 false
    pub fn should_enter_long(&self) -> bool {
        self.current_bar.enter_long
            && !self.current_bar.exit_long
            && !self.current_bar.enter_short
            && !self.current_bar.exit_short
    }

    /// 检查是否触发空头进场信号
    ///
    /// # 返回
    /// 如果满足进场条件返回 true，否则返回 false
    pub fn should_enter_short(&self) -> bool {
        self.current_bar.enter_short
            && !self.current_bar.exit_short
            && !self.current_bar.enter_long
            && !self.current_bar.exit_long
    }
}
