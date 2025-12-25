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

impl Action {
    /// 重置所有价格字段
    pub fn reset_prices(&mut self) {
        self.entry_long_price = None;
        self.entry_short_price = None;
        self.exit_long_price = None;
        self.exit_short_price = None;
        // 注意：is_first_entry_xxx 不需要在这里重置，它们由 position_calculator 控制
    }
}
