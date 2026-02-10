use super::super::data_preparer::PreparedData;
use super::risk_trigger::risk_state::RiskState;
use super::{action::Action, capital_state::CapitalState, current_bar_data::CurrentBarData};
use crate::types::BacktestParams;

/// 回测状态管理结构体
/// 用于跟踪回测过程中的动态状态，包括资金、仓位、交易状态等
pub struct BacktestState<'a> {
    /// 原始数据引用
    pub prepared_data: &'a PreparedData<'a>,
    /// 当前索引
    pub current_index: usize,
    /// 当前交易动作
    pub action: Action,
    pub risk_state: RiskState,
    pub current_bar: CurrentBarData,
    pub prev_bar: CurrentBarData,
    /// 帐户资金计算
    pub capital_state: CapitalState,
    /// 当前帧的事件位掩码
    pub frame_events: u32,
}

impl<'a> BacktestState<'a> {
    /// 创建新的回测状态实例
    ///
    /// # 参数
    /// * `params` - 回测参数，用于初始化状态
    /// * `prepared_data` - 原始数据引用
    ///
    /// # 返回
    /// 初始化完成的 BacktestState 实例
    pub fn new(params: &BacktestParams, prepared_data: &'a PreparedData<'a>) -> Self {
        Self {
            prepared_data,
            current_index: 0,
            action: Action::default(),
            risk_state: RiskState::default(),
            current_bar: CurrentBarData::default(),
            prev_bar: CurrentBarData::default(),
            capital_state: CapitalState::new(params.initial_capital),
            frame_events: 0,
        }
    }

    /// 获取任意偏移的历史数据
    /// offset=0 → current_bar (bar[i])
    /// offset=1 → prev_bar (bar[i-1])
    /// offset=2 → bar[i-2]
    pub fn get_bar(&self, offset: usize) -> Option<CurrentBarData> {
        match offset {
            0 => Some(self.current_bar),
            1 => Some(self.prev_bar),
            n if self.current_index >= n => Some(CurrentBarData::new(
                self.prepared_data,
                self.current_index - n,
            )),
            _ => None,
        }
    }
}

// ================================================================================
// 价格驱动状态判断辅助函数
// ================================================================================

impl<'a> BacktestState<'a> {
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
    pub fn can_entry_long(&self) -> bool {
        self.has_no_position() || self.is_exiting_short()
    }

    /// 判断能否进入空头（无仓位或即将平多反手）
    pub fn can_entry_short(&self) -> bool {
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
        let risk = self.risk_state.in_bar_direction;
        let first = self.action.first_entry_side;

        match (el, xl, es, xs, risk, first) {
            // #1 无仓位
            (false, false, false, false, 0, 0) => "no_position".to_string(),
            // #2 持有多头 (延续)
            (true, false, false, false, 0, 0) => "hold_long".to_string(),
            // #3 持有多头 (进场)
            (true, false, false, false, 0, 1) => "hold_long_first".to_string(),
            // #4 持有空头 (延续)
            (false, false, true, false, 0, 0) => "hold_short".to_string(),
            // #5 持有空头 (进场)
            (false, false, true, false, 0, -1) => "hold_short_first".to_string(),
            // #6 多头离场 (信号)
            (true, true, false, false, 0, 0) => "exit_long_signal".to_string(),
            // #7 多头离场 (持仓后风险)
            (true, true, false, false, 1, 0) => "exit_long_risk".to_string(),
            // #8 多头离场 (秒杀风险)
            (true, true, false, false, 1, 1) => "exit_long_risk_first".to_string(),
            // #9 空头离场 (信号)
            (false, false, true, true, 0, 0) => "exit_short_signal".to_string(),
            // #10 空头离场 (持仓后风险)
            (false, false, true, true, -1, 0) => "exit_short_risk".to_string(),
            // #11 空头离场 (秒杀风险)
            (false, false, true, true, -1, -1) => "exit_short_risk_first".to_string(),
            // #12 反手 L->S
            (true, true, true, false, 0, -1) => "reversal_L_to_S".to_string(),
            // #13 反手 S->L
            (true, false, true, true, 0, 1) => "reversal_S_to_L".to_string(),
            // #14 反手风险 -> L
            (true, true, true, true, 1, 1) => "reversal_to_L_risk".to_string(),
            // #15 反手风险 -> S
            (true, true, true, true, -1, -1) => "reversal_to_S_risk".to_string(),
            _ => format!("invalid_state:({el},{xl},{es},{xs},risk:{risk},first:{first})"),
        }
    }
}
