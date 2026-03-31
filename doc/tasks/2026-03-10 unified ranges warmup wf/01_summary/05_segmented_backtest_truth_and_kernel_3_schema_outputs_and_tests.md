# 分段真值回测、可变 ATR 与对现有主循环的精准抽象（三）output schema、stitched 输入与测试

## 10. output schema 的正式口径

如果不同 segment 打开了不同的风险功能，最终 backtest 结果到底包含哪些列？

1. `run_backtest(...)` 在内部也先退化成单段 `schedule`，再走 `run_backtest_with_schedule(...)`。
2. 因此这里的 `output schema` 规则统一按 schedule 路径定义。
3. 若 `schedule` 只有一个 segment，则 `build_schedule_output_schema(schedule)` 必须退化成当前固定 schema。
4. 只有在多段 schedule 且不同 segment 打开了不同风险功能时，最终 backtest 结果才会出现并集列。
5. stitched schedule 回测的输出列集合，取所有 segment 的**并集**。
6. 只要某个列在任意一个 segment 里可能被写入，它就属于最终 stitched backtest 的合法列。
7. 对于当前 row 未启用的功能列：
   - 该列保留
   - 但当前 row 只写文档已定义的非激活态默认值

当前这条 contract 要再写死一层：

1. 当前 multi-segment output schema 里，按 segment 启用/停用变化的可选功能列，正式范围只包括各类风险价格列：
   - `sl_pct_price_*`
   - `tp_pct_price_*`
   - `tsl_pct_price_*`
   - `sl_atr_price_*`
   - `tp_atr_price_*`
   - `tsl_atr_price_*`
   - `tsl_psar_price_*`
2. 这些列当前全部是 `f64` 数值列。
3. 因而“未启用 segment 的非激活态默认值”在当前正式语义下统一写死为：
   - `f64::NAN`
4. 也就是说：
   - 列存在但当前 segment 未启用该功能 -> 写 `NaN`
   - 列存在且当前 segment 启用了该功能，但该 row 暂无有效价格 -> 也写 `NaN`
5. 因此 `NaN` 在多段 schedule 下只表示“当前 row 没有可写价格”，不再区分“功能未启用”和“功能已启用但当前无有效价格”。
6. 当前 contract 不覆盖“可选布尔列默认写 `false` 还是 `null`”这类情况，因为本方案当前没有这类按 segment 可变的可选布尔输出列。
7. 若后续引入新的可选非 `f64` 输出列，必须先在摘要里显式补充该列类型及其非激活态默认值，不能沿用隐式规则。

并集输出的不良影响也要一起写清楚：

1. 在 schedule 路径里，列存在的正式语义是：这列对应的功能至少在某个 segment 中启用过。
3. 因此对某个具体 row 来说：
   - 列存在，不代表当前 row 所属 segment 一定启用了这类风控
   - 当前值为 `NaN`，可能表示“该功能已启用但当前 row 没有有效价格”，也可能表示“当前 segment 根本没开这类功能”
4. 所以下游若要判断某 row / 某 segment 是否真的启用了某类风控，不能只看列是否存在或当前值是否为 `NaN`，必须结合最终结果里保留的 `stitched_result.meta.backtest_schedule` 判断。
5. 因而真正需要显式承认差异的，不是“单参数入口 vs schedule 入口”，而是“单段 schedule vs 多段 schedule”。

## 11. stitched 阶段到底要产出什么

stitched 阶段的正式产物如下。

### 11.1 必需产物

1. `stitched_data_pack`
   - 表示 stitched test-active 轴上的正式 `DataPack`
2. `stitched_indicators_with_time`
   - stitched 阶段拼出来的结果态 indicators
   - 每个 `k` 都带 `time` 列
   - 在最终生成 stitched `ResultPack` 前，必须先统一走 `strip_indicator_time_columns(...)`
3. `stitched_signals`
   - 与 `stitched_data_pack.base` 一一对齐
   - 直接由各窗口 `test_active_result.signals` 拼接得到
   - 也就是各窗口 `final_signals` 的 active-only 可见部分
   - 当前正式语义下，carry 开仓写在 active 第一根，因此 `extract_active(...)` 会保留 carry 行
   - 当前正式语义接受这条保守约束：
     - carry 开仓会在第二根 active bar 开盘执行
