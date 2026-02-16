//! 输出缓冲区初始化模块
//!
//! 负责根据回测参数初始化输出缓冲区

use super::output_struct::OutputBuffers;
use crate::types::BacktestParams;

impl OutputBuffers {
    /// 创建新的输出缓冲区实例
    ///
    /// # 参数
    /// * `params` - 回测参数，用于决定哪些可选列需要初始化
    /// * `capacity` - 缓冲区初始容量，通常等于K线数量
    ///
    /// # 返回
    /// 初始化完成的 OutputBuffers 实例
    pub fn new(params: &BacktestParams, capacity: usize) -> Self {
        Self {
            // 资金状态
            balance: vec![0.0; capacity],
            equity: vec![0.0; capacity],
            trade_pnl_pct: vec![0.0; capacity],
            total_return_pct: vec![0.0; capacity],
            fee: vec![0.0; capacity],
            fee_cum: vec![0.0; capacity],
            current_drawdown: vec![0.0; capacity],

            // 价格列
            entry_long_price: vec![0.0; capacity],
            entry_short_price: vec![0.0; capacity],
            exit_long_price: vec![0.0; capacity],
            exit_short_price: vec![0.0; capacity],

            // 可选列根据参数决定是否初始化
            sl_pct_price_long: if params.is_sl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            sl_pct_price_short: if params.is_sl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_pct_price_long: if params.is_tp_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_pct_price_short: if params.is_tp_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_pct_price_long: if params.is_tsl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_pct_price_short: if params.is_tsl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            // ATR相关列
            atr: if params.has_any_atr_param() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            sl_atr_price_long: if params.is_sl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            sl_atr_price_short: if params.is_sl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_atr_price_long: if params.is_tp_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_atr_price_short: if params.is_tp_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_atr_price_long: if params.is_tsl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_atr_price_short: if params.is_tsl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_psar_price_long: if params.is_tsl_psar_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_psar_price_short: if params.is_tsl_psar_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },

            // Risk State Output
            risk_in_bar_direction: vec![0; capacity],
            first_entry_side: vec![0; capacity],
            frame_state: vec![0; capacity],
        }
    }
}
