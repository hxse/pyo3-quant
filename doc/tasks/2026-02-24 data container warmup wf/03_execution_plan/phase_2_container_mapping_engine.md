# Phase 2 执行文档：容器 + Mapping + 回测主链落地

## 1. 目标

完成容器与回测主链重构：`run_ranges` 入容器、mapping 重构、回测口径收敛，并完成大规模 pytest 迁移。

## 2. 本阶段范围

1. `DataContainer` 增加 `run_ranges`，并保持 API 只读约束。
2. `BacktestSummary` 增加 `run_ranges`。
3. 落地统一构建函数：
   - `build_data_container(source, base_data_key, run_ranges, skip_mask?)`
4. mapping 构建流程重构：
   - 结构上保持 mapping 全长；
   - 校验只绑定非预热 `data_range`；
   - `base_data_key` 必须是最小周期；
   - `source` 原始 DF 全区间 `null/NaN` Fail-Fast。
5. 回测引擎主链口径落地：
   - 指标/信号/回测全量执行；
   - 绩效仅统计 `data_range`；
   - 预热禁开仓在 signal 阶段。
6. pytest 大规模迁移（本阶段重点）：
   - 所有手工拼旧容器样例改为统一构建路径；
   - 资金列与回归护栏测试全部修正并通过。

## 3. 非目标（明确不做）

1. 不改 WF 窗口算法与注入算法。
2. 不改 WF 输出结构（留到 Phase 3）。

## 4. 实施步骤

1. 先改类型与构建函数，再改 mapping 校验。
2. 接着改回测主链口径。
3. 最后做测试迁移：
   - 先迁移公共 fixture/构造器；
   - 再迁移各用例断言；
   - 每批迁移后跑对应 pytest 子集。

## 5. 验收命令

1. `just check`
2. `just test-py path="py_entry/Test/backtest"`
3. `just test`

## 6. 完成标准

1. 旧容器构造方式在测试中不再出现。
2. mapping 与回测主链新口径稳定通过。
3. 单次回测/优化/抖动相关测试全绿。

## 7. 风险与应对

1. 风险：pytest 迁移量最大，可能出现连锁失败。
   应对：按子目录分批迁移，避免一次性改全量。
2. 风险：mapping 校验口径改动引入边界失败。
   应对：保留失败路径专项测试，所有异常必须可诊断。
