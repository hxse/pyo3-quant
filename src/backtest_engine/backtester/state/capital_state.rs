/// 回测动作结构体
/// 用于记录回测过程中的交易动作和状态
#[derive(Debug, Clone)]
pub struct CapitalState {
    /// 初始本金
    pub initial_capital: f64,
    /// 当前账户余额（已实现盈亏）
    pub balance: f64,
    /// 当前账户净值（含未实现盈亏）
    pub equity: f64,
    /// 单笔盈亏百分比
    pub trade_pnl_pct: f64,
    /// 相对初始资金的总回报率
    pub total_return_pct: f64,
    /// 当前交易的手续费
    pub fee: f64,
    /// 累计手续费
    pub fee_cum: f64,
    /// 历史最高净值（用于止损后暂停开仓判断）
    pub peak_equity: f64,
}
impl CapitalState {
    /// 使用指定的初始本金创建新的 CapitalState
    pub fn new(initial_capital: f64) -> Self {
        // 初始时，余额、净值和历史最高净值都等于初始本金
        Self {
            initial_capital,
            balance: initial_capital,
            equity: initial_capital,
            // 以下字段使用默认值
            trade_pnl_pct: 0.0,
            total_return_pct: 0.0,
            fee: 0.0,
            fee_cum: 0.0,
            peak_equity: initial_capital, // 初始最高净值设为初始本金
        }
    }
}
