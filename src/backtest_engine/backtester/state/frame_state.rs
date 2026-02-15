use pyo3::prelude::*;

/// 帧状态枚举（替代 frame_events 位掩码 + debug_inferred_state）
///
/// 在 calculate_position 结束后，由价格组合 + risk + first_entry_side 直接推断。
/// 增加 #15 GapBlocked 状态覆盖进场被跳空拦截的场景。
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum FrameState {
    #[default]
    NoPosition = 0, // #1
    HoldLong = 1,            // #2
    HoldLongFirst = 2,       // #3
    HoldShort = 3,           // #4
    HoldShortFirst = 4,      // #5
    ExitLongSignal = 5,      // #6
    ExitLongRisk = 6,        // #7
    ExitLongRiskFirst = 7,   // #8
    ExitShortSignal = 8,     // #9
    ExitShortRisk = 9,       // #10
    ExitShortRiskFirst = 10, // #11
    ReversalLToS = 11,       // #12
    ReversalSToL = 12,       // #13
    ReversalToLRisk = 13,    // #14
    ReversalToSRisk = 14,    // #15
    GapBlocked = 15,         // #16 新增
    CapitalExhausted = 16,   // #17 新增：资金耗尽
    Invalid = 255,           // 非法状态
}

impl FrameState {
    /// 从价格组合推断状态（替代 debug_inferred_state）
    pub fn infer(
        el: bool,
        xl: bool,
        es: bool,
        xs: bool,
        risk: i8,
        first: i8,
        gap_blocked: bool,
    ) -> Self {
        // GAP_BLOCKED 优先：进场被拦截时状态为 NoPosition，但需要区分
        if gap_blocked {
            return Self::GapBlocked;
        }
        match (el, xl, es, xs, risk, first) {
            (false, false, false, false, 0, 0) => Self::NoPosition,
            (true, false, false, false, 0, 0) => Self::HoldLong,
            (true, false, false, false, 0, 1) => Self::HoldLongFirst,
            (false, false, true, false, 0, 0) => Self::HoldShort,
            (false, false, true, false, 0, -1) => Self::HoldShortFirst,
            (true, true, false, false, 0, 0) => Self::ExitLongSignal,
            (true, true, false, false, 1, 0) => Self::ExitLongRisk,
            (true, true, false, false, 1, 1) => Self::ExitLongRiskFirst,
            (false, false, true, true, 0, 0) => Self::ExitShortSignal,
            (false, false, true, true, -1, 0) => Self::ExitShortRisk,
            (false, false, true, true, -1, -1) => Self::ExitShortRiskFirst,
            (true, true, true, false, 0, -1) => Self::ReversalLToS,
            (true, false, true, true, 0, 1) => Self::ReversalSToL,
            (true, true, true, true, 1, 1) => Self::ReversalToLRisk,
            (true, true, true, true, -1, -1) => Self::ReversalToSRisk,
            _ => Self::Invalid,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::NoPosition => "no_position",
            Self::HoldLong => "hold_long",
            Self::HoldLongFirst => "hold_long_first",
            Self::HoldShort => "hold_short",
            Self::HoldShortFirst => "hold_short_first",
            Self::ExitLongSignal => "exit_long_signal",
            Self::ExitLongRisk => "exit_long_risk",
            Self::ExitLongRiskFirst => "exit_long_risk_first",
            Self::ExitShortSignal => "exit_short_signal",
            Self::ExitShortRisk => "exit_short_risk",
            Self::ExitShortRiskFirst => "exit_short_risk_first",
            Self::ReversalLToS => "reversal_L_to_S",
            Self::ReversalSToL => "reversal_S_to_L",
            Self::ReversalToLRisk => "reversal_to_L_risk",
            Self::ReversalToSRisk => "reversal_to_S_risk",
            Self::GapBlocked => "gap_blocked",
            Self::CapitalExhausted => "capital_exhausted",
            Self::Invalid => "invalid_state",
        }
    }
}
use pyo3_stub_gen::derive::*;

/// 将状态 ID 转为名称（PyO3 导出，替代 bitmask_to_event_names）
#[gen_stub_pyfunction(module = "pyo3_quant.backtest_engine.backtester")]
#[pyfunction(name = "frame_state_name")]
pub fn py_frame_state_name(state_id: u8) -> String {
    let state = match state_id {
        0 => FrameState::NoPosition,
        1 => FrameState::HoldLong,
        2 => FrameState::HoldLongFirst,
        3 => FrameState::HoldShort,
        4 => FrameState::HoldShortFirst,
        5 => FrameState::ExitLongSignal,
        6 => FrameState::ExitLongRisk,
        7 => FrameState::ExitLongRiskFirst,
        8 => FrameState::ExitShortSignal,
        9 => FrameState::ExitShortRisk,
        10 => FrameState::ExitShortRiskFirst,
        11 => FrameState::ReversalLToS,
        12 => FrameState::ReversalSToL,
        13 => FrameState::ReversalToLRisk,
        14 => FrameState::ReversalToSRisk,
        15 => FrameState::GapBlocked,
        16 => FrameState::CapitalExhausted,
        _ => FrameState::Invalid,
    };
    state.as_str().to_string()
}
