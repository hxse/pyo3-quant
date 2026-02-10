use super::super::data_preparer::PreparedData;
use super::risk_trigger::risk_state::RiskState;
use super::{
    action::Action, capital_state::CapitalState, current_bar_data::CurrentBarData,
    frame_state::FrameState,
};
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
    /// 当前帧的状态
    pub frame_state: FrameState,
    /// 是否被跳空拦截进场
    pub gap_blocked: bool,
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
            frame_state: FrameState::NoPosition,
            gap_blocked: false,
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

    /// 根据当前所有字段推断 FrameState
    pub fn infer_frame_state(&mut self) {
        self.frame_state = FrameState::infer(
            self.action.entry_long_price.is_some(),
            self.action.exit_long_price.is_some(),
            self.action.entry_short_price.is_some(),
            self.action.exit_short_price.is_some(),
            self.risk_state.in_bar_direction,
            self.action.first_entry_side,
            self.gap_blocked,
        );
    }
}
