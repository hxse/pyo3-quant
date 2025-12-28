/// 持仓方向枚举
#[derive(PartialEq, Clone, Copy, Debug)]
pub enum Direction {
    Long,
    Short,
}

impl Direction {
    /// 获取方向符号：Long为1.0，Short为-1.0
    pub fn sign(&self) -> f64 {
        match self {
            Direction::Long => 1.0,
            Direction::Short => -1.0,
        }
    }
}

/// 计算 SL PCT 价格
pub fn calc_sl_pct_price(anchor: f64, sl_pct: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor * (1.0 - sign * sl_pct)
}

/// 计算 SL ATR 价格
pub fn calc_sl_atr_price(anchor: f64, atr: f64, sl_atr_k: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor - sign * atr * sl_atr_k
}

/// 计算 TP PCT 价格
pub fn calc_tp_pct_price(anchor: f64, tp_pct: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor * (1.0 + sign * tp_pct)
}

/// 计算 TP ATR 价格
pub fn calc_tp_atr_price(anchor: f64, atr: f64, tp_atr_k: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor + sign * atr * tp_atr_k
}

/// 计算 TSL PCT 价格
pub fn calc_tsl_pct_price(anchor: f64, tsl_pct: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor * (1.0 - sign * tsl_pct)
}

/// 计算 TSL ATR 价格
pub fn calc_tsl_atr_price(anchor: f64, atr: f64, tsl_atr_k: f64, direction: Direction) -> f64 {
    let sign = direction.sign();
    anchor - sign * atr * tsl_atr_k
}

/// 获取 SL 锚点价格
pub fn get_sl_anchor(
    close: f64,
    low: f64,
    high: f64,
    anchor_mode: bool,
    direction: Direction,
) -> f64 {
    if anchor_mode {
        match direction {
            Direction::Long => low,
            Direction::Short => high,
        }
    } else {
        close
    }
}

/// 获取 TP 锚点价格
pub fn get_tp_anchor(
    close: f64,
    low: f64,
    high: f64,
    anchor_mode: bool,
    direction: Direction,
) -> f64 {
    if anchor_mode {
        match direction {
            Direction::Long => high,
            Direction::Short => low,
        }
    } else {
        close
    }
}

/// 获取 TSL 锚点价格（用于初始化）
pub fn get_tsl_anchor(
    close: f64,
    low: f64,
    high: f64,
    anchor_mode: bool,
    direction: Direction,
) -> f64 {
    if anchor_mode {
        match direction {
            Direction::Long => high,
            Direction::Short => low,
        }
    } else {
        close
    }
}
/// 更新极值（多头取更高，空头取更低）
///
/// Returns: (新极值, 是否更新)
pub fn update_anchor_since_entry(
    current_anchor: f64,
    prev_anchor: f64,
    direction: Direction,
) -> (f64, bool) {
    match direction {
        Direction::Long => {
            if current_anchor > prev_anchor {
                (current_anchor, true)
            } else {
                (prev_anchor, false)
            }
        }
        Direction::Short => {
            if current_anchor < prev_anchor {
                (current_anchor, true)
            } else {
                (prev_anchor, false)
            }
        }
    }
}

/// 检查是否触发止损
pub fn is_sl_triggered(price: f64, threshold: Option<f64>, direction: Direction) -> bool {
    threshold.map_or(false, |t| price * direction.sign() <= t * direction.sign())
}

/// 检查是否触发止盈
pub fn is_tp_triggered(price: f64, threshold: Option<f64>, direction: Direction) -> bool {
    threshold.map_or(false, |t| price * direction.sign() >= t * direction.sign())
}

/// 检查是否触发跟踪止损
pub fn is_tsl_triggered(price: f64, threshold: Option<f64>, direction: Direction) -> bool {
    threshold.map_or(false, |t| price * direction.sign() <= t * direction.sign())
}

/// 单向更新价格（多头只升不降，空头只降不升）
pub fn update_price_one_direction(
    old_price: Option<f64>,
    new_price: f64,
    direction: Direction,
) -> Option<f64> {
    match (old_price, direction) {
        (None, _) => Some(new_price),
        (Some(old), Direction::Long) if new_price > old => Some(new_price),
        (Some(old), Direction::Short) if new_price < old => Some(new_price),
        (old, _) => old,
    }
}
