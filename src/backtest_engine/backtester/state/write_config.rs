//! 分组写入配置模块
//!
//! 将可选列按类型组(PCT/ATR/PSAR)和功能组(SL/TP/TSL)分层，
//! 减少主循环中的分支检查次数。

use crate::data_conversion::BacktestParams;

/// 功能组标志位
///
/// 用于标记某个类型组(PCT/ATR)内启用了哪些功能(SL/TP/TSL)
#[derive(Clone, Copy, Debug, Default)]
pub struct FuncFlags {
    pub has_sl: bool,
    pub has_tp: bool,
    pub has_tsl: bool,
}

impl FuncFlags {
    pub fn is_empty(&self) -> bool {
        !self.has_sl && !self.has_tp && !self.has_tsl
    }
}

/// 分组写入配置
///
/// 在主循环开始前根据 BacktestParams 构建，
/// 用于指导 OutputRow 按组写入可选列。
#[derive(Clone, Copy, Debug, Default)]
pub struct WriteConfig {
    /// PCT 组需要写入的功能列 (SL_PCT, TP_PCT, TSL_PCT)
    pub pct_funcs: FuncFlags,
    /// ATR 组需要写入的功能列 (SL_ATR, TP_ATR, TSL_ATR)
    pub atr_funcs: FuncFlags,
    /// 是否需要写入 TSL_PSAR 列 (PSAR 只有 TSL)
    pub has_psar: bool,
}

impl WriteConfig {
    /// 从 BacktestParams 构建写入配置
    pub fn from_params(params: &BacktestParams) -> Self {
        let mut config = Self::default();

        // PCT 组
        if params.is_sl_pct_param_valid() {
            config.pct_funcs.has_sl = true;
        }
        if params.is_tp_pct_param_valid() {
            config.pct_funcs.has_tp = true;
        }
        if params.is_tsl_pct_param_valid() {
            config.pct_funcs.has_tsl = true;
        }

        // ATR 组
        if params.is_sl_atr_param_valid() {
            config.atr_funcs.has_sl = true;
        }
        if params.is_tp_atr_param_valid() {
            config.atr_funcs.has_tp = true;
        }
        if params.is_tsl_atr_param_valid() {
            config.atr_funcs.has_tsl = true;
        }

        // PSAR 组
        config.has_psar = params.is_tsl_psar_param_valid();

        config
    }
}
