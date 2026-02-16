mod config;
mod expr;
mod indicator;
mod pipeline;

pub use config::MACDConfig;
pub use expr::macd_expr;
pub use indicator::MacdIndicator;
pub use pipeline::{macd_eager, macd_lazy};
