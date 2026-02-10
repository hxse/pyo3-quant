//! 输出缓冲区结构定义
//!
//! 定义回测输出缓冲区的数据结构

/// 回测输出缓冲区结构体
/// 用于收集每根K线的输出结果，包括固定列和可选列
pub struct OutputBuffers {
    // === 固定列 ===
    /// 账户余额，带复利
    pub balance: Vec<f64>,
    /// 账户净值（含未实现盈亏），带复利
    pub equity: Vec<f64>,
    /// 当前回撤比例
    pub current_drawdown: Vec<f64>,

    /// 单笔回报率
    pub trade_pnl_pct: Vec<f64>,
    /// 累计回报率，带复利
    pub total_return_pct: Vec<f64>,
    /// 单笔离场结算手续费
    pub fee: Vec<f64>,
    /// 当前历史累计手续费
    pub fee_cum: Vec<f64>,

    // === 价格列（价格驱动状态核心） ===
    /// 多头进场价格
    pub entry_long_price: Vec<f64>,
    /// 空头进场价格
    pub entry_short_price: Vec<f64>,
    /// 多头离场价格
    pub exit_long_price: Vec<f64>,
    /// 空头离场价格
    pub exit_short_price: Vec<f64>,

    // === 可选列（多空分离） ===
    /// 百分比止损价格（多头）
    pub sl_pct_price_long: Option<Vec<f64>>,
    /// 百分比止损价格（空头）
    pub sl_pct_price_short: Option<Vec<f64>>,
    /// 百分比止盈价格（多头）
    pub tp_pct_price_long: Option<Vec<f64>>,
    /// 百分比止盈价格（空头）
    pub tp_pct_price_short: Option<Vec<f64>>,
    /// 百分比跟踪止损价格（多头）
    pub tsl_pct_price_long: Option<Vec<f64>>,
    /// 百分比跟踪止损价格（空头）
    pub tsl_pct_price_short: Option<Vec<f64>>,

    /// ATR指标值（可选）
    pub atr: Option<Vec<f64>>,
    /// ATR止损价格（多头）
    pub sl_atr_price_long: Option<Vec<f64>>,
    /// ATR止损价格（空头）
    pub sl_atr_price_short: Option<Vec<f64>>,
    /// ATR止盈价格（多头）
    pub tp_atr_price_long: Option<Vec<f64>>,
    /// ATR止盈价格（空头）
    pub tp_atr_price_short: Option<Vec<f64>>,
    /// ATR跟踪止损价格（多头）
    pub tsl_atr_price_long: Option<Vec<f64>>,
    /// ATR跟踪止损价格（空头）
    pub tsl_atr_price_short: Option<Vec<f64>>,

    /// PSAR跟踪止损价格（多头）
    pub tsl_psar_price_long: Option<Vec<f64>>,
    /// PSAR跟踪止损价格（空头）
    pub tsl_psar_price_short: Option<Vec<f64>>,

    // === Risk State Output ===
    /// Risk 是否 In-Bar 离场（0=无, 1=多, -1=空）
    pub risk_in_bar_direction: Vec<i8>,
    /// 首次进场方向（0=无, 1=多头, -1=空头）
    pub first_entry_side: Vec<i8>,
    /// 帧事件位掩码
    pub frame_events: Vec<u32>,
}
