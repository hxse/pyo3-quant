use super::position_state::Position;

/// 回测动作结构体
/// 用于记录回测过程中的交易动作和状态
#[derive(Debug, Clone)]
pub struct Action {
    /// 当前仓位状态
    pub current_position: Position,
    /// 上一个仓位状态
    pub previous_position: Position,
    /// 多头进场价格
    pub entry_long_price: Option<f64>,
    /// 空头进场价格
    pub entry_short_price: Option<f64>,
    /// 多头离场价格
    pub exit_long_price: Option<f64>,
    /// 空头离场价格
    pub exit_short_price: Option<f64>,

    /// 是否触发多头止盈止损
    pub risk_long_trigger: bool,
    /// 是否触发空头止盈止损
    pub risk_short_trigger: bool,
    /// 是否跳过下一根K线
    pub risk_in_bar: bool,
}

impl Default for Action {
    fn default() -> Self {
        Self {
            current_position: Position::None,
            previous_position: Position::None,
            entry_long_price: None,
            entry_short_price: None,
            exit_long_price: None,
            exit_short_price: None,

            risk_long_trigger: false,
            risk_short_trigger: false,
            risk_in_bar: false,
        }
    }
}