4. `backtest_schedule`
   - 每段对应一套 `BacktestParams`
   - replay 完成后保存到 `stitched_result.meta.backtest_schedule`
   - 这里保存的必须是 replay 实际使用并已通过校验的同一份 schedule，不允许在 replay 后再反推第二份
5. `stitched_atr_by_row`
   - 若存在，则与 `stitched_data_pack.base` 一一对齐

### 11.1.1 `stitched_atr_by_row` 的双层校验

`stitched_atr_by_row` 同时属于 stitched 构造结果和 `run_backtest_with_schedule(...)` 的正式输入契约，因此要求双层校验：

1. stitched 外层负责语义校验：
   - 是否该有就有、该无就无
   - 是否与 stitched base 轴和 schedule 完全对齐
   - 是否按每行所属 segment 的 ATR 语义正确物化
2. `run_backtest_with_schedule(...)` 负责硬契约校验：
   - 是否缺失
   - 是否多传
   - 长度是否匹配

kernel 不允许在内部重算 ATR 反向验证外层结果；这里只做 fail-fast，不做语义重建。

### 11.2 可选附加产物

1. 窗口级调试 artifact
   - 若需要审计窗口内部行为，则保留

### 11.3 不再作为正式 stitched 真值来源的产物

下面这些产物不再作为 stitched backtest 正式真值来源：

1. 窗口 `backtest` 直接拼接结果
2. stitched 后再人工重建资金列的 backtest 草稿

最终 stitched `ResultPack` 的落地顺序也要写死：

1. 先得到 `stitched_backtest_truth`
2. 再计算 `stitched_performance`
3. 再执行：
   - `stitched_raw_indicators = strip_indicator_time_columns(stitched_indicators_with_time)`
4. 最后统一调用 `build_result_pack(...)` 构建最终 stitched `ResultPack`
5. 最终结果里正式保留：
   - `stitched_result.meta.backtest_schedule`
   - 作为多段 backtest 输出的正式解释元数据

它们若保留，只能是 debug artifact，不是正式结果入口。

## 12. 对 `03-10` 现有方案的影响范围

本方案对现有 `03-10` 文档体系的影响很集中：

### 12.1 基本不受影响

