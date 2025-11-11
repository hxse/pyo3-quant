/// 离场模式枚举
/// 提供类型安全和清晰的语义
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExitMode {
    /// 无离场
    None = 0,
    /// in_bar 离场
    InBar = 1,
    /// next_bar 离场
    NextBar = 2,
}

impl ExitMode {
    /// 判断是否为离场模式
    pub fn is_exit(&self) -> bool {
        matches!(self, ExitMode::InBar | ExitMode::NextBar)
    }

    /// 转换为 u8（为了兼容现有代码）
    pub fn as_u8(&self) -> u8 {
        *self as u8
    }
}
