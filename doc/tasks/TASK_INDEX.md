# Task Index

说明：
- 本文件只用于“任务检索与回找”，不负责历史是否过时。
- 每条记录只保留：任务名 + 简短摘要（5~10 句）。
- 若与文档或实现存在歧义，最终以源代码为准。

## 2026-02-24 data container warmup wf
- 这个方案太复杂, 没有实现, 已经废除,
- 聚焦重构 DataContainer 预热与切片语义，建立 `DataContainer`、`RangedTrimmedDataContainer`、`FlatTrimmedDataContainer` 三层容器边界。
- 明确回测执行约束：回测引擎只接受包含“预热+非预热”完整执行区间的 `DataContainer`；画图切片在 Python 层调用 Rust 工具函数（PyO3 暴露）。
- 向前测试返回路径统一到“窗口返回 + 拼接返回”，并约束拼接基于各窗口非预热测试段，且可与全量连续区提取做时间序列一致性校验。

## 2026-02-27 wf warmup minimal
- **已废除：此过渡期最小实现方案已被后继的 `2026-03-10 unified ranges warmup wf` 全局大一统重构彻底取代并作废。**
- 该任务是对 2026-02-24 方案的收敛：放弃先做全局容器重构，先用最小改动解决 WF 预热不足问题。
- 核心约束是“回测引擎主链不改”，改动集中在 WF 模块和 WF 测试，降低连锁迁移风险。
- WF 新增预热参数与预热模式，保留现有过渡期实现思路：`BorrowFromTrain` 允许与训练尾部重叠，`ExtendTest` 不允许重叠。
- 在 WF 执行前新增一次 `ExecutionStage::Indicator` 预检，只校验非预热段指标有效性，不通过直接报错并提示增大预热。
- 该预检只做一次，依据是所有窗口共用同一套入口参数，窗口间参数口径不变。
- Python 侧只负责拉够数据并传参，不重复做指标预检，避免职责重叠。
- 该方案优先追求可快速落地与可回归验证，后续是否继续全局统一重构再单独决策。

## 2026-03-02 private workflow unify
- 本任务最终收敛为两类策略资产：`test_strategies` 与 `search_spaces`；策略根目录统一迁移到 `py_entry/strategy_hub/`，`example` 与 `personal` 删除。
- 公共策略后续统一迁入 `test_strategies`，且 `test` 与 `search_spaces` 使用相同写法；导入约束为“search 可导入 test，test 不能导入 search”。
- 核心工作流固定为两条命令：单策略多品种 backtest 与单策略多品种 walk_forward，用于评估是否上实盘；其他灵活命令保留。
- `just search` 默认输出日志；日志写入策略文件同目录 `logs/`，并随搜索空间子目录层级自然同构，命名采用“UTC 秒级时间 + 策略名”（不含 symbol 与顺序号）。
- 日志文件名时间格式固定 UTC（`YYYYMMDD_HHMMSS`）；同秒冲突按“延迟1秒重试3次，仍失败报错并建议重跑命令”处理。
- 日志只保留可部署的 best 参数，不保存 min/max/step 等搜索边界；单日志按“单策略多品种”组织，WF 记录每窗口完整时间与最后窗口参数。
- 日志新增 `strategy_version` 字段用于版本识别。
- 机器人不跑 WF，走“注册器 + 日志路径”模式；注册器固定 JSON，绑定键为 `(strategy_name, symbol, mode)`，仅注册时预检日志契约，缺字段全局终止。
- 机器人调度周期沿用现有机制（如最小周期 5m 则按 5m 调度），本任务不改该机制。
- 策略名唯一性只检查当前代码仓定义，历史日志不参与去重。
- 注册器条目粒度固定为“单策略单品种单仓位单模式”。
- Rust 需补齐窗口时间与 bars 元信息并统一毫秒口径，Python 仅消费展示。
- 发布口径固定：`test_strategies` 全量上传，`search_spaces` 仅上传 `sma_2tf` 示例。
- 重构前已先完成策略备份快照，并要求后续迁移继续遵循分目录备份原则。
- 测试体系要求大范围迁移到 `test_strategies + 统一接口`，旧测试入口与兼容冗余代码不保留。
- `py_entry/strategies` 旧体系要求在代码/测试/文档层面完全清理，`reversal_extreme` 维持 test 策略定位用于 Test 与 demo 验收。
- 2026-03-04 运行口径补充：机器人启动只校验“已注册且 enabled 条目”的策略名唯一性，不再扫描仓库全量策略。
- 2026-03-04 运行口径补充：机器人循环只消费已注册策略内存映射，`just workflow` 仍保持全量策略扫描与全局合法性校验。
- 2026-03-04 维护口径补充：`spec_loader` 模块发现缓存已删除，改为每次实时扫描，避免缓存状态漂移。

