use polars::prelude::*;

/// 交易统计结果
#[derive(Debug, Default)]
pub struct TradeStats {
    pub total_trades: f64,
    pub wins_count: f64,
    pub losses_count: f64,
    pub avg_win: f64,
    pub avg_loss: f64,
    pub win_rate: f64,
    pub profit_loss_ratio: f64,
}

/// 计算交易统计信息（矢量化）
pub fn calculate_trade_stats(trade_pnl_pct: &ChunkedArray<Float64Type>) -> TradeStats {
    let mut stats = TradeStats::default();

    // 转换为 Series 以利用 Polars 矢量化操作
    let trades_series = trade_pnl_pct.clone().into_series();

    // 过滤非零收益（代表已关闭的交易）
    let closed_trades = trades_series
        .filter(&trades_series.not_equal(0.0).unwrap())
        .unwrap();

    let n_trades = closed_trades.len();
    if n_trades == 0 {
        return stats;
    }

    stats.total_trades = n_trades as f64;

    // 盈利和亏损交易
    let wins = closed_trades
        .filter(&closed_trades.gt(0.0).unwrap())
        .unwrap();
    let losses = closed_trades
        .filter(&closed_trades.lt(0.0).unwrap())
        .unwrap();

    stats.wins_count = wins.len() as f64;
    stats.losses_count = losses.len() as f64;

    stats.win_rate = stats.wins_count / stats.total_trades;

    if stats.wins_count > 0.0 {
        stats.avg_win = wins.f64().unwrap().mean().unwrap_or(0.0);
    }

    if stats.losses_count > 0.0 {
        stats.avg_loss = losses.f64().unwrap().mean().unwrap_or(0.0).abs();
    }

    if stats.avg_loss > 0.0 {
        stats.profit_loss_ratio = stats.avg_win / stats.avg_loss;
    }

    stats
}

/// 时长统计结果
#[derive(Debug, Default)]
pub struct DurationStats {
    pub avg_holding_duration: f64,
    pub max_holding_duration: f64,
    pub avg_empty_duration: f64,
    pub max_empty_duration: f64,
    pub max_drawdown_duration: f64,
}

/// 计算时长统计信息
///
/// 注：持仓和空仓时长由于涉及状态切换，目前仍使用线性扫描。
/// 最大回撤时长可以通过矢量化计算。
pub fn calculate_duration_stats(
    n: usize,
    entry_long: &ChunkedArray<Float64Type>,
    entry_short: &ChunkedArray<Float64Type>,
    current_drawdown: &ChunkedArray<Float64Type>,
) -> DurationStats {
    let mut stats = DurationStats::default();

    let mut holding_durs = Vec::new();
    let mut empty_durs = Vec::new();
    let mut current_holding_dur = 0;
    let mut current_empty_dur = 0;
    let mut in_pos = false;
    let mut seen_first_trade = false;

    // 1. 持仓和空仓时长统计 (线性扫描)
    for i in 0..n {
        let long_active = entry_long.get(i).map(|v| !v.is_nan()).unwrap_or(false);
        let short_active = entry_short.get(i).map(|v| !v.is_nan()).unwrap_or(false);
        let is_active = long_active || short_active;

        if is_active {
            seen_first_trade = true;
            if !in_pos {
                if current_empty_dur > 0 {
                    empty_durs.push(current_empty_dur);
                    current_empty_dur = 0;
                }
                in_pos = true;
            }
            current_holding_dur += 1;
        } else {
            if in_pos {
                if current_holding_dur > 0 {
                    holding_durs.push(current_holding_dur);
                    current_holding_dur = 0;
                }
                in_pos = false;
            }
            if seen_first_trade {
                current_empty_dur += 1;
            }
        }
    }

    // 处理收尾
    if current_holding_dur > 0 {
        holding_durs.push(current_holding_dur);
    }
    if current_empty_dur > 0 {
        empty_durs.push(current_empty_dur);
    }

    if !holding_durs.is_empty() {
        stats.avg_holding_duration =
            holding_durs.iter().sum::<i32>() as f64 / holding_durs.len() as f64;
        stats.max_holding_duration = holding_durs.iter().max().cloned().unwrap_or(0) as f64;
    }

    if !empty_durs.is_empty() {
        stats.avg_empty_duration = empty_durs.iter().sum::<i32>() as f64 / empty_durs.len() as f64;
        stats.max_empty_duration = empty_durs.iter().max().cloned().unwrap_or(0) as f64;
    }

    // 2. 最大回撤时长统计 (矢量化：使用 RLE 计算最长连续 dd > 0 的长度)
    stats.max_drawdown_duration = calculate_max_drawdown_duration_vect(current_drawdown);

    stats
}

/// 矢量化计算最大回撤时长
fn calculate_max_drawdown_duration_vect(current_drawdown: &ChunkedArray<Float64Type>) -> f64 {
    let dd_series = current_drawdown.clone().into_series();

    // 标记是否处于回撤状态 (dd > 0)
    let is_dd = dd_series.gt(0.0).unwrap();

    if !is_dd.any() {
        return 0.0;
    }

    // 使用 Polars 的逻辑计算连续 True 的最大重复次数
    // 这里采用线性扫描作为回退，直到确认 Polars RLE 插件或原生方法在当前版本的可用性
    // 原 mod.rs 中的逻辑已经很高效且正确处理了边界，暂时保持逻辑一致
    let mut max_dur = 0;
    let mut current_dur = 0;

    for val in is_dd.into_iter().flatten() {
        if val {
            current_dur += 1;
        } else {
            if current_dur > max_dur {
                max_dur = current_dur;
            }
            current_dur = 0;
        }
    }
    if current_dur > max_dur {
        max_dur = current_dur;
    }

    max_dur as f64
}
