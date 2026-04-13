# Legacy Kill List

## 1. 旧执行字段与旧命名

下面这些旧口径在本任务落地后应从正式代码路径中消失：

1. `execution_stage`
2. `return_only_final`
3. `execute_single_backtest`
4. optimizer 下歧义的 `run_single_backtest`
5. `run_backtest_engine`
6. `py_run_backtest_engine`
7. `BacktestContext`

## 2. 旧 precheck / guard 支线

下面这些旧支线不再保留：

1. `validate_wf_indicator_readiness(...)`
2. shared guard / execution entry guard 的独立设计支线
3. `skip_validation`
4. “入口再兜底一次 DataPack 合法性”的旧口径

## 3. 旧 pack 构造方式

下面这些旧构造方式必须退出正式路径：

1. Python 侧直接 `DataPack(...)`
2. Python 侧直接 `ResultPack(...)`
3. Python 侧 pack setter
4. Rust 生产代码直接 `DataPack::new_checked(...)`
5. Rust 生产代码直接 `ResultPack::new_checked(...)`
6. 其他旁路手造正式 pack object 的写法

## 4. 旧 WF 局部执行方式

下面这些旧控制流必须收口：

1. WF 手动拆 `ResultPack` 再补跑局部 leaf 阶段
2. `walk_forward/window_runner.rs` 中基于旧 `SettingContainer` 字段的阶段覆盖写法
3. `walk_forward/stitch.rs` / `window_runner.rs` 中直接 `analyze_performance(...)` 的旧阶段控制路径

## 5. 旧 pack producer 残留

下面这些位置必须作为最终扫描关键点：

1. `src/backtest_engine/data_ops/active_extract.rs`
2. `src/backtest_engine/data_ops/slicing.rs`
3. `py_entry/runner/results/run_result.py`
4. `py_entry/Test/signal/utils/mapping_helpers.py`
5. `py_entry/Test/backtest/common_tests/test_top_level_api_validation.py`
6. `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
7. `py_entry/Test/backtest/test_extract_active_contract.py`

## 6. 旧 Python wrapper / 导出方法 / 透传口径

下面这些旧口径也必须退出正式路径：

1. `RunResult`
2. `BatchResult`
3. `WalkForwardResultWrapper`
4. `OptimizeResult`
5. `SensitivityResultWrapper`
6. `OptunaOptResult`
7. `format_for_export(...)`
8. `run_result` 代理
9. `__getattr__`
10. `context: dict`
11. `export_buffers`
12. `export_zip_buffer`

## 7. 旧 source time / Renko 口径

下面这些旧口径必须退出正式接口、正式测试和正式文案：

1. `renko_timeframes`
2. `generate_renko`
3. `calculate_renko`
4. “非 base source 非递减即可”
5. “Renko 只是重复时间戳测试载体”

## 8. 最终扫描关键词

执行完成后，默认至少扫描下面这些关键词：

1. `execution_stage`
2. `return_only_final`
3. `BacktestContext`
4. `execute_single_backtest`
5. `run_backtest_engine`
6. `py_run_backtest_engine`
7. `validate_wf_indicator_readiness`
8. `skip_validation`
9. `RunResult`
10. `BatchResult`
11. `WalkForwardResultWrapper`
12. `OptimizeResult`
13. `SensitivityResultWrapper`
14. `OptunaOptResult`
15. `format_for_export`
16. `run_result`
17. `__getattr__`
18. `context: dict`
19. `context={`
20. `export_buffers`
21. `export_zip_buffer`
22. `renko_timeframes`
23. `generate_renko`
24. `calculate_renko`
25. `DataPack::new_checked`
26. `ResultPack::new_checked`

若仍有残留，必须逐项判断它是：

1. 应删的旧逻辑
2. 必须同步迁移的测试夹具
3. 仅允许在局部负例测试中保留的最小构造手段

其中：

1. `run_result` 关键词的目标是旧 runner result proxy 语义，不是任意局部变量名。
2. `__getattr__` 关键词的目标是 Python runner view 的无边界原始对象透传，不是与 runner 结果层无关的其他委托对象。
