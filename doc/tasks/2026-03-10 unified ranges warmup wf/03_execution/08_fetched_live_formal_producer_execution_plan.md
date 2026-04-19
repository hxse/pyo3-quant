# Fetched / Live Formal Producer 执行计划

## 1. Patch 级别

本 patch 归属于 `03-10`，按 `A 类任务` 执行。

原因：

1. 涉及 fetched / live producer、Rust planner、Python runner、WF 入口与测试主链。
2. 若实现偏离，可能生成 quietly wrong 的 `DataPack.ranges`。
3. 需要清理 legacy coverage-only producer 语义。

## 2. 阶段计划

### 阶段 0：文档 patch

目标：

1. 将临时 `todo.md` 内容迁入正式 task 文档。
2. 在 `00_meta`、`01_context` 与 `02_spec` 中按当前正式状态表达范围、取舍与 contract。
3. 在 `03_execution` 中保留本次 patch 的阶段计划、legacy kill list 与验证计划。
4. 删除临时 `todo.md`。

验收：

1. `00_meta` 指向当前正式文档入口。
2. `01_context`、`02_spec` 使用最终态口径，不记录补丁演化过程。
3. `03_execution` 保留 patch 执行计划。
4. `todo.md` 不再作为任务真值入口存在。

### 阶段 1：参数先冻结

目标：

1. fetched / live formal producer 在构建 `DataPackFetchPlannerInput` 前拿到当前 `SingleParamSet`。
2. `params_override` 不得静默复用按另一组参数规划的 fetched `DataPack`。
3. `run / walk_forward / optimize / sensitivity / batch` 的 data planning 参数口径明确。

预期影响：

1. [py_entry/runner/backtest.py](/home/hxse/pyo3-quant/py_entry/runner/backtest.py)
2. [py_entry/runner/setup_utils.py](/home/hxse/pyo3-quant/py_entry/runner/setup_utils.py)

### 阶段 2：fetched / live 接回 planner

目标：

1. `OhlcvDataFetchConfig` formal path 构造 `DataPackFetchPlannerInput`。
2. Python loop 只消费 `planner.next_request()` 并调用 `planner.ingest_response(...)`。
3. `planner.finish()` 返回 formal full `DataPack`。
4. `since=None`、`limit=None`、`align_to_base_range=True` 在 formal path 明确 fail-fast 或有专门迁移策略。

预期影响：

1. [py_entry/data_generator/data_generator.py](/home/hxse/pyo3-quant/py_entry/data_generator/data_generator.py)
2. `src/backtest_engine/data_ops/fetch_planner/*`

### 阶段 3：WF 入口 guard

目标：

1. `run_walk_forward(...)` 增加 `validate_indicator_source_subset(...)`。
2. `run_walk_forward(...)` 增加 `validate_wf_input_datapack_readiness(...)`。
3. readiness guard 使用第 0 窗 active anchors，不使用 `data.ranges[base].warmup_bars` 作为唯一锚点。
4. 错误信息指向 `WF 输入 full DataPack 不满足 required_warmup_by_key`。

预期影响：

1. [src/backtest_engine/walk_forward/runner.rs](/home/hxse/pyo3-quant/src/backtest_engine/walk_forward/runner.rs)
2. `src/backtest_engine/walk_forward/*`

### 阶段 4：Legacy Kill List

清理目标：

1. `_fetch_with_coverage_backfill(...)` 不再承担 formal fetched full pack producer 语义。
2. fetched branch 不再以 `build_time_mapping(...)` 作为正式出口。
3. `end_backfill_min_step_bars` 的归属必须明确：删除、迁移到 planner input，或保留为非 formal 工具字段。
4. fetched path 不再生成 synthetic all-false `skip_mask` 作为必要输出。
5. 旧 coverage backfill 测试迁移为 planner integration / Python wiring 测试。

不清理：

1. HA / derived source 旧口径。
2. 外部指标注入。
3. `DataPack.source` 的 `ohlcv_*` 全局强约束。

### 阶段 5：测试与验证

新增或迁移测试：

1. fetched Python wiring integration：
   - Python 按 `planner.next_request()` 请求。
   - request mismatch 不能被 Python 吞掉。
   - `planner.finish()` 的 ranges 不再全是 `0 / height / height`。
2. MTF warmup regression：
   - `30m + 4h + 1d`。
   - 非 base source 在第 0 窗 active anchor 上满足 `mapped_src_idx >= required_warmup`。
3. `WF` readiness guard：
   - 旧 coverage-only full pack 在入口 fail-fast。
   - direct / simulated 且第 0 窗 active anchor 足够时不被误杀。
   - indicator source 不存在时在 `run_walk_forward(...)` 入口 fail-fast。
4. 参数 override：
   - override 扩大 warmup 时不能静默复用旧 fetched pack。
   - optimize=true 的 warmup 字段按 `Param.max` 规划。
5. 配置失败语义：
   - `since=None` / `limit=None` 在 formal fetched path 直接报错。
   - `align_to_base_range=True` 在 formal fetched path 直接报错或被明确迁移。

正式验证顺序：

1. `just check`
2. `just test`

## 3. 交付标准

1. fetched / live formal path 产出的 full `DataPack` 来自 `planner.finish()`。
2. `DataPack.ranges` 能表达 per-source warmup。
3. `WF` 入口能提前拒绝不满足第 0 窗基础 warmup 的 full pack。
4. legacy coverage-only producer 不再被文档或测试描述为 formal fetched path。
5. `just check` 与 `just test` 通过。
