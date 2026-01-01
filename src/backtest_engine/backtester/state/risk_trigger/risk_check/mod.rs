// 风控触发检查子模块

mod outcome_applier;
mod threshold_updater;
mod trigger_checker;

use super::risk_price_calc::Direction;
use crate::backtest_engine::backtester::state::backtest_state::BacktestState;
use crate::types::BacktestParams;

/// 风控触发状态详细结果
#[derive(Debug, Clone, Copy, Default)]
pub(super) struct RiskTriggerResult {
    pub sl_pct_triggered: bool,
    pub sl_atr_triggered: bool,
    pub tp_pct_triggered: bool,
    pub tp_atr_triggered: bool,
    pub tsl_pct_triggered: bool,
    pub tsl_atr_triggered: bool,
    pub tsl_psar_triggered: bool,
}

impl RiskTriggerResult {
    /// 是否有任何止损触发
    pub fn sl_triggered(&self) -> bool {
        self.sl_pct_triggered || self.sl_atr_triggered
    }

    /// 是否有任何止盈触发
    pub fn tp_triggered(&self) -> bool {
        self.tp_pct_triggered || self.tp_atr_triggered
    }

    /// 是否有任何跟踪止损触发
    pub fn tsl_triggered(&self) -> bool {
        self.tsl_pct_triggered || self.tsl_atr_triggered || self.tsl_psar_triggered
    }

    /// 是否有任何风控条件触发
    pub fn any_triggered(&self) -> bool {
        self.sl_triggered() || self.tp_triggered() || self.tsl_triggered()
    }
}

impl<'a> BacktestState<'a> {
    /// 通用 Risk 离场检查逻辑
    pub(crate) fn check_risk_exit(&mut self, params: &BacktestParams, direction: Direction) {
        // 1. 判断是否首次进场
        let is_first_entry = match direction {
            Direction::Long => self.action.first_entry_side == 1,
            Direction::Short => self.action.first_entry_side == -1,
        };

        // 2. 初始化/更新 Risk 价格
        self.update_risk_thresholds(params, is_first_entry, direction);

        // 3. 检查触发条件
        let trigger_result = self.check_risk_triggers(params, direction);

        // 4. 应用结果
        self.apply_risk_outcome(params, direction, trigger_result);
    }
}
