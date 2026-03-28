# 统一 Ranges / Warmup / WF 重构摘要阅读入口

原 `task_summary.md` 已按运行流程拆分为多份顺序文档，避免继续维护单个 1000+ 行摘要。

## 场景与设计出发点

这次重构不是为了把系统做得“更抽象”，而是为了把本来就存在的复杂度收回到框架内部，避免继续外包给调用方。

这里还必须先写死一个总前提：

1. 这个任务属于高复杂度、高耦合、高风险链路，不能采用氛围编程。
2. 对这种任务，“先写个差不多能跑的版本再慢慢修”是危险的，因为错误往往不是直接报错，而是 quietly wrong。
3. 多周期、warmup、mapping、WF、stitched 一旦混在一起，任何一个对象来源、索引空间、边界条件写模糊，后续实现都很容易漂。
4. 因此本任务必须先把摘要文档写到足够细，先把接口、算法、边界、失败策略讲清楚，再进入执行与代码落地。
5. 文档在这里不是装饰，而是为了把复杂系统的真值先收敛清楚，尽量避免实现阶段静默出错。
6. 只靠测试是不够的。测试只能校验“已经被明确写出来的不变量与断言”，不能替代先把口径、对象来源、索引空间和失败策略写清楚。
7. 因此在本任务里，第一优先级始终是把文档写清楚；测试是第二层，用来把文档里已经定死的真值固化下来，减少实现漂移，而不是反过来代替方案澄清。
8. 当然，也不是所有东西都值得重文档。简单、低耦合、可直接从源码肉眼确认的局部改动，不需要强行写成超细方案。
9. 但像多周期映射、warmup 传播、WF 窗口规划、stitched 拼接、跨窗状态传播、资金列重建这类链路，属于高耦合、不可视、容易静默出错的问题域；这类地方如果不先把文档写清楚，后面最容易 quietly wrong。
10. 因此本任务的文档重点不是“面面俱到”，而是优先把那些最难靠直觉、最难靠局部测试兜住的真值链条先钉死。

核心场景：

1. 项目需要同时支持多周期数据、自动预热、统一回测、向前测试、窗口切片与 stitched。
2. 这些能力一旦组合起来，复杂度就不再是单个函数级别，而是时间轴、mapping、ranges、窗口语义之间的整体一致性问题。
3. 尤其在大周期指标场景下，例如 `1h` base 叠加 `1d EMA200`，若没有自动 warmup 与统一切片规则，会浪费大量数据与有效样本，直接影响训练与测试质量。

设计出发点：

1. 能由程序统一负责的，就不让用户负责。
2. 不把多周期 mapping、warmup、WF 切片、stitched 这类高风险逻辑外包给用户手写经验值或临时脚本。
3. 不采用 `backtesting.py` 一类“用户自由编排、框架只做部分约束”的模式，而是追求唯一写法、唯一语义、唯一工作流。
4. 复杂度不追求消失，而是要内聚到少数几个真值入口与专用工具函数里，对外只暴露统一接口。

在类型边界上，本任务再补一条硬约束：

1. 只要某个核心输入/输出类型可以直接在 Rust 端定义并通过 PyO3 暴露，就必须以 Rust 为唯一事实源，并通过 `just stub` 自动生成 `.pyi`。
2. 对这类核心边界类型，Python 侧不得再定义同语义的镜像类型、平行 dataclass、平行 Pydantic 模型或手写 `.pyi`。
3. Python 侧允许保留的，只应是：
   - 业务包装器
   - 展示 / 导出辅助对象
   - 不属于 Rust 核心边界的纯 Python 配置
4. 因此本任务里的 `DataPack / ResultPack / SourceRange / WalkForwardConfig / WalkForwardResult / WindowArtifact / StitchedArtifact / NextWindowHint` 等核心边界类型，都应优先走 Rust 定义 + stub 生成，不再在 Python 端重复维护一份。

在错误系统上，也补一条同级约束：

1. 本任务涉及的新错误与失败分支，必须优先复用项目现有的 Rust 错误体系，不新增平行错误系统。
2. 优先复用 `src/error` 下已经存在的错误入口与子错误类型，例如：
   - `QuantError`
   - `BacktestError`
   - `IndicatorError`
   - `SignalError`
   - `OptimizerError`
