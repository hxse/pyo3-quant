pub mod backtest;
pub mod indicator_contract;
pub mod optimizer;
pub mod sensitivity;
pub mod walk_forward;

pub use self::backtest::{IndicatorResults, PerformanceMetrics, ResultPack};
pub use self::indicator_contract::{IndicatorContract, IndicatorContractReport};
pub use self::optimizer::{OptimizationResult, RoundSummary, SamplePoint};
pub use self::sensitivity::{SensitivityResult, SensitivitySample};
pub use self::walk_forward::{
    NextWindowHint, StitchedArtifact, StitchedMeta, WalkForwardResult, WindowArtifact, WindowMeta,
};
