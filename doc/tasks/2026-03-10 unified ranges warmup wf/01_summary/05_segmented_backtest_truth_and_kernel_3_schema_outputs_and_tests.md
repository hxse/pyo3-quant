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

`build_schedule_output_schema(schedule)` 的列顺序还要写成唯一算法：

1. 先固定当前单段回测 schema 的基底列顺序：
   - `balance`
   - `equity`
   - `trade_pnl_pct`
   - `total_return_pct`
   - `entry_long_price`
   - `entry_short_price`
   - `exit_long_price`
   - `exit_short_price`
   - `fee`
   - `fee_cum`
   - `current_drawdown`
   - `risk_in_bar_direction`
   - `first_entry_side`
   - `frame_state`
2. 再只允许按下面这份预定义可选列顺序依次追加并集列：
   - `sl_pct_price_long`
   - `sl_pct_price_short`
   - `tp_pct_price_long`
   - `tp_pct_price_short`
   - `tsl_pct_price_long`
   - `tsl_pct_price_short`
   - `atr`
   - `sl_atr_price_long`
   - `sl_atr_price_short`
   - `tp_atr_price_long`
   - `tp_atr_price_short`
   - `tsl_atr_price_long`
   - `tsl_atr_price_short`
   - `tsl_psar_price_long`
   - `tsl_psar_price_short`
3. 对这份预定义序列中的每个候选列，只要它在任意一个 segment 中可能被写入，就追加一次。
4. 不允许按字母序、首次出现顺序、`HashMap` 迭代顺序或其他隐式顺序决定列顺序。
5. 因而单段 schedule 的 `output schema` 等于“基底列顺序 + 当前参数启用的那部分可选列顺序”；多段 schedule 的 `output schema` 等于“基底列顺序 + 过滤后的预定义并集列顺序”。

当前这条 contract 要再写死一层：

1. 当前 multi-segment output schema 里，按 segment 启用/停用变化的可选列，正式范围包括一条 `atr` 列和各类风险价格列：
   - `atr`
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
4. 所以下游若要判断某 row / 某 segment 是否真的启用了某类风控，不能只看列是否存在或当前值是否为 `NaN`，必须结合最终结果里保留的 `WalkForwardResult.stitched_result.meta.backtest_schedule` 判断。
5. 因而真正需要显式承认差异的，不是“单参数入口 vs schedule 入口”，而是“单段 schedule vs 多段 schedule”。

## 11. stitched 阶段到底要产出什么

stitched 阶段的正式产物如下。

### 11.1 必需产物

1. `stitched_data`
   - 表示 stitched test-active 轴上的正式 `DataPack`
2. `stitched_indicators_with_time`
   - stitched 阶段拼出来的结果态 indicators
   - 每个 `k` 都带 `time` 列
   - 在最终生成 stitched `ResultPack` 前，必须先统一走 `strip_indicator_time_columns(...)`
3. `stitched_signals`
   - 与 `stitched_data.base` 一一对齐
   - 直接由各窗口 `test_active_result.signals` 拼接得到
   - 也就是各窗口 `final_signals` 的 active-only 可见部分
   - 当前正式语义下，carry 开仓写在 active 第一根，因此 `extract_active(...)` 会保留 carry 行
   - 当前正式语义接受这条保守约束：
     - carry 开仓会在第二根 active bar 开盘执行
4. `backtest_schedule`
   - 每段对应一套 `BacktestParams`
   - replay 完成后保存到 `WalkForwardResult.stitched_result.meta.backtest_schedule`
   - 这里保存的必须是 replay 实际使用并已通过校验的同一份 schedule，不允许在 replay 后再反推第二份
5. `stitched_atr_by_row`
   - 若存在，则与 `stitched_data.base` 一一对齐

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

### 11.3 正式 stitched 真值入口

最终 stitched `ResultPack` 的落地顺序也要写死：

1. 先得到 `stitched_backtest_truth`
2. 再计算 `stitched_performance`
3. 再执行：
   - `stitched_raw_indicators = strip_indicator_time_columns(stitched_indicators_with_time)`
4. 最后统一调用 `build_result_pack(...)` 构建最终 stitched `ResultPack`
5. 最终结果里正式保留：
   - `WalkForwardResult.stitched_result.meta.backtest_schedule`
   - 作为多段 backtest 输出的正式解释元数据

## 12. 本方案不解决什么

为了避免范围膨胀，本篇直接把非目标写死：

1. 不把指标层改造成“同一趟全局运行时按段切指标参数”。
2. 不把信号层改造成“同一趟全局运行时按段切信号参数”。
3. 不引入 trade-owned 参数快照语义。
4. 不处理“窗口之间重叠 test_active”的情况；仍沿用 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 的非重叠前提。

## 13. 本篇最终结论

1. stitched 真值的正式路径是：先 stitched 出输入，再让回测引擎沿连续时间轴执行一次。
2. 指标和信号维持按窗口生成，不需要连带重写上游架构；其中 stitched 正式信号直接复用窗口 `test_active_result.signals`。
3. 需要新增 `run_backtest_with_schedule(...)`，但真正的核心设计是一套内部通用 backtest kernel；它是对现有主循环的精准抽象，不是第二套回测引擎。
4. `04` 的跨窗注入与窗口尾部强平语义保留，`05` 直接消费这套 stitched 信号边界规则。
5. 这样窗口正式返回与 stitched 连续回放使用的是同一份信号语义，更一致，也更接近实盘换参时“先平再开”的可执行流程。
6. `atr_period` 可以允许变化；只要把 `atr_by_row` 当成 schedule 回测的正式输入，而不是回测 kernel 内部现算的隐藏中间量即可。