3. 只有在现有错误枚举无法表达时，才允许在原有错误体系内部补分支；不允许为了某个局部功能单独再起一套新错误类型。
4. Python / PyO3 暴露层也应直接承接这套 Rust 错误映射，不在 Python 端再额外包装一套平行异常语义。

这套设计最终追求的不是“自由拼装”，而是五个明确目标：

1. 方便：尽量减少用户手动维护 warmup、mapping、切片、拼接的负担。
2. 安全：尽量把容易静默出错的逻辑前置成框架约束与硬校验。
3. 唯一写法：减少平行写法、经验写法和临时口径，避免同一问题出现多套实现。
4. 大一统：把多周期数据、预热、回测、向前测试、切片、拼接统一到同一套容器语义与工作流中。
5. 一条命令工作流：最终希望用户与 AI 都只需要走统一入口，而不是在 Python 层手工编排大量隐性逻辑。

同时，这套设计明确拒绝“静默容错”：

1. 能明确判定为错误的情况，就直接报错，不做模糊回退。
2. 能在框架层提前校验的地方，就做强校验，不把不确定状态留到策略层或用户层。
3. 目标不是“尽量跑起来”，而是“要么口径自洽地跑通，要么尽早明确失败”。

对关键算法的抽象也必须谨慎：

1. 只有当抽象不会损失场景语义、反而能让语义更清楚时，才值得做。
2. 对 warmup、ranges、mapping、WF 窗口投影、stitched 这类高耦合环节，宁可保持专用表达，也不要为了形式统一而过度泛化。
3. 本任务更适合“真值入口统一、关键场景专用表达”，而不是把所有算法强行抽成一个看似通用的大接口。

因此，这次方案的目标不是“看起来简单”，而是：

1. 在框架层把 warmup、ranges、mapping、切片、拼接、WF 的口径一次定死。
2. 即使后续换语言重新实现，也不容易在核心语义上跑偏。
3. 让用户层与 AI 调用层尽量只做配置和网络请求，而不是承担隐性高风险逻辑。

阅读顺序：

1. [01_overview_and_foundation.md](./01_overview_and_foundation.md)
   - 破坏性更新声明
   - 指标预热契约与测试现状
   - `DataPack / ResultPack / SourceRange`
   - `mapping.time`、ranges 不变式
   - 三个统一时间工具函数：
     - `exact_index_by_time(...)`
     - `map_source_row_by_time(...)`
     - `map_source_end_by_base_end(...)`
   - 首尾覆盖与共享 mapping builder

2. [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)
   - Python 只保留网络请求
   - Rust 取数状态机与两阶段补拉算法
   - 初始 `ranges` 计算与 `DataPack` 返回
   - 非 base source 的时间投影统一复用 `01` 的时间工具函数

3. [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)
   - 单次回测主流程
   - `build_result_pack(...)`
   - `extract_active(...)`
   - 绩效模块内部按当前 `DataPack.ranges` 只统计非预热段

4. [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)
   - WF 窗口生成
   - DataPack 窗口切片
   - 跨窗信号注入与窗口执行流程
   - stitched、校验与 stitched 资金列重建
   - 明确只支持 `step = test_active_bars`
   - stitched 阶段不再关心预热补回，直接处理 `test_active`
   - WF 预热配置的摘要方案最终收敛为 `BorrowFromTrain | ExtendTest` 加 `ignore_indicator_warmup: bool`；默认值固定为 `false`

5. [../02_execution/01_execution_plan.md](../02_execution/01_execution_plan.md)
   - 执行顺序
   - 文件修改清单
   - 关键接口
   - 删除项与不保留兼容层
   - 测试计划与验收顺序

6. [../02_execution/02_test_plan.md](../02_execution/02_test_plan.md)
   - 测试分层
   - 推荐保留的 PyO3 测试工具函数
   - WF 测试性能约束
   - 建议新增测试文件清单

拆分原则：

1. 按运行流程组织：先 Python 层，再构建数据，再回测，再向前测试。
2. 原单体文档中的算法细节、边界条件、失败策略必须保留，不允许因拆分而省略。
3. `build_data_pack(...)` / `build_result_pack(...)` 仍是统一入口；切片与拼接仍采用两层模型。
