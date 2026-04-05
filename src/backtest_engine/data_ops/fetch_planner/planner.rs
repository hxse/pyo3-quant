use std::collections::{BTreeSet, HashMap};

use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;

use crate::backtest_engine::data_ops::time_projection::extract_time_values;
use crate::backtest_engine::data_ops::{
    build_data_pack, build_warmup_requirements, exact_index_by_time, map_source_row_by_time,
    resolve_source_interval_ms,
};
use crate::error::QuantError;
use crate::types::{BacktestParams, DataPack, DataSource, IndicatorsParams};

use super::initial_ranges::build_initial_ranges;
use super::source_state::{FetchStage, SourceFetchState};

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct DataPackFetchPlannerInput {
    pub timeframes: Vec<String>,
    pub base_data_key: String,
    pub effective_since: i64,
    pub effective_limit: usize,
    pub indicators_params: IndicatorsParams,
    pub backtest_params: BacktestParams,
    pub min_request_bars: usize,
    pub max_rounds_per_source: usize,
}

#[gen_stub_pymethods]
#[pymethods]
impl DataPackFetchPlannerInput {
    #[new]
    #[pyo3(signature = (*, timeframes, base_data_key, effective_since, effective_limit, indicators_params=None, backtest_params=None, min_request_bars=10, max_rounds_per_source=20))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        timeframes: Vec<String>,
        base_data_key: String,
        effective_since: i64,
        effective_limit: usize,
        indicators_params: Option<IndicatorsParams>,
        backtest_params: Option<BacktestParams>,
        min_request_bars: usize,
        max_rounds_per_source: usize,
    ) -> PyResult<Self> {
        if effective_limit < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "effective_limit 必须 >= 1",
            ));
        }
        if min_request_bars < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "min_request_bars 必须 >= 1",
            ));
        }
        if max_rounds_per_source < 1 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "max_rounds_per_source 必须 >= 1",
            ));
        }
        Ok(Self {
            timeframes,
            base_data_key,
            effective_since,
            effective_limit,
            indicators_params: indicators_params.unwrap_or_default(),
            backtest_params: backtest_params.unwrap_or_default(),
            min_request_bars,
            max_rounds_per_source,
        })
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct FetchRequest {
    pub source_key: String,
    pub since: i64,
    pub limit: usize,
}

