/// 单个交易动作 (Pure Rust)
#[derive(Debug, Clone)]
pub struct SignalAction {
    pub action_type: String,
    pub symbol: String,
    pub side: Option<String>,
    pub price: Option<f64>,
}

impl SignalAction {
    pub fn new(action_type: &str, symbol: &str, side: Option<&str>, price: Option<f64>) -> Self {
        Self {
            action_type: action_type.to_string(),
            symbol: symbol.to_string(),
            side: side.map(|s| s.to_string()),
            price,
        }
    }
}

/// 信号状态 (Pure Rust)
#[derive(Debug, Clone)]
pub struct SignalState {
    pub actions: Vec<SignalAction>,
    pub has_exit: bool,
}

impl SignalState {
    pub fn new(actions: Vec<SignalAction>, has_exit: bool) -> Self {
        Self { actions, has_exit }
    }
}
