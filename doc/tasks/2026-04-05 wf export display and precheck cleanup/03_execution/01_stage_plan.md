# 执行阶段计划

## 1. 执行顺序

这次任务按下面顺序执行：

1. 先收 pack producer 真值入口。
2. 再收执行层内部主链。
3. 再收 Python runner wrapper、WF / optimizer / sensitivity、export / display、source time 等外围调用面。
4. 最后统一做旧痕迹清扫、stub 更新和回归验证。

这个顺序不能反过来。
原因是执行层与 WF 主链都依赖 pack producer 的单一真值边界；如果 pack 这一层还允许旁路构造，后面的执行层重构会一直被旧边界污染。

本任务执行期验证分成两类，不得混淆：

1. 等价回归：
   核心执行主链、公开 `stop_stage × artifact_retention` 语义、WF / optimizer / sensitivity 的既有模式语义必须保持等价。
2. 有意 breaking 验收：
   Python precheck 删除、pack producer 收口、source time 严格递增 contract、Renko 正式入口退出，必须按收紧后的新 contract 验收，不按旧行为回归。

## 2. Stage 1: Pack Producer 收口

### 2.1 目标

把 `DataPack` / `ResultPack` 收口为 formal contract object，冻结“禁止绕过工具函数构建 pack”的正式实现边界。

### 2.2 本阶段必须完成

1. `build_data_pack(...)`、`build_result_pack(...)`、`extract_active(...)` 固定为唯一 producer 真值入口。
2. Python 侧不再公开 `DataPack.__new__` / `ResultPack.__new__`。
3. Python 侧不再公开 pack setter。
4. Rust 生产代码除 producer 真值入口内部外，不再直接 `DataPack::new_checked(...)` / `ResultPack::new_checked(...)` 构建正式 pack。
5. `active_extract.rs` 与 `slicing.rs` 回到 producer 真值入口体系。
6. `run_result.py`、测试辅助、公开接口文档不再把 pack 当自由构造对象。

### 2.3 阶段验收

1. `src` 生产代码中不存在 pack 旁路构造。
2. Python stubs 中不存在 `DataPack.__new__` / `ResultPack.__new__` 与 pack setter。
3. `py_entry` 与 `doc/structure` 中不再把 pack 直接构造写成正式示例。
4. `02_spec/01_pack_producer_contracts.md` 对应的委托规则在代码结构上已经可见。

## 3. Stage 2: 执行层主链重构

### 3.1 目标

删除 `BacktestContext`，把 single / batch / WF / optimizer / sensitivity 都收回同一条内部执行主链。

### 3.2 本阶段必须完成

1. 公开设置从 `execution_stage / return_only_final` 迁移为 `stop_stage / artifact_retention`。
2. 内部单次执行器收口为 `execute_single_pipeline(...)`。
3. 内部正式引入严格 `PipelineRequest` 与严格 `PipelineOutput`。
4. 公开 backtest 入口命名收口为 `run_single_backtest(...)` / `run_batch_backtest(...)`，旧命名 `run_backtest_engine(...)` / `py_run_backtest_engine(...)` 退出正式接口面。
5. `top_level_api.rs` 不再同时承载公开入口、内部执行器与 PyO3 绑定三种职责。
6. `utils/context.rs` 退出执行主链并删除。
7. `optimizer/evaluation.rs` 下歧义的 `run_single_backtest(...)` 让出名称。

### 3.3 阶段验收

1. `BacktestContext` 与 `execute_single_backtest(...)` 不再作为正式设计残留在主链中。
2. backtest 公开模式入口正式收口为 `run_single_backtest(...)` / `run_batch_backtest(...)`，旧命名退出主接口面。
3. Rust 正式模式入口只保留 `run_*`，PyO3 wrapper 只保留 `py_run_*`，内部能力只保留 `execute_* / evaluate_*`。
4. 内部请求与输出正式收口为 `PipelineRequest -> PipelineOutput`，不再残留 `PipelineStart / PipelineArtifacts`。
5. `ResultPack` 不再作为内部执行中间货币。
6. 旧字段迁移后的主要使用面保持行为等价。

## 4. Stage 3: 模式调用面与外围链路收束

### 4.1 目标

让 Python runner wrapper、WF / optimizer / sensitivity、export / display、source time 全部回到新的正式边界，不再各自保留旧解释层。

### 4.2 本阶段必须完成

1. WF 内部通过 `execute_single_pipeline(...)` 收束 first eval、natural replay、final replay、stitched performance。
2. optimizer / sensitivity 的 single pipeline 调用收口为 `evaluate_param_set(...)` 语义。
3. `validate_wf_indicator_readiness(...)` 退出正式入口体系。
4. Python runner wrapper 层收口为 `Backtest + RunnerSession + *View + PreparedExportBundle` 四层。
5. 旧命名 `RunResult`、`BatchResult`、`WalkForwardResultWrapper`、`OptimizeResult`、`SensitivityResultWrapper`、`OptunaOptResult` 退出正式命名。
6. export adapter / packager 收口到 `ExportPayload` 分层，display/save/upload 收口到 `PreparedExportBundle`。
7. source time / stitched time 统一收口到严格递增。
8. `renko_timeframes`、`generate_renko`、`calculate_renko` 退出正式入口与正式文案。

### 4.2.1 Python runner wrapper 子顺序

为避免只改到 adapter / packager 而把 Python 结果层留在半旧状态，本阶段内部必须按下面顺序推进：

1. 先引入 `RunnerSession`，清掉 `context: dict` 的共享上下文承载方式。
2. 再把 `Backtest.run / batch / walk_forward / optimize / sensitivity / optimize_with_optuna` 的正式返回对象改成 `*View`。
3. 再把 single / WF 的正式导出入口改成 `prepare_export(...) -> PreparedExportBundle`。
4. 最后删除旧 wrapper 名、`run_result` 代理、`__getattr__` 透传和 view 上的导出缓存。

### 4.3 阶段验收

1. WF 主链不再手动拆 `ResultPack` 再局部补跑 leaf 阶段。
2. `walk_forward/window_runner.rs` 与 `walk_forward/stitch.rs` 中不再保留旧阶段控制分叉。
3. Python precheck 相关公开入口、测试口径、文档口径完成迁移。
4. Python wrapper 不再保存 `context: dict`、`run_result` 代理、`__getattr__` 透传和 view 上的导出缓存。
5. export/display 只在 adapter / bundle 边界解释结果语义。
6. `Backtest.*` 的正式返回对象已经全部收口到 `*View`，不再对外暴露旧 wrapper 名。
7. 只有 `SingleBacktestView` 与 `WalkForwardView` 保留 `prepare_export(...)`；其他 view 不定义该入口。

## 5. Stage 4: 最终清扫与回归

### 5.1 目标

完成 breaking 清扫、stub 同步、旧术语最终扫描和正式验证。

### 5.2 本阶段必须完成

1. 执行 `Legacy Kill List` 最终扫描。
2. 更新 stubs 与公共接口文档。
3. 串行执行 `just check` 与 `just test`。
4. 回填 `04_review` 的执行与验收结果。

### 5.3 阶段验收

1. 旧字段、旧函数、旧术语、旧示例不再残留在正式代码路径。
2. 静态检查通过。
3. 相关测试通过。
4. `04_review` 已记录最终结果。
