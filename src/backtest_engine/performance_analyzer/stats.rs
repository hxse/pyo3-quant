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

    // 中文注释：仅保留有限且非零收益，明确排除 NaN/Infinity 对统计的污染。
    let mut closed_trades: Vec<f64> = Vec::new();
    for value in trade_pnl_pct.into_iter().flatten() {
        if value != 0.0 && value.is_finite() {
            closed_trades.push(value);
        }
    }

    let n_trades = closed_trades.len();
    if n_trades == 0 {
        return stats;
    }

    stats.total_trades = n_trades as f64;

    let mut wins_sum = 0.0;
    let mut losses_sum = 0.0;
    for value in closed_trades {
        if value > 0.0 {
            stats.wins_count += 1.0;
            wins_sum += value;
        } else if value < 0.0 {
            stats.losses_count += 1.0;
            losses_sum += value.abs();
        }
    }

    stats.win_rate = stats.wins_count / stats.total_trades;

    if stats.wins_count > 0.0 {
        stats.avg_win = wins_sum / stats.wins_count;
    }

    if stats.losses_count > 0.0 {
        stats.avg_loss = losses_sum / stats.losses_count;
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
    pub avg_holding_duration_ms: f64,
    pub max_holding_duration_ms: f64,
    pub avg_empty_duration_ms: f64,
    pub max_empty_duration_ms: f64,
    pub max_drawdown_duration: f64,
}

/// 计算时长统计信息
///
/// 注：持仓和空仓时长由于涉及状态切换，目前仍使用线性扫描。
/// 最大回撤时长可以通过矢量化计算。
pub fn calculate_duration_stats(
    n: usize,
    time: &ChunkedArray<Int64Type>,
    entry_long: &ChunkedArray<Float64Type>,
    entry_short: &ChunkedArray<Float64Type>,
    current_drawdown: &ChunkedArray<Float64Type>,
) -> DurationStats {
    let mut stats = DurationStats::default();

    let mut holding_durs = Vec::new();
    let mut empty_durs = Vec::new();
    let mut current_holding_dur = 0;
    let mut current_empty_dur = 0;
    let mut current_holding_ms = 0.0;
    let mut current_empty_ms = 0.0;
    let mut in_pos = false;
    let mut seen_first_trade = false;
    let mut holding_durs_ms: Vec<f64> = Vec::new();
    let mut empty_durs_ms: Vec<f64> = Vec::new();
    let deltas_ms = build_bar_deltas_ms(time, n);

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
                    // 中文注释：ms 统计与 bar 统计在同一时点 flush，保证分母一致。
                    empty_durs_ms.push(current_empty_ms);
                    current_empty_dur = 0;
                    current_empty_ms = 0.0;
                }
                in_pos = true;
            }
            current_holding_dur += 1;
            current_holding_ms += deltas_ms[i];
        } else {
            if in_pos {
                if current_holding_dur > 0 {
                    holding_durs.push(current_holding_dur);
                    // 中文注释：即使区间内毫秒总和为 0，也保持与 bar 区间数量对齐。
                    holding_durs_ms.push(current_holding_ms);
                    current_holding_dur = 0;
                    current_holding_ms = 0.0;
                }
                in_pos = false;
            }
            if seen_first_trade {
                current_empty_dur += 1;
                current_empty_ms += deltas_ms[i];
            }
        }
    }

    // 处理收尾
    if current_holding_dur > 0 {
        holding_durs.push(current_holding_dur);
        holding_durs_ms.push(current_holding_ms);
    }
    if current_empty_dur > 0 {
        empty_durs.push(current_empty_dur);
        empty_durs_ms.push(current_empty_ms);
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
    if !holding_durs_ms.is_empty() {
        stats.avg_holding_duration_ms =
            holding_durs_ms.iter().sum::<f64>() / holding_durs_ms.len() as f64;
        stats.max_holding_duration_ms =
            holding_durs_ms
                .iter()
                .fold(0.0, |acc, &x| if x > acc { x } else { acc });
    }
    if !empty_durs_ms.is_empty() {
        stats.avg_empty_duration_ms =
            empty_durs_ms.iter().sum::<f64>() / empty_durs_ms.len() as f64;
        stats.max_empty_duration_ms = empty_durs_ms
            .iter()
            .fold(0.0, |acc, &x| if x > acc { x } else { acc });
    }

    // 2. 最大回撤时长统计 (矢量化：使用 RLE 计算最长连续 dd > 0 的长度)
    stats.max_drawdown_duration = calculate_max_drawdown_duration_vect(current_drawdown);

    stats
}

fn build_bar_deltas_ms(time: &ChunkedArray<Int64Type>, n: usize) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    if n == 1 {
        return vec![0.0];
    }

    let mut deltas_ms: Vec<f64> = Vec::with_capacity(n);
    let mut positive_deltas: Vec<i64> = Vec::with_capacity(n - 1);
    for i in 0..(n - 1) {
        let start = time.get(i).unwrap_or(0);
        let end = time.get(i + 1).unwrap_or(start);
        let delta = (end - start).max(0);
        if delta > 0 {
            positive_deltas.push(delta);
        }
        deltas_ms.push(delta as f64);
    }

    // 中文注释：最后一根没有右侧时间点，使用正增量中位数作为近似间隔。
    let fallback = if positive_deltas.is_empty() {
        0.0
    } else {
        positive_deltas.sort_unstable();
        positive_deltas[positive_deltas.len() / 2] as f64
    };
    deltas_ms.push(fallback);
    deltas_ms
}

/// 矢量化计算最大回撤时长
fn calculate_max_drawdown_duration_vect(current_drawdown: &ChunkedArray<Float64Type>) -> f64 {
    // 标记是否处于回撤状态 (dd > 0)
    let is_dd = current_drawdown.gt(0.0);

    if !is_dd.any() {
        return 0.0;
    }

    // 使用 Polars 的逻辑计算连续 True 的最大重复次数
    // 这里采用线性扫描实现，直到确认 Polars RLE 插件或原生方法在当前版本的可用性
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
