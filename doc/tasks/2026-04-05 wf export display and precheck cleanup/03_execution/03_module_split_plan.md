# 模块拆分方案

## 1. pack producer 层

`src/backtest_engine/data_ops/` 继续承担 pack producer 真值层，但职责要更明确：

1. `build_data_pack(...)` 负责正式 `DataPack` 构造。
2. `build_result_pack(...)` 负责正式 `ResultPack` 构造。
3. `extract_active(...)` 负责正式 active pair-transform。
4. `slice_*`、`build_time_mapping(...)`、planner 等只作为更高层 helper，不再手造 pack。

这一层的目标不是新增更多 helper，而是把 pack 真值入口真正收成三个。

## 2. 执行层

执行层不应继续塞在 `top_level_api.rs` 一个文件里混写。
本轮实际拆分为 `src/backtest_engine/pipeline/` 目录：

1. `pipeline/types.rs`
   - `PipelineRequest`
   - `PipelineOutput`
2. `pipeline/settings.rs`
   - `compile_public_setting_to_request(...)`
   - `validate_mode_settings(...)`
3. `pipeline/public_result.rs`
   - `build_public_result_pack(...)`
4. `pipeline/validation.rs`
   - 高度与 raw-indicator contract 校验
5. `pipeline/executor.rs`
   - `execute_single_pipeline(...)`
   - `evaluate_param_set(...)`
6. `pipeline/tests.rs`
   - 轻量 contract test

若暂时保留 `top_level_api.rs`，它也只应承担：

1. `run_*`
2. `py_run_*`
3. 少量模式编排 glue code

`top_level_api.rs` 只保留 `run_*` 编排与少量 glue code，不承担内部执行器定义。

## 3. WF / optimizer / sensitivity

这三组模块的职责边界应当收成：

1. `walk_forward/*`
   - 只负责窗口编排、stitch、WF 结果拼装
   - 不再自己手动拆 `ResultPack` 再补跑 leaf 阶段
   - replay 只是步骤概念，不单独承诺 `replay_*` helper 层级
2. `optimizer/*`
   - 只负责样本搜索与结果收集
   - single pipeline 推进统一交给 `evaluate_param_set(...)`
3. `sensitivity/*`
   - 只负责样本扰动与结果汇总
   - 不再内联第二份 single 执行逻辑

## 4. context 与 memory helper

`utils/context.rs` 应删除。
这次不接受“换个更诚实的名字继续保留”。

`utils/memory_optimizer.rs` 若继续存在，应只表达 `artifact_retention` 派生出的释放策略，不再绑定旧字段 `return_only_final` 的命名与语义。

## 5. Python runner wrapper / display

Python runner 层这次不应继续围绕 `RunResult` 打补丁。
推荐拆成四层：

1. `Backtest`
   - 执行门面
   - 只负责调 Rust 入口并返回正式 view
2. `RunnerSession`
   - 保存 `data_pack / template_config / engine_settings / enable_timing`
   - 不再使用 `context: dict`
3. `views/*`
   - `SingleBacktestView`
   - `BatchBacktestView`
   - `WalkForwardView`
   - `OptimizationView`
   - `SensitivityView`
   - `OptunaOptimizationView`
4. `PreparedExportBundle`
   - 只表达 bundle / display / save / upload 会话

若继续保留 `py_entry/runner/results/` 目录，也必须至少做到：

1. 旧 wrapper 名退出正式命名
2. `WalkForwardView` 不再惰性拼 single 结果代理
3. `BatchBacktestView` 不再保存 `context: dict`
4. `display/*` 正式只消费 `PreparedExportBundle`
5. 旧 `results/*` 文件若保留，只能作为内部实现细节，不得继续通过 `py_entry/runner/__init__.py` 或其他公开入口 re-export

## 6. Python / stub / 文档面

Python 面与 stub 面只保留正式公开对象和正式 producer API：

1. `DataPack` / `ResultPack` 继续作为公开类型存在
2. 但它们不再是自由构造对象
3. pack producer 的公开入口收口到 `data_ops` 工具函数
4. 旧 precheck、旧字段、旧示例同步退出

## 7. 这次拆分的判断标准

如果某个文件同时承担下面两种以上职责，就应优先拆分：

1. 正式模式入口
2. PyO3 wrapper
3. 内部执行器
4. pack producer
5. WF 编排
6. 结果适配 / 导出解释

这次任务默认优先用拆分解决混乱，而不是继续在大文件里叠加桥接。
