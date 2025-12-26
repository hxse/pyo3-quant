use super::current_bar_data::CurrentBarData;
use crate::backtest_engine::backtester::data_preparer::PreparedData;

/// PreparedData 的迭代器，每次返回一个 CurrentBarData
/// 使用迭代器而非索引访问，消除边界检查
pub struct PreparedDataIter<'a> {
    open: std::slice::Iter<'a, f64>,
    high: std::slice::Iter<'a, f64>,
    low: std::slice::Iter<'a, f64>,
    close: std::slice::Iter<'a, f64>,
    entry_long: std::slice::Iter<'a, i32>,
    exit_long: std::slice::Iter<'a, i32>,
    entry_short: std::slice::Iter<'a, i32>,
    exit_short: std::slice::Iter<'a, i32>,
    atr: Option<std::slice::Iter<'a, f64>>,
    index: usize,
}

impl<'a> PreparedDataIter<'a> {
    /// 从 PreparedData 创建迭代器，从指定起始索引开始
    pub fn new(data: &'a PreparedData, start: usize) -> Self {
        Self {
            open: data.open[start..].iter(),
            high: data.high[start..].iter(),
            low: data.low[start..].iter(),
            close: data.close[start..].iter(),
            entry_long: data.entry_long[start..].iter(),
            exit_long: data.exit_long[start..].iter(),
            entry_short: data.entry_short[start..].iter(),
            exit_short: data.exit_short[start..].iter(),
            atr: data.atr.as_ref().map(|v| v[start..].iter()),
            index: start,
        }
    }
}

impl<'a> Iterator for PreparedDataIter<'a> {
    type Item = (usize, CurrentBarData);

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        let open = *self.open.next()?;
        let high = *self.high.next()?;
        let low = *self.low.next()?;
        let close = *self.close.next()?;
        let entry_long = *self.entry_long.next()?;
        let exit_long = *self.exit_long.next()?;
        let entry_short = *self.entry_short.next()?;
        let exit_short = *self.exit_short.next()?;
        let atr = self.atr.as_mut().and_then(|iter| iter.next().copied());

        let idx = self.index;
        self.index += 1;

        Some((
            idx,
            CurrentBarData::from_values(
                open,
                high,
                low,
                close,
                entry_long,
                exit_long,
                entry_short,
                exit_short,
                atr,
            ),
        ))
    }
}