1. [01_overview_and_foundation.md](./01_overview_and_foundation.md) 的 shared resolver 与 warmup 三层口径。
2. [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md) 的 planner 与初始构建。
3. [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 里单次回测、`build_result_pack(...)`、`extract_active(...)` 的基本容器语义。

### 12.2 主要受影响

真正需要替换思路的，主要是 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 里 stitched backtest 生成末段：

1. 不再拼窗口 `backtest`。
2. 不再重建资金列作为 stitched backtest 正式真值。
3. 改为：
   - stitched `signals`（直接拼接窗口 `test_active_result.signals`）
   - stitched `atr_by_row`
   - `backtest_schedule`
   - `run_backtest_with_schedule(...)`

因此，本方案对 `03-10` 的影响不是“全盘推倒重来”，而是：

1. 上游窗口级生产逻辑基本不动。
2. 最终 stitched backtest 的构建方式整体替换。

### 12.3 如何验证“精准改造且语义等价”

1. 主测试只放 Rust，不放 pytest。
2. 更合适的落点是：
   - 在 [mod.rs](/home/hxse/pyo3-quant/src/backtest_engine/backtester/mod.rs) 增加 `#[cfg(test)] mod tests;`
   - 新建 [tests.rs](/home/hxse/pyo3-quant/src/backtest_engine/backtester/tests.rs)
3. 测试直接比较：
   - `legacy_run_backtest_reference(...)`
   - `run_backtest(...)`
   - 冻结顺序必须写死：
     1. 先在当前旧 `run_backtest(...)` 实现上完成 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 已写死的 `has_leading_nan` 收口修正，即：
        - `has_leading_nan` 只保留在 `signals`
        - 不再参与回测核心逻辑
        - 不再透传到 `backtest`
        - 不再被 `performance` 读取
        - 一句话概括：除 `signals` 外，其他模块都不应再感知或消费 `has_leading_nan`
     2. 再把这份已经收口后的旧实现改名存档为 `legacy_run_backtest_reference(...)`
   - 也就是说，这个 reference 不是“带着历史错误行为的冷冻拷贝”，而是“先完成正式契约修正，再冻结”的测试基线
   - 除这条 `has_leading_nan` 收口修正外，其余旧实现逻辑都按原样冻结，只作为等价性测试基线使用
4. 这里的“一致”不能只做模糊比较，至少要显式断言：
   - 列名集合一致
   - 列顺序一致
   - 每列 dtype 一致
   - 行数一致
   - 每列逐值一致
   - `backtest` 输出里都不应再出现 `has_leading_nan`
5. 测试数据的构造也必须写死：
   - 不要求所有价格数据都手工一根根写出
   - 原始 `source` 数据可以使用**固定 seed 的确定性随机 fixture**
   - 但随机数据不能过于平缓，必须刻意做出**足够大的趋势**和**足够大的波动**
   - 否则很多 case 只会验证“能跑完”，却覆盖不到真实的开平仓、风控触发和资金变化
   - 但 `signals` 最好手工构造，以便明确覆盖开仓、平仓、冲突信号和预处理分支
   - 同一份 fixture 必须同时喂给：
     - `legacy_run_backtest_reference(...)`
     - 新的 `run_backtest(...)`
   - 不能让两边各自造一份近似数据再比较
6. 这份 fixture 至少应包含：
   - 一份单 source 的原始 `source` 数据
   - base source 上完整的 `time/open/high/low/close`
   - 可直接喂给 `build_data_pack(...)` 的 `base_data_key + ranges`
   - `entry_long / exit_long / entry_short / exit_short` 四列 signals
7. 这里的正式 `DataPack` 应优先复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 与 [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md) 已定义的 `build_data_pack(...)` 构造：
   - 测试里可以准备固定 seed 的原始 `source` 数据，并手工准备 `ranges / signals`
   - 但不应再手工拼 `mapping` 充当正式输入
   - `mapping` 真值仍应由 `build_data_pack(...)` 内部收口生成
8. 为了避免“主流程大体能跑，但关键分支没覆盖”，测试数据最好至少拆成三类确定性 case：
   - 基础 case：
     - 不启用 ATR
     - 不带 `skip_mask`
     - 只验证基础单次回测流程等价
   - ATR case：
     - 启用至少一个 ATR 相关参数
     - 让 `calculate_atr_if_needed(...)` 明确走到 `Some(atr_series)` 分支
     - 覆盖 ATR 输入链与可选列 schema
   - 预处理 case：
     - 显式带 `skip_mask`
     - 最好再带一两处冲突 signals
     - 用来验证 `PreparedData::new(...)` 前的信号预处理没有被重构破坏
9. 所有 case 都应满足：
    - `data_length > 2`
    - 至少发生一次真实开平仓
    - 价格路径要有足够大的趋势与波动，避免回测结果过于平淡
    - 不只是“能跑完”，而是能让资金列、价格列、可选列都真正写出非平凡结果

## 13. 本方案不解决什么

为了避免范围膨胀，本篇直接把非目标写死：

1. 不把指标层改造成“同一趟全局运行时按段切指标参数”。
2. 不把信号层改造成“同一趟全局运行时按段切信号参数”。
3. 不引入 trade-owned 参数快照语义。
4. 不处理“窗口之间重叠 test_active”的情况；仍沿用 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 的非重叠前提。

## 14. 本篇最终结论

1. stitched 真值的正式路径是：先 stitched 出输入，再让回测引擎沿连续时间轴执行一次。
2. 指标和信号维持按窗口生成，不需要连带重写上游架构；其中 stitched 正式信号直接复用窗口 `test_active_result.signals`。
3. 需要新增 `run_backtest_with_schedule(...)`，但真正的核心设计是一套内部通用 backtest kernel；它是对现有主循环的精准抽象，不是第二套回测引擎。
4. `04` 的跨窗注入与窗口尾部强平语义保留，`05` 直接消费这套 stitched 信号边界规则。
5. 这样窗口正式返回与 stitched 连续回放使用的是同一份信号语义，更一致，也更接近实盘换参时“先平再开”的可执行流程。
6. `atr_period` 可以允许变化；只要把 `atr_by_row` 当成 schedule 回测的正式输入，而不是回测 kernel 内部现算的隐藏中间量即可。