## 2026-03-10 unified ranges warmup wf
- 本任务聚焦统一 `ranges / warmup / mapping / walk_forward / stitched` 的整套语义，并明确拒绝氛围编程与“先跑起来再修”的路径。
- 摘要文档被拆成 `01~05` 五卷，分别覆盖基础约束、Python 网络请求与 Rust 取数、单次回测与 `extract_active(...)`、WF 与 stitched 上游输入、segmented replay 与最终 stitched 真值。
- 核心类型口径统一为 `DataPack / ResultPack / SourceRange`，其中 `SourceRange` 收敛为 `warmup_bars / active_bars / pack_bars`。
- 时间映射算法统一收口到三个工具函数：`exact_index_by_time(...)`、`map_source_row_by_time(...)`、`map_source_end_by_base_end(...)`，不再允许多处各写一套 backward asof 逻辑。
- 单次回测要求信号模块内部处理预热禁开仓，绩效模块内部按 `DataPack.ranges` 只统计非预热段。
- `extract_active(...)` 被定义为唯一显式例外：它不走 builder，只对已验证同源的 `DataPack / ResultPack` 做机械化非预热提取视图。
- WF 只支持 `step = test_active_bars`，窗口测试执行固定三段：先产出 `raw_signal_stage_result`，再用 `carry_only_signals` 跑出 `natural_test_pack_backtest_result`，最后用 `final_signals` 跑出正式 `final_test_pack_result`。
- WF 预热配置的摘要方案最终收敛为 `BorrowFromTrain | ExtendTest`，并补入 `ignore_indicator_warmup: bool` 作为显式对照实验 / 备胎开关，默认值固定为 `false`。
- stitched 的 `DataPack` 真值直接来自初始 `full_data` 的全局 `test_active` 切片，不来自窗口 `DataPack` 拼接；`04` 只负责组装 `StitchedReplayInput`，正式 stitched backtest 真值由 `05` 的 segmented replay 生成。
- 任务现已补出 `02_execution/01_execution_plan.md` 与 `02_execution/02_test_plan.md`：前者只保留实现顺序、关键接口、文件清单、删除项和验收步骤，后者单独收敛测试分层、PyO3 测试工具函数、WF 性能约束与建议新增测试文件清单。

## 2026-04-05 wf export display and precheck cleanup
- 本任务是 `2026-03-10 unified ranges warmup wf` 的后续清理任务，目标是收口 03-10 落地后仍残留的双轨解释层、旧入口和误导性外围实现。
- 任务范围集中在四条线：WF stitched 导出与 display 链路、Python `validate_wf_indicator_readiness(...)` 预检入口、重复时间戳 / Renko 残余、`BacktestContext` 与 Rust 顶层 readiness validator 的职责边界。
- WF 导出正式改为“single / WF 各自 adapter + 通用 packager”结构；single 与 WF 可以继续共享 display / bundle 消费链路，但不再共享同一套结果解释层。
- Python precheck 已退出正式 gate，workflow 不再显式依赖该入口；pack 合法性真值固定收口于 producer，执行合法性真值固定收口于 Rust pipeline 主链，如需新增 explain 工具，只允许是只读解释工具。
- 仓库当前正式口径继续写死为“时间列必须严格递增，不支持重复时间戳 source”；本任务要求删除 Renko 生成入口、删除 stitched 中“非递减即可”的旧兜底，并同步清理当前结构文档与测试残余。
- `BacktestContext` 已退出正式设计；正式执行链固定为 `PipelineRequest -> execute_single_pipeline(...) -> PipelineOutput`，不再保留并行 validator 支线。

