mod config;
mod expr;
mod indicator;
mod pipeline;

pub use config::EMAConfig;
pub use expr::ema_expr;
pub use indicator::EmaIndicator;
pub use pipeline::{ema_eager, ema_lazy};
