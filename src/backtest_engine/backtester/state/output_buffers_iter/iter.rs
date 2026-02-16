use crate::backtest_engine::backtester::output::OutputBuffers;

use super::row::OutputRow;

/// 输出缓冲区迭代器，每次返回一行的可变引用。
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
    frame_state: std::slice::IterMut<'a, u8>,
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
    /// 从 OutputBuffers 创建迭代器，从指定起始索引开始。
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
            frame_state: buffers.frame_state[start..].iter_mut(),
            sl_pct_long: buffers
                .sl_pct_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            sl_pct_short: buffers
                .sl_pct_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tp_pct_long: buffers
                .tp_pct_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tp_pct_short: buffers
                .tp_pct_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_pct_long: buffers
                .tsl_pct_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_pct_short: buffers
                .tsl_pct_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            sl_atr_long: buffers
                .sl_atr_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            sl_atr_short: buffers
                .sl_atr_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tp_atr_long: buffers
                .tp_atr_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tp_atr_short: buffers
                .tp_atr_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_atr_long: buffers
                .tsl_atr_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_atr_short: buffers
                .tsl_atr_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_psar_long: buffers
                .tsl_psar_price_long
                .as_mut()
                .map(|values| values[start..].iter_mut()),
            tsl_psar_short: buffers
                .tsl_psar_price_short
                .as_mut()
                .map(|values| values[start..].iter_mut()),
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
            frame_state: self.frame_state.next()?,
            sl_pct_long: self.sl_pct_long.as_mut().and_then(|iter| iter.next()),
            sl_pct_short: self.sl_pct_short.as_mut().and_then(|iter| iter.next()),
            tp_pct_long: self.tp_pct_long.as_mut().and_then(|iter| iter.next()),
            tp_pct_short: self.tp_pct_short.as_mut().and_then(|iter| iter.next()),
            tsl_pct_long: self.tsl_pct_long.as_mut().and_then(|iter| iter.next()),
            tsl_pct_short: self.tsl_pct_short.as_mut().and_then(|iter| iter.next()),
            sl_atr_long: self.sl_atr_long.as_mut().and_then(|iter| iter.next()),
            sl_atr_short: self.sl_atr_short.as_mut().and_then(|iter| iter.next()),
            tp_atr_long: self.tp_atr_long.as_mut().and_then(|iter| iter.next()),
            tp_atr_short: self.tp_atr_short.as_mut().and_then(|iter| iter.next()),
            tsl_atr_long: self.tsl_atr_long.as_mut().and_then(|iter| iter.next()),
            tsl_atr_short: self.tsl_atr_short.as_mut().and_then(|iter| iter.next()),
            tsl_psar_long: self.tsl_psar_long.as_mut().and_then(|iter| iter.next()),
            tsl_psar_short: self.tsl_psar_short.as_mut().and_then(|iter| iter.next()),
        })
    }
}