#[gen_stub_pymethods]
#[pymethods]
impl FetchRequest {
    #[new]
    pub fn new(source_key: String, since: i64, limit: usize) -> Self {
        Self {
            source_key,
            since,
            limit,
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct BaseResolvedWindow {
    /// base 最终 pack 左边界时间，已经包含 base 自身 warmup。
    full_start_time: i64,
    /// base 最终 pack 右边界时间，按 source 区间右开语义需要再加一个 interval 才表示“完全覆盖到此刻之后”。
    full_end_time: i64,
    /// base 首根 live bar 的时间。后续所有非 base source 都围绕这个时刻补齐各自 warmup。
    first_live_time: i64,
}

/// 中文注释：阶段 B 先落独立 planner，不直接切现有 Python 主流程。
#[gen_stub_pyclass]
#[pyclass]
#[derive(Debug, Clone)]
pub struct DataPackFetchPlanner {
    input: DataPackFetchPlannerInput,
    source_keys: Vec<String>,
    intervals_ms: HashMap<String, i64>,
    required_warmup_by_key: HashMap<String, usize>,
    base_state: SourceFetchState,
    source_states: Vec<SourceFetchState>,
    next_source_idx: usize,
    base_window: Option<BaseResolvedWindow>,
    base_effective_start_time: Option<i64>,
}

impl DataPackFetchPlanner {
    fn build_source_keys(timeframes: &[String], base_data_key: &str) -> Vec<String> {
        // 中文注释：这里先用 BTreeSet 同时完成“去重 + 稳定排序”，再转回 Vec<String>；
        // 即使 timeframes 里包含 base 对应周期，最终也只保留一份 base source key。
        let mut ordered = BTreeSet::new();
        ordered.insert(base_data_key.to_string());
        for timeframe in timeframes {
            ordered.insert(format!("ohlcv_{timeframe}"));
        }
        ordered.into_iter().collect()
    }

    fn validate_indicator_sources(
        source_keys: &[String],
        indicators_params: &IndicatorsParams,
    ) -> Result<(), QuantError> {
        let allowed: BTreeSet<&str> = source_keys.iter().map(String::as_str).collect();
        for source_key in indicators_params.keys() {
            if !allowed.contains(source_key.as_str()) {
                return Err(QuantError::InvalidParam(format!(
                    "indicators_params.source_key='{}' 不属于 planner source_keys",
                    source_key
                )));
            }
        }
        Ok(())
    }

    fn validate_response_df(request: &FetchRequest, df: &DataFrame) -> Result<(), QuantError> {
        if df.height() == 0 {
            return Err(QuantError::InvalidParam(format!(
                "source '{}' 的响应 DataFrame 不允许为空",
                request.source_key
            )));
        }
        // 中文注释：planner 不关心列全集，但要求每轮响应至少能抽出合法 time 轴。
        let _ = extract_time_values(df, &request.source_key)?;
        Ok(())
    }

    fn current_request(&self) -> Option<FetchRequest> {
        if self.base_state.stage != FetchStage::Complete {
            return Some(self.base_state.request());
        }
        if self.next_source_idx < self.source_states.len() {
            return Some(self.source_states[self.next_source_idx].request());
        }
        None
    }

    fn active_state_mut(&mut self, source_key: &str) -> Result<&mut SourceFetchState, QuantError> {
        if self.base_state.source_key == source_key {
            return Ok(&mut self.base_state);
        }
        self.source_states
            .iter_mut()
            .find(|state| state.source_key == source_key)
            .ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "planner 当前不存在 source_key='{}' 的状态",
                    source_key
                ))
            })
    }

    fn complete_base_state(&mut self) -> Result<(), QuantError> {
        // 中文注释：base 是整套 planner 的真值锚点。
        // 只有先把 base 的最终 pack 窗口冻结下来，其他 source 才能知道自己至少要覆盖到哪。
        let required = self.base_state.required_warmup;
        let df = self
            .base_state
            .df
            .as_ref()
            .ok_or_else(|| QuantError::InvalidParam("base 状态缺少已接收响应".to_string()))?;
        let times = extract_time_values(df, &self.base_state.source_key)?;
        let effective_start_time = match self.base_effective_start_time {
            Some(time) => time,
            None => {
                let first_live_time = *times
                    .first()
                    .ok_or_else(|| QuantError::InvalidParam("base 响应为空".to_string()))?;
                self.base_effective_start_time = Some(first_live_time);
                first_live_time
            }
        };
        let mapped_idx =
            exact_index_by_time(&times, effective_start_time, &self.base_state.source_key)?;
        let missing_by_warmup = required.saturating_sub(mapped_idx);
        if missing_by_warmup > 0 {
            // 中文注释：当前响应已经含有 live 起点，但起点左侧 warmup 还不够，就继续向头部补拉。
            let prepend_bars = missing_by_warmup.max(self.input.min_request_bars);
            self.base_state.bump_round_and_check()?;
            self.base_state.current_since -= prepend_bars as i64 * self.base_state.interval_ms;
            self.base_state.current_limit += prepend_bars;
            self.base_state.stage = FetchStage::HeadWarmup;
            return Ok(());
        }

        let live_start_idx =
            exact_index_by_time(&times, effective_start_time, &self.base_state.source_key)?;
        let slice_start = live_start_idx.checked_sub(required).ok_or_else(|| {
            QuantError::InvalidParam(
                "base 左裁减时 live_start_idx 小于 required_warmup".to_string(),
            )
        })?;
        // 中文注释：base 一旦 warmup 足够，就直接把最终 pack 左边界裁到“live 起点往左 required 根”。
        // 后续所有 source 都要覆盖这个裁完后的 base_window。
        let full_df = df.slice(slice_start as i64, df.height() - slice_start);
        let full_times = extract_time_values(&full_df, &self.base_state.source_key)?;
        let first_live_time = full_times[required];
        let full_start_time = full_times[0];
        let full_end_time = *full_times.last().expect("full_times 非空");

        self.base_state.df = Some(full_df);
        self.base_state.stage = FetchStage::Complete;
        self.base_window = Some(BaseResolvedWindow {
            full_start_time,
            full_end_time,
            first_live_time,
        });
        self.initialize_source_states()?;
        Ok(())
    }

    fn initialize_source_states(&mut self) -> Result<(), QuantError> {
        let Some(base_window) = self.base_window else {
            return Ok(());
        };
        if !self.source_states.is_empty() {
            return Ok(());
        }

        // 中文注释：非 base source 统一从“至少覆盖完整 base pack 时间段”的初始请求开始。
        // 之后再按各自 stage 逐步补头部时间覆盖与 warmup。
        for source_key in &self.source_keys {
            if source_key == &self.input.base_data_key {
                continue;
            }
            let interval_ms = *self.intervals_ms.get(source_key).ok_or_else(|| {
                QuantError::InvalidParam(format!("intervals_ms 缺少 source_key='{}'", source_key))
            })?;
            let span_ms = base_window.full_end_time - base_window.full_start_time;
            let limit = ((span_ms + interval_ms - 1).div_euclid(interval_ms) + 1) as usize;
            let required_warmup = self
                .required_warmup_by_key
                .get(source_key)
                .copied()
                .unwrap_or(0);
            self.source_states.push(SourceFetchState::new(
                source_key.clone(),
                interval_ms,
                required_warmup,
                base_window.full_start_time,
                limit.max(1),
                self.input.max_rounds_per_source,
                FetchStage::Initial,
            ));
        }
        Ok(())
    }

    fn advance_source_state(&mut self, source_key: &str) -> Result<(), QuantError> {
        // 中文注释：非 base source 的推进顺序固定为：
        // 1. 先保证尾部覆盖 base pack 右边界
        // 2. 再保证头部时间覆盖到 base pack 左边界
        // 3. 最后补齐该 source 自身所需 warmup
        let base_window = self
            .base_window
            .ok_or_else(|| QuantError::InvalidParam("source 推进前缺少 base_window".to_string()))?;
        let min_request_bars = self.input.min_request_bars;
        let state = self.active_state_mut(source_key)?;
        let df = state.df.as_ref().ok_or_else(|| {
            QuantError::InvalidParam(format!("source '{}' 缺少已接收响应", source_key))
        })?;
        let times = extract_time_values(df, source_key)?;

        if state.stage == FetchStage::Initial || state.stage == FetchStage::TailCoverage {
            let last_time = *times.last().expect("times 非空");
            let covered_end_time = last_time.checked_add(state.interval_ms).ok_or_else(|| {
                QuantError::InvalidParam(format!("source '{}' 的尾覆盖计算溢出", source_key))
            })?;
            if covered_end_time <= base_window.full_end_time {
                let missing_ms = base_window.full_end_time - covered_end_time;
                let missing_bars = missing_ms.div_euclid(state.interval_ms) as usize + 1;
                let append_bars = missing_bars.max(min_request_bars);
                state.bump_round_and_check()?;
                state.current_limit += append_bars;
                state.stage = FetchStage::TailCoverage;
                return Ok(());
            }
            state.stage = FetchStage::HeadTimeCoverage;
        }

        if state.stage == FetchStage::HeadTimeCoverage {
            // 中文注释：这里看的不是 warmup，而是“当前 source 的最早时间是否已经早于 base pack 左边界”。
            let first_time = times[0];
            if first_time > base_window.full_start_time {
                let missing_ms = first_time - base_window.full_start_time;
                let missing_bars =
                    ((missing_ms + state.interval_ms - 1) / state.interval_ms) as usize;
                let prepend_bars = missing_bars.max(min_request_bars);
                state.bump_round_and_check()?;
                state.current_since -= prepend_bars as i64 * state.interval_ms;
                state.current_limit += prepend_bars;
                return Ok(());
            }
            state.stage = FetchStage::HeadWarmup;
        }

        if state.stage == FetchStage::HeadWarmup {
            // 中文注释：当前 source 的 warmup 基线，不是对齐 base.first bar，
            // 而是对齐 base.first_live_time 再向左数 required_warmup 根。
            let mapped_src_idx =
                map_source_row_by_time(base_window.first_live_time, &times, source_key)?;
            let missing_by_warmup = state.required_warmup.saturating_sub(mapped_src_idx);
            if missing_by_warmup > 0 {
                let prepend_bars = missing_by_warmup.max(min_request_bars);
                state.bump_round_and_check()?;
                state.current_since -= prepend_bars as i64 * state.interval_ms;
                state.current_limit += prepend_bars;
                return Ok(());
            }
            let first_time = times[0];
            let last_time = *times.last().expect("times 非空");
            let covered_end_time = last_time.checked_add(state.interval_ms).ok_or_else(|| {
                QuantError::InvalidParam(format!("source '{}' 的尾覆盖计算溢出", source_key))
            })?;
            if first_time > base_window.full_start_time {
                return Err(QuantError::InvalidParam(format!(
                    "source '{}' 首覆盖失败：src_first={} > base_first={}",
                    source_key, first_time, base_window.full_start_time
                )));
            }
            if covered_end_time <= base_window.full_end_time {
                return Err(QuantError::InvalidParam(format!(
                    "source '{}' 尾覆盖失败：src_last + interval = {} <= base_last={}",
                    source_key, covered_end_time, base_window.full_end_time
                )));
            }
            state.stage = FetchStage::Complete;
            self.next_source_idx += 1;
        }

        Ok(())
    }

    fn clone_source_map(&self) -> Result<DataSource, QuantError> {
        // 中文注释：finish() 只接受已经 complete 的状态；这里复制的是最终冻结窗口，而不是每轮原始响应。
        let mut source = HashMap::new();
        let base_df =
            self.base_state.df.clone().ok_or_else(|| {
                QuantError::InvalidParam("finish() 时 base 数据尚未完成".to_string())
            })?;
        source.insert(self.base_state.source_key.clone(), base_df);
        for state in &self.source_states {
            let df = state.df.clone().ok_or_else(|| {
                QuantError::InvalidParam(format!(
                    "finish() 时 source '{}' 尚未完成",
                    state.source_key
                ))
            })?;
            source.insert(state.source_key.clone(), df);
        }
        Ok(source)
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl DataPackFetchPlanner {
    #[new]
    pub fn new(input: DataPackFetchPlannerInput) -> PyResult<Self> {
        // 中文注释：new() 只做纯规划初始化，不执行任何远端请求，也不提前构造 DataPack。
        let source_keys = Self::build_source_keys(&input.timeframes, &input.base_data_key);
        Self::validate_indicator_sources(&source_keys, &input.indicators_params)
            .map_err::<PyErr, _>(Into::into)?;

        let mut intervals_ms = HashMap::new();
        for source_key in &source_keys {
            intervals_ms.insert(
                source_key.clone(),
                resolve_source_interval_ms(source_key).map_err::<PyErr, _>(Into::into)?,
            );
        }
        let warmup = build_warmup_requirements(
            &source_keys,
            &input.base_data_key,
            &input.indicators_params,
            false,
            &input.backtest_params,
        )
        .map_err::<PyErr, _>(Into::into)?;
        let base_interval_ms = *intervals_ms.get(&input.base_data_key).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("base_data_key 缺少 interval_ms")
        })?;
        let base_required = warmup
            .required_warmup_by_key
            .get(&input.base_data_key)
            .copied()
            .unwrap_or(0);

        Ok(Self {
            input: input.clone(),
            source_keys,
            intervals_ms,
            required_warmup_by_key: warmup.required_warmup_by_key,
            base_state: SourceFetchState::new(
                input.base_data_key.clone(),
                base_interval_ms,
                base_required,
                input.effective_since,
                input.effective_limit,
                input.max_rounds_per_source,
                FetchStage::Initial,
            ),
            source_states: Vec::new(),
            next_source_idx: 0,
            base_window: None,
            base_effective_start_time: None,
        })
    }

    #[getter]
    pub fn source_keys(&self) -> Vec<String> {
        self.source_keys.clone()
    }

    #[getter]
    pub fn required_warmup_by_key(&self) -> HashMap<String, usize> {
        self.required_warmup_by_key.clone()
    }

    pub fn next_request(&self) -> Option<FetchRequest> {
        self.current_request()
    }

    pub fn ingest_response(&mut self, request: FetchRequest, df: Bound<'_, PyAny>) -> PyResult<()> {
        let expected = self.current_request().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("planner 已完成，不应再 ingest_response(...)")
        })?;
        if expected.source_key != request.source_key
            || expected.since != request.since
            || expected.limit != request.limit
        {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "ingest_response(...) 的 request 与当前挂起请求不匹配，expected=({}, {}, {}) actual=({}, {}, {})",
                expected.source_key,
                expected.since,
                expected.limit,
                request.source_key,
                request.since,
                request.limit
            )));
        }

        let py_df: PyDataFrame = df.extract()?;
        let inner_df: DataFrame = py_df.into();
        Self::validate_response_df(&request, &inner_df).map_err::<PyErr, _>(Into::into)?;

        // 中文注释：ingest_response(...) 必须严格消费“当前挂起请求”的响应，不允许乱序喂数据。
        let source_key = request.source_key.clone();
        let is_base_request = source_key == self.input.base_data_key;
        let effective_limit = self.input.effective_limit;
        let state = self
            .active_state_mut(&source_key)
            .map_err::<PyErr, _>(Into::into)?;
        state.current_since = request.since;
        state.current_limit = request.limit;
        state.df = Some(inner_df);

        if is_base_request {
            let base_df = state.df.as_ref().expect("base 响应已写入");
            if base_df.height() < effective_limit {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "base 首次有效段长度不足：height()={} < effective_limit={}",
                    base_df.height(),
                    effective_limit
                )));
            }
            self.complete_base_state().map_err::<PyErr, _>(Into::into)
        } else {
            self.advance_source_state(&source_key)
                .map_err::<PyErr, _>(Into::into)
        }
    }

    pub fn is_complete(&self) -> bool {
        self.base_state.stage == FetchStage::Complete
            && self
                .source_states
                .iter()
                .all(|state| state.stage == FetchStage::Complete)
    }

    pub fn finish(&self) -> PyResult<DataPack> {
        if !self.is_complete() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "finish() 只能在 planner 完成后调用",
            ));
        }
        // 中文注释：finish() 不再重新推导抓取窗口，只把已经冻结的 source 数据转成 DataPack。
        let source = self.clone_source_map().map_err::<PyErr, _>(Into::into)?;
        let ranges = build_initial_ranges(
            &source,
            &self.input.base_data_key,
            &self.required_warmup_by_key,
        )
        .map_err::<PyErr, _>(Into::into)?;
        build_data_pack(source, self.input.base_data_key.clone(), ranges, None)
            .map_err::<PyErr, _>(Into::into)
    }
}
