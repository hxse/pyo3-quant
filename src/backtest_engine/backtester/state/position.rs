/// 仓位状态枚举
/// 使用数值枚举提供类型安全和清晰的语义
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Position {
    /// 无仓位
    None = 0,
    /// 进多
    EnterLong = 1,
    /// 持多
    HoldLong = 2,
    /// 平多
    ExitLong = 3,
    /// 平空进多
    ExitShortEnterLong = 4,
    /// 进空
    EnterShort = -1,
    /// 持空
    HoldShort = -2,
    /// 平空
    ExitShort = -3,
    /// 平多进空
    ExitLongEnterShort = -4,
}

impl Position {
    /// 判断是否为无仓位
    pub fn is_none(&self) -> bool {
        matches!(self, Position::None)
    }

    /// 判断是否为多头仓位（进多或持多）
    pub fn is_long(&self) -> bool {
        matches!(
            self,
            Position::EnterLong | Position::HoldLong | Position::ExitShortEnterLong
        )
    }

    /// 判断是否为空头仓位（进空或持空）
    pub fn is_short(&self) -> bool {
        matches!(
            self,
            Position::EnterShort | Position::HoldShort | Position::ExitLongEnterShort
        )
    }

    /// 判断是否为进场仓位
    pub fn is_entry(&self) -> bool {
        matches!(
            self,
            Position::EnterLong
                | Position::EnterShort
                | Position::ExitLongEnterShort
                | Position::ExitShortEnterLong
        )
    }

    /// 判断是否为离场仓位
    pub fn is_exit(&self) -> bool {
        matches!(
            self,
            Position::ExitLong
                | Position::ExitShort
                | Position::ExitLongEnterShort
                | Position::ExitShortEnterLong
        )
    }

    /// 判断是否为反手仓位
    pub fn is_reversal(&self) -> bool {
        matches!(
            self,
            Position::ExitShortEnterLong | Position::ExitLongEnterShort
        )
    }

    /// 转换为 i8（为了兼容现有代码）
    pub fn as_i8(&self) -> i8 {
        *self as i8
    }
}
