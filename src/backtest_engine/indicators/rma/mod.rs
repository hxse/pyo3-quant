mod config;
mod expr;
mod indicator;
mod pipeline;

pub use config::RMAConfig;
pub use expr::rma_expr;
pub use indicator::RmaIndicator;
pub use pipeline::{rma_eager, rma_lazy};
