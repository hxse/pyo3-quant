use crate::error::QuantError;
use polars::prelude::*;

use super::planner::FetchRequest;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FetchStage {
    /// 尚未确认当前 source 的基础覆盖范围。
    Initial,
    /// 已知尾部 live 覆盖不足，需要向右扩张请求窗口。
    TailCoverage,
    /// 已知尾部已覆盖，但头部时间还没覆盖到 base pack 起点。
    HeadTimeCoverage,
    /// 已知时间覆盖成立，但还要继续补到该 source 自身所需 warmup。
    HeadWarmup,
    /// 当前 source 的最终窗口已经冻结，不再继续补拉。
    Complete,
}

#[derive(Debug, Clone)]
pub struct SourceFetchState {
    pub source_key: String,
    pub interval_ms: i64,
    pub required_warmup: usize,
    pub current_since: i64,
    pub current_limit: usize,
    pub max_rounds_per_source: usize,
    pub rounds: usize,
    pub stage: FetchStage,
    pub df: Option<DataFrame>,
}

impl SourceFetchState {
    /// 中文注释：统一构造单个 source 的取数状态。
    pub fn new(
        source_key: String,
        interval_ms: i64,
        required_warmup: usize,
        initial_since: i64,
        initial_limit: usize,
        max_rounds_per_source: usize,
        stage: FetchStage,
    ) -> Self {
        Self {
            source_key,
            interval_ms,
            required_warmup,
            current_since: initial_since,
            current_limit: initial_limit,
            max_rounds_per_source,
            rounds: 0,
            stage,
            df: None,
        }
    }

    /// 中文注释：返回当前 source 的下一轮请求快照。
    pub fn request(&self) -> FetchRequest {
        FetchRequest::new(
            self.source_key.clone(),
            self.current_since,
            self.current_limit,
        )
    }

    /// 中文注释：状态机每次扩张请求窗口都统一累加轮次并检查上限。
    /// 这里的 rounds 只在“需要继续补拉”时递增；首次请求本身不算补拉轮次。
    pub fn bump_round_and_check(&mut self) -> Result<(), QuantError> {
        self.rounds += 1;
        if self.rounds > self.max_rounds_per_source {
            return Err(QuantError::InvalidParam(format!(
                "source '{}' 的补拉轮次超过上限 {}",
                self.source_key, self.max_rounds_per_source
            )));
        }
        Ok(())
    }
}
