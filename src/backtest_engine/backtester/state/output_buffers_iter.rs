use super::write_config::WriteConfig;
use crate::backtest_engine::backtester::output::OutputBuffers;
use crate::backtest_engine::backtester::state::BacktestState;

impl OutputBuffers {
    /// 按索引写入单行数据（统一写入接口）
    ///
    /// 用于初始化阶段（row 0/1）的随机访问写入。
    /// 主循环中使用 OutputBuffersIter 进行顺序写入以获得更高性能。
    #[inline]
    pub fn write_row(&mut self, i: usize, state: &BacktestState<'_>, config: &WriteConfig) {
        // === 固定列 ===
        self.balance[i] = state.capital_state.balance;
        self.equity[i] = state.capital_state.equity;
        self.trade_pnl_pct[i] = state.capital_state.trade_pnl_pct;
        self.total_return_pct[i] = state.capital_state.total_return_pct;
        self.fee[i] = state.capital_state.fee;
        self.fee_cum[i] = state.capital_state.fee_cum;
        self.current_drawdown[i] = state.capital_state.current_drawdown;
        self.entry_long_price[i] = state.action.entry_long_price.unwrap_or(f64::NAN);
        self.entry_short_price[i] = state.action.entry_short_price.unwrap_or(f64::NAN);
        self.exit_long_price[i] = state.action.exit_long_price.unwrap_or(f64::NAN);
        self.exit_short_price[i] = state.action.exit_short_price.unwrap_or(f64::NAN);
        self.risk_in_bar_direction[i] = state.risk_state.in_bar_direction;
        self.first_entry_side[i] = state.action.first_entry_side;
        self.frame_events[i] = state.frame_events;

        // === 可选列（从 WriteConfig 判断是否需要写入） ===

        // PCT 组
        if !config.pct_funcs.is_empty() {
            if config.pct_funcs.has_sl {
                if let (Some(l), Some(s)) = (
                    self.sl_pct_price_long.as_mut(),
                    self.sl_pct_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.pct_funcs.has_tp {
                if let (Some(l), Some(s)) = (
                    self.tp_pct_price_long.as_mut(),
                    self.tp_pct_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.pct_funcs.has_tsl {
                if let (Some(l), Some(s)) = (
                    self.tsl_pct_price_long.as_mut(),
                    self.tsl_pct_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
                }
            }
        }

        // ATR 组
        if !config.atr_funcs.is_empty() {
            if config.atr_funcs.has_sl {
                if let (Some(l), Some(s)) = (
                    self.sl_atr_price_long.as_mut(),
                    self.sl_atr_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.atr_funcs.has_tp {
                if let (Some(l), Some(s)) = (
                    self.tp_atr_price_long.as_mut(),
                    self.tp_atr_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.atr_funcs.has_tsl {
                if let (Some(l), Some(s)) = (
                    self.tsl_atr_price_long.as_mut(),
                    self.tsl_atr_price_short.as_mut(),
                ) {
                    l[i] = state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
                    s[i] = state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
                }
            }
        }

        // PSAR 组
        if config.has_psar {
            if let (Some(l), Some(s)) = (
                self.tsl_psar_price_long.as_mut(),
                self.tsl_psar_price_short.as_mut(),
            ) {
                l[i] = state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
                s[i] = state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
            }
        }

        // ATR column (always write if enabled)
        if let Some(atr) = self.atr.as_mut() {
            atr[i] = state.current_bar.atr.unwrap_or(f64::NAN);
        }
    }
}

/// 输出缓冲区行数据结构体
/// 包含当前行所有输出列的可变引用
pub struct OutputRow<'a> {
    // 固定列
    pub balance: &'a mut f64,
    pub equity: &'a mut f64,
    pub trade_pnl_pct: &'a mut f64,
    pub total_return_pct: &'a mut f64,
    pub fee: &'a mut f64,
    pub fee_cum: &'a mut f64,
    pub current_drawdown: &'a mut f64,
    pub entry_long_price: &'a mut f64,
    pub entry_short_price: &'a mut f64,
    pub exit_long_price: &'a mut f64,
    pub exit_short_price: &'a mut f64,
    pub risk_in_bar_direction: &'a mut i8,
    pub first_entry_side: &'a mut i8,
    pub frame_events: &'a mut u32,
    // 可选列
    pub sl_pct_long: Option<&'a mut f64>,
    pub sl_pct_short: Option<&'a mut f64>,
    pub tp_pct_long: Option<&'a mut f64>,
    pub tp_pct_short: Option<&'a mut f64>,
    pub tsl_pct_long: Option<&'a mut f64>,
    pub tsl_pct_short: Option<&'a mut f64>,
    pub sl_atr_long: Option<&'a mut f64>,
    pub sl_atr_short: Option<&'a mut f64>,
    pub tp_atr_long: Option<&'a mut f64>,
    pub tp_atr_short: Option<&'a mut f64>,
    pub tsl_atr_long: Option<&'a mut f64>,
    pub tsl_atr_short: Option<&'a mut f64>,
    pub tsl_psar_long: Option<&'a mut f64>,
    pub tsl_psar_short: Option<&'a mut f64>,
}

impl<'a> OutputRow<'a> {
    /// 写入固定列数据
    #[inline]
    fn write_fixed(&mut self, state: &BacktestState<'_>) {
        *self.balance = state.capital_state.balance;
        *self.equity = state.capital_state.equity;
        *self.trade_pnl_pct = state.capital_state.trade_pnl_pct;
        *self.total_return_pct = state.capital_state.total_return_pct;
        *self.fee = state.capital_state.fee;
        *self.fee_cum = state.capital_state.fee_cum;
        *self.current_drawdown = state.capital_state.current_drawdown;
        *self.entry_long_price = state.action.entry_long_price.unwrap_or(f64::NAN);
        *self.entry_short_price = state.action.entry_short_price.unwrap_or(f64::NAN);
        *self.exit_long_price = state.action.exit_long_price.unwrap_or(f64::NAN);
        *self.exit_short_price = state.action.exit_short_price.unwrap_or(f64::NAN);
        *self.risk_in_bar_direction = state.risk_state.in_bar_direction;
        *self.first_entry_side = state.action.first_entry_side;
        *self.frame_events = state.frame_events;
    }

    /// 按组写入可选列数据
    ///
    /// 使用 WriteConfig 按类型组(PCT/ATR/PSAR)和功能组(SL/TP/TSL)分层检查，
    /// 减少分支次数。
    #[inline]
    fn write_optional_grouped(&mut self, state: &BacktestState<'_>, config: &WriteConfig) {
        // PCT 组
        if !config.pct_funcs.is_empty() {
            if config.pct_funcs.has_sl {
                **self.sl_pct_long.as_mut().unwrap() =
                    state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
                **self.sl_pct_short.as_mut().unwrap() =
                    state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
            }
            if config.pct_funcs.has_tp {
                **self.tp_pct_long.as_mut().unwrap() =
                    state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
                **self.tp_pct_short.as_mut().unwrap() =
                    state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
            }
            if config.pct_funcs.has_tsl {
                **self.tsl_pct_long.as_mut().unwrap() =
                    state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
                **self.tsl_pct_short.as_mut().unwrap() =
                    state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
            }
        }

        // ATR 组
        if !config.atr_funcs.is_empty() {
            if config.atr_funcs.has_sl {
                **self.sl_atr_long.as_mut().unwrap() =
                    state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
                **self.sl_atr_short.as_mut().unwrap() =
                    state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
            }
            if config.atr_funcs.has_tp {
                **self.tp_atr_long.as_mut().unwrap() =
                    state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
                **self.tp_atr_short.as_mut().unwrap() =
                    state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
            }
            if config.atr_funcs.has_tsl {
                **self.tsl_atr_long.as_mut().unwrap() =
                    state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
                **self.tsl_atr_short.as_mut().unwrap() =
                    state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
            }
        }

        // PSAR 组 (只有 TSL)
        if config.has_psar {
            **self.tsl_psar_long.as_mut().unwrap() =
                state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
            **self.tsl_psar_short.as_mut().unwrap() =
                state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
        }
    }

    /// 从 BacktestState 写入数据到当前行（分组优化版本）
    ///
    /// 先写入固定列，再按组写入可选列。
    #[inline]
    pub fn write(&mut self, state: &BacktestState<'_>, config: &WriteConfig) {
        self.write_fixed(state);
        self.write_optional_grouped(state, config);
    }
}

/// 输出缓冲区迭代器，每次返回一行的可变引用
pub struct OutputBuffersIter<'a> {
    // 固定列迭代器
    balance: std::slice::IterMut<'a, f64>,
    equity: std::slice::IterMut<'a, f64>,
    trade_pnl_pct: std::slice::IterMut<'a, f64>,
    total_return_pct: std::slice::IterMut<'a, f64>,
    fee: std::slice::IterMut<'a, f64>,
    fee_cum: std::slice::IterMut<'a, f64>,
    current_drawdown: std::slice::IterMut<'a, f64>,
    entry_long_price: std::slice::IterMut<'a, f64>,
    entry_short_price: std::slice::IterMut<'a, f64>,
    exit_long_price: std::slice::IterMut<'a, f64>,
    exit_short_price: std::slice::IterMut<'a, f64>,
    risk_in_bar_direction: std::slice::IterMut<'a, i8>,
    first_entry_side: std::slice::IterMut<'a, i8>,
    frame_events: std::slice::IterMut<'a, u32>,
    // 可选列迭代器
    sl_pct_long: Option<std::slice::IterMut<'a, f64>>,
    sl_pct_short: Option<std::slice::IterMut<'a, f64>>,
    tp_pct_long: Option<std::slice::IterMut<'a, f64>>,
    tp_pct_short: Option<std::slice::IterMut<'a, f64>>,
    tsl_pct_long: Option<std::slice::IterMut<'a, f64>>,
    tsl_pct_short: Option<std::slice::IterMut<'a, f64>>,
    sl_atr_long: Option<std::slice::IterMut<'a, f64>>,
    sl_atr_short: Option<std::slice::IterMut<'a, f64>>,
    tp_atr_long: Option<std::slice::IterMut<'a, f64>>,
    tp_atr_short: Option<std::slice::IterMut<'a, f64>>,
    tsl_atr_long: Option<std::slice::IterMut<'a, f64>>,
    tsl_atr_short: Option<std::slice::IterMut<'a, f64>>,
    tsl_psar_long: Option<std::slice::IterMut<'a, f64>>,
    tsl_psar_short: Option<std::slice::IterMut<'a, f64>>,
}

impl<'a> OutputBuffersIter<'a> {
    /// 从 OutputBuffers 创建迭代器，从指定起始索引开始
    pub fn new(buffers: &'a mut OutputBuffers, start: usize) -> Self {
        Self {
            balance: buffers.balance[start..].iter_mut(),
            equity: buffers.equity[start..].iter_mut(),
            trade_pnl_pct: buffers.trade_pnl_pct[start..].iter_mut(),
            total_return_pct: buffers.total_return_pct[start..].iter_mut(),
            fee: buffers.fee[start..].iter_mut(),
            fee_cum: buffers.fee_cum[start..].iter_mut(),
            current_drawdown: buffers.current_drawdown[start..].iter_mut(),
            entry_long_price: buffers.entry_long_price[start..].iter_mut(),
            entry_short_price: buffers.entry_short_price[start..].iter_mut(),
            exit_long_price: buffers.exit_long_price[start..].iter_mut(),
            exit_short_price: buffers.exit_short_price[start..].iter_mut(),
            risk_in_bar_direction: buffers.risk_in_bar_direction[start..].iter_mut(),
            first_entry_side: buffers.first_entry_side[start..].iter_mut(),
            frame_events: buffers.frame_events[start..].iter_mut(),
            sl_pct_long: buffers
                .sl_pct_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            sl_pct_short: buffers
                .sl_pct_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tp_pct_long: buffers
                .tp_pct_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tp_pct_short: buffers
                .tp_pct_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_pct_long: buffers
                .tsl_pct_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_pct_short: buffers
                .tsl_pct_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            sl_atr_long: buffers
                .sl_atr_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            sl_atr_short: buffers
                .sl_atr_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tp_atr_long: buffers
                .tp_atr_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tp_atr_short: buffers
                .tp_atr_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_atr_long: buffers
                .tsl_atr_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_atr_short: buffers
                .tsl_atr_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_psar_long: buffers
                .tsl_psar_price_long
                .as_mut()
                .map(|v| v[start..].iter_mut()),
            tsl_psar_short: buffers
                .tsl_psar_price_short
                .as_mut()
                .map(|v| v[start..].iter_mut()),
        }
    }
}

impl<'a> Iterator for OutputBuffersIter<'a> {
    type Item = OutputRow<'a>;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        Some(OutputRow {
            balance: self.balance.next()?,
            equity: self.equity.next()?,
            trade_pnl_pct: self.trade_pnl_pct.next()?,
            total_return_pct: self.total_return_pct.next()?,
            fee: self.fee.next()?,
            fee_cum: self.fee_cum.next()?,
            current_drawdown: self.current_drawdown.next()?,
            entry_long_price: self.entry_long_price.next()?,
            entry_short_price: self.entry_short_price.next()?,
            exit_long_price: self.exit_long_price.next()?,
            exit_short_price: self.exit_short_price.next()?,
            risk_in_bar_direction: self.risk_in_bar_direction.next()?,
            first_entry_side: self.first_entry_side.next()?,
            frame_events: self.frame_events.next()?,
            sl_pct_long: self.sl_pct_long.as_mut().and_then(|i| i.next()),
            sl_pct_short: self.sl_pct_short.as_mut().and_then(|i| i.next()),
            tp_pct_long: self.tp_pct_long.as_mut().and_then(|i| i.next()),
            tp_pct_short: self.tp_pct_short.as_mut().and_then(|i| i.next()),
            tsl_pct_long: self.tsl_pct_long.as_mut().and_then(|i| i.next()),
            tsl_pct_short: self.tsl_pct_short.as_mut().and_then(|i| i.next()),
            sl_atr_long: self.sl_atr_long.as_mut().and_then(|i| i.next()),
            sl_atr_short: self.sl_atr_short.as_mut().and_then(|i| i.next()),
            tp_atr_long: self.tp_atr_long.as_mut().and_then(|i| i.next()),
            tp_atr_short: self.tp_atr_short.as_mut().and_then(|i| i.next()),
            tsl_atr_long: self.tsl_atr_long.as_mut().and_then(|i| i.next()),
            tsl_atr_short: self.tsl_atr_short.as_mut().and_then(|i| i.next()),
            tsl_psar_long: self.tsl_psar_long.as_mut().and_then(|i| i.next()),
            tsl_psar_short: self.tsl_psar_short.as_mut().and_then(|i| i.next()),
        })
    }
}
