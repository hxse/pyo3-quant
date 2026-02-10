//! 帧事件位掩码定义
//!
//! 用于在输出 DataFrame 中记录每帧发生的事件，以便于追踪和调试。

use pyo3::prelude::*;

/// 事件位定义
pub mod event_bits {
    /// 进场多头
    pub const ENTRY_LONG: u32 = 1 << 0;
    /// 进场空头
    pub const ENTRY_SHORT: u32 = 1 << 1;
    /// 策略离场多头
    pub const EXIT_LONG: u32 = 1 << 2;
    /// 策略离场空头
    pub const EXIT_SHORT: u32 = 1 << 3;
    /// 风控离场多头
    pub const RISK_EXIT_LONG: u32 = 1 << 4;
    /// 风控离场空头
    pub const RISK_EXIT_SHORT: u32 = 1 << 5;
    /// In-Bar 离场多头（特定标识）
    pub const RISK_IN_BAR_LONG: u32 = 1 << 6;
    /// In-Bar 离场空头（特定标识）
    pub const RISK_IN_BAR_SHORT: u32 = 1 << 7;
    /// 重置多头状态
    pub const RESET_LONG: u32 = 1 << 8;
    /// 重置空头状态
    pub const RESET_SHORT: u32 = 1 << 9;
    /// 由于数据跳空导致进场被阻止
    pub const GAP_BLOCKED: u32 = 1 << 10;
}

/// 将位掩码解码为事件名称列表（用于调试和测试）
#[pyfunction(name = "bitmask_to_event_names")]
pub fn py_bitmask_to_event_names(mask: u32) -> Vec<String> {
    let mut names = Vec::new();
    if mask & event_bits::ENTRY_LONG != 0 {
        names.push("EntryLong".to_string());
    }
    if mask & event_bits::ENTRY_SHORT != 0 {
        names.push("EntryShort".to_string());
    }
    if mask & event_bits::EXIT_LONG != 0 {
        names.push("ExitLong".to_string());
    }
    if mask & event_bits::EXIT_SHORT != 0 {
        names.push("ExitShort".to_string());
    }
    if mask & event_bits::RISK_EXIT_LONG != 0 {
        names.push("RiskExitLong".to_string());
    }
    if mask & event_bits::RISK_EXIT_SHORT != 0 {
        names.push("RiskExitShort".to_string());
    }
    if mask & event_bits::RISK_IN_BAR_LONG != 0 {
        names.push("RiskInBarLong".to_string());
    }
    if mask & event_bits::RISK_IN_BAR_SHORT != 0 {
        names.push("RiskInBarShort".to_string());
    }
    if mask & event_bits::RESET_LONG != 0 {
        names.push("ResetLong".to_string());
    }
    if mask & event_bits::RESET_SHORT != 0 {
        names.push("ResetShort".to_string());
    }
    if mask & event_bits::GAP_BLOCKED != 0 {
        names.push("GapBlocked".to_string());
    }
    names
}