## 2026-04-16 extensible builtin indicators
- 本任务是内置指标体系的长期扩展任务，不是单个指标的一次性任务。
- 项目正式口径固定为模板化回测引擎链路：配置只声明内置指标参数和信号模板，指标计算必须由 Rust 内置指标系统完成。
- 正式回测链路不允许运行时外部自定义指标，不允许策略局部手写指标计算，也不允许绕过 registry 挂接临时指标函数。
- 任务冻结新增内置指标的通用扩展协议：文件结构、registry 注册、参数命名、输出列命名、warmup contract、测试基准、验证入口和禁止事项。
- task 结构按长期扩展设计为 `global/` 与 `indicators/<base_name>/` 两层；后续新增指标只追加自己的单指标规格和执行记录。
- 所有内置指标默认对齐原版 `pandas-ta`；只有原版 `pandas-ta` 缺失该指标或目标模式时，才允许按项目指标优先级后退。
- `kc` 是本任务首个指标实例，正式输出列为 `<indicator_key>_lower / middle / upper`，通道宽度为 `EMA(True Range, length)`。
- `kc` 参数固定为 `length / scalar`，不提供 `period` 别名，不开放 `tr` 或 `mamode` 参数，warmup 固定为 `length` 且模式为 `Strict`。

## 2026-04-18 indicator comparison test refactor
- 本任务聚焦重构内置指标对比测试系统，先于 `2026-04-16 extensible builtin indicators` 的代码执行完成。
- 任务目标是在不改变生产指标语义的前提下，让指标测试 case 显式声明主校验源、逻辑输出列、容差、secondary oracle assertion、数据集和特殊处理；比较口径由主校验源派生，缺失值口径由全局 comparator contract 统一定义。
- 指标扩展采用高内聚目录结构：每个指标目录集中放 `cases.py / adapter.py / test_contracts.py / fixtures`，共享 `comparison/` 只保留通用 runner、compare、datasets、reporting、oracle 类型与全局 warmup 冻结测试；`test_contracts.py` 固定只包含 `test_accuracy` 与 `test_warmup_contract` 两个 pytest 薄入口。
- 项目正式 pandas-ta 对齐优先级只有四级：`pandas-ta (talib=true)`、`pandas-ta (talib=false)`、`pandas-ta-classic (talib=true)`、`pandas-ta-classic (talib=false)`；case 层面可选第五种后备主校验源 `local_csv`。
- 前四级 oracle 只能做 strict exact comparison，不允许用 similarity、correlation 或方向一致率作为通过条件。
- `local_csv` 只在用户判断前四级 oracle 全部不可用时作为后备交叉验证方式，并允许选择 exact 或 similarity；普通指标默认声明 3 个参数和数据都不同的标准 case，生成数据使用具体 `DatasetId`，本地 CSV 数据来源必须使用 `Path` 类型，`LocalCsvOracle` 不暴露重复 `path` 或 `similarity_api`。
- 任务保留并正式化“预期不一致校验”，以 secondary oracle assertion 表达 pandas-ta / pandas-ta-classic 路线中“另一个 oracle 应当 same 或 different”的场景；`local_csv` 不参与 secondary assertion，`expected_different` 复用 same comparator，并且只能精确识别 comparison mismatch。
- comparison case 不承载 warmup 数值真值；`resolve_indicator_contracts(...)` 是全局 warmup 真值入口，warmup runner 复用 `cases.py` 的 `CASES` 与 `warmup_check`，warmup skip 只作为逃生舱式特殊处理。
- 落地必须使用 Pydantic 严格模型定义 case、adapter、oracle、dataset、skip、tolerance 与 adapter 回调边界，并配合静态类型标注，通过 `just check` 与 `just test`。
- 任务明确默认行为与特殊处理边界；容差放宽、skip、列 skip、warmup skip、local CSV similarity 等特殊处理必须注释、报告并审查。
- 失败输出必须定位校验模式、指标、列、行、参数、数据源、oracle，并打印短上下文，避免指标对齐阶段日志失控。
- 由于测试框架本身很难再用测试完整证明正确性，本任务把语义新增与冻结清单作为最低审查基线，同时要求后续执行必须进行完整 diff 审查，避免测试重构漂移。
