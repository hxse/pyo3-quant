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
    pub prev_bar: CurrentBarData,
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
            prev_bar: CurrentBarData::default(),
            capital_state: CapitalState::new(params.initial_capital),
        }
    }
}

// ================================================================================
// 价格驱动状态判断辅助函数
// ================================================================================

impl BacktestState {
    /// 判断是否持有多头仓位
    pub fn has_long_position(&self) -> bool {
        self.action.entry_long_price.is_some() && self.action.exit_long_price.is_none()
    }

    /// 判断是否持有空头仓位
    pub fn has_short_position(&self) -> bool {
        self.action.entry_short_price.is_some() && self.action.exit_short_price.is_none()
    }

    /// 判断是否无仓位
    pub fn has_no_position(&self) -> bool {
        self.action.entry_long_price.is_none() && self.action.entry_short_price.is_none()
    }

    /// 判断能否进入多头（无仓位或即将平空反手）
    pub fn can_enter_long(&self) -> bool {
        self.has_no_position() || self.is_exiting_short()
    }

    /// 判断能否进入空头（无仓位或即将平多反手）
    pub fn can_enter_short(&self) -> bool {
        self.has_no_position() || self.is_exiting_long()
    }

    /// 判断是否正在多头离场（entry和exit同时存在）
    pub fn is_exiting_long(&self) -> bool {
        self.action.entry_long_price.is_some() && self.action.exit_long_price.is_some()
    }

    /// 判断是否正在空头离场（entry和exit同时存在）
    pub fn is_exiting_short(&self) -> bool {
        self.action.entry_short_price.is_some() && self.action.exit_short_price.is_some()
    }

    /// Debug辅助：推断当前状态（英文，供调试）
    /// 可在DataFrame转换时添加为独立的debug列
    #[allow(dead_code)]
    pub fn debug_inferred_state(&self) -> String {
        let el = self.action.entry_long_price.is_some();
        let xl = self.action.exit_long_price.is_some();
        let es = self.action.entry_short_price.is_some();
        let xs = self.action.exit_short_price.is_some();
        let risk_long = self.risk_state.should_exit_in_bar_long() as i8;
        let risk_short = self.risk_state.should_exit_in_bar_short() as i8;
        // 计算 risk 状态：1 表示多头 in_bar, -1 表示空头 in_bar, 0 表示无或 next_bar
        let risk = if risk_long != 0 {
            1
        } else if risk_short != 0 {
            -1
        } else {
            0
        };

        match (el, xl, es, xs, risk) {
            (true, true, true, true, -1) => "reversal_short_risk".to_string(),
            (true, true, true, true, 1) => "reversal_long_risk".to_string(),
            (true, true, true, true, 0) => "reversal_complex".to_string(),
            (true, true, true, false, _) => "reversal_long_to_short".to_string(),
            (true, false, true, true, _) => "reversal_short_to_long".to_string(),
            (true, true, false, false, 1) => "exit_long_risk".to_string(),
            (true, true, false, false, 0) => "exit_long_signal".to_string(),
            (false, false, true, true, -1) => "exit_short_risk".to_string(),
            (false, false, true, true, 0) => "exit_short_signal".to_string(),
            (true, false, false, false, _) => "hold_long".to_string(),
            (false, false, true, false, _) => "hold_short".to_string(),
            (false, false, false, false, _) => "no_position".to_string(),
            _ => "invalid_state".to_string(),
        }
    }
}
