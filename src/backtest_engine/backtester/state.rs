use crate::data_conversion::BacktestParams;

/// 回测状态管理结构体
/// 用于跟踪回测过程中的动态状态，包括资金、仓位、交易状态等
pub struct BacktestState {
    /// 初始本金
    pub initial_capital: f64,
    /// 当前账户余额（已实现盈亏）
    pub balance: f64,
    /// 当前账户净值（含未实现盈亏）
    pub equity: f64,
    /// 当前仓位状态
    /// 0=无仓位, 1=进多, 2=持多, 3=平多, 4=平空进多
    /// -1=进空, -2=持空, -3=平空, -4=平多进空
    pub position: i8,
    /// 当前离场模式
    /// 0=无离场, 1=in_bar离场, 2=next_bar离场
    pub exit_mode: u8,
    /// 当前持仓的进场价格
    pub entry_price: f64,
    /// 当前持仓的实际离场价格
    pub exit_price: f64,
    /// 当前交易的手续费
    pub fee: f64,
    /// 累计手续费
    pub fee_cum: f64,
    /// 历史最高净值（用于止损后暂停开仓判断）
    pub peak_equity: f64,
    /// 是否允许开仓（根据止损后暂停/恢复逻辑）
    pub trading_allowed: bool,
    /// 当前跟踪止损价格（仅在使用跟踪止损时有效）
    pub current_tsl_price: f64,
    /// 当前持仓期间最高价（用于跟踪止损计算）
    pub highest_since_entry: f64,
    /// 当前持仓期间最低价（用于跟踪止损计算）
    pub lowest_since_entry: f64,
}

impl BacktestState {
    /// 创建新的回测状态实例
    ///
    /// # 参数
    /// * `params` - 回测参数，用于初始化状态
    ///
    /// # 返回
    /// 初始化完成的 BacktestState 实例
    pub fn new(params: &BacktestParams) -> Self {
        Self {
            initial_capital: params.initial_capital,
            balance: params.initial_capital,
            equity: params.initial_capital,
            position: 0,  // 初始无仓位
            exit_mode: 0, // 初始无离场
            entry_price: 0.0,
            exit_price: 0.0,
            fee: 0.0,
            fee_cum: 0.0,
            peak_equity: params.initial_capital,
            trading_allowed: true,
            current_tsl_price: 0.0,
            highest_since_entry: 0.0,
            lowest_since_entry: 0.0,
        }
    }
}
