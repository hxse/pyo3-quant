# 向前测试、窗口切片、跨窗注入与 stitched

本卷是 WF / stitched 的 owned 文档入口。

本卷统一引用共享 warmup / mapping / container 定义，正文只写窗口级真值、窗口执行流程和 stitched 上游输入准备。

## 本卷作用

1. 定义 `WalkForwardConfig`、参数来源、窗口模式与窗口几何。
2. 定义 `build_window_indices(...)`、窗口 `DataPack` 切片与 ranges 草稿。
3. 定义跨窗 carry 注入、尾部强平与窗口正式返回。
4. 定义 stitched 上游输入如何准备，并把 replay 真值边界交给 `05`。

## 分卷地图

### [04_walk_forward_and_stitched_1_windowing_and_injection.md](./04_walk_forward_and_stitched_1_windowing_and_injection.md)

负责：

1. WF 输入与参数来源
2. `build_window_indices(...)`
3. `slice_data_pack_by_base_window(...)`
4. 跨窗信号注入

### [04_walk_forward_and_stitched_2_window_execution_and_return.md](./04_walk_forward_and_stitched_2_window_execution_and_return.md)

负责：

1. 每个窗口的执行流程
2. 阶段对象契约
3. `WindowArtifact / WalkForwardResult / StitchedArtifact`

### [04_walk_forward_and_stitched_3_stitched_algorithm.md](./04_walk_forward_and_stitched_3_stitched_algorithm.md)

负责：

1. stitched 正式上游输入
2. `stitched_data`
3. `stitched_signals / stitched_indicators_with_time / backtest_schedule / stitched_atr_by_row`

## 和其他卷的边界

1. `01` 归属 warmup 真值链、容器不变式、时间投影工具函数。
2. `03` 归属 `build_result_pack(...)` 与 `extract_active(...)` 的容器语义。
3. `05` 归属 segmented replay、schedule backtest、kernel 与 schema 真值。

## 阅读提醒

1. `04` 真正直接消费的是 `W_required[k]`，但真正落地到切片与重基时，只能认当前窗口的 `warmup_by_key[k]` 与最终 `ranges[k].warmup_bars`。
2. stitched 阶段的职责是准备 replay 输入；正式 stitched backtest 真值由 `05` 的 segmented replay 生成。
