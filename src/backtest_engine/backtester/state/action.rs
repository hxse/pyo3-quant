/// 回测动作结构体（价格驱动设计）
/// 用4个价格字段的组合推断所有状态，无需显式Position枚举
#[derive(Debug, Clone, Default)]
pub struct Action {
    // === 价格字段（状态机变量，默认延续） ===
    /// 多头进场价格
    pub entry_long_price: Option<f64>,
    /// 空头进场价格
    pub entry_short_price: Option<f64>,
    /// 多头离场价格
    pub exit_long_price: Option<f64>,
    /// 空头离场价格
    pub exit_short_price: Option<f64>,

    /// 首次进场方向：0=无, 1=多头, -1=空头
    pub first_entry_side: i8,
}

// 结构体已派生 Default，无需显式 new
