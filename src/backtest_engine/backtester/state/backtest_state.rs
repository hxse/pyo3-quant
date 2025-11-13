use super::position::Position;
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
    /// 当前仓位状态（使用枚举提供类型安全）
    pub position: Position,
    /// 前一个仓位状态（使用枚举提供类型安全）
    pub last_position: Position,
    /// 当前持仓的进场价格
    pub entry_price: Option<f64>,
    /// 当前持仓的实际离场价格
    pub exit_price: Option<f64>,
    /// 当前持仓的实际离场价格, in_bar模式触发
    pub exit_price_in_bar: Option<f64>,
    /// 当前交易的手续费
    pub fee: f64,
    /// 累计手续费
    pub fee_cum: f64,
    /// 历史最高净值（用于止损后暂停开仓判断）
    pub peak_equity: f64,
    /// 是否允许开仓（根据止损后暂停/恢复逻辑）
    pub trading_allowed: bool,
    /// 当前百分比跟踪止损价格（仅在使用百分比跟踪止损时有效）
    pub current_tsl_pct_price: f64,
    /// 当前ATR跟踪止损价格（仅在使用ATR跟踪止损时有效）
    pub current_tsl_atr_price: f64,
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
            position: Position::None,      // 初始无仓位
            last_position: Position::None, // 初始无仓位
            entry_price: None,
            exit_price: None,
            exit_price_in_bar: None,
            fee: 0.0,
            fee_cum: 0.0,
            peak_equity: params.initial_capital,
            trading_allowed: true,
            current_tsl_pct_price: 0.0,
            current_tsl_atr_price: 0.0,
            highest_since_entry: 0.0,
            lowest_since_entry: 0.0,
        }
    }
}
