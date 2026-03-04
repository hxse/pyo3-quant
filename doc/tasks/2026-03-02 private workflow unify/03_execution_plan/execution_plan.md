# 私有工作流统一重构：执行文档（最终落地版）

## 1. 执行目标

1. 策略协议统一为 `CommonStrategySpec` 单轨。
2. 搜索、测试、注册器、机器人消费同一执行协议。
3. 删除旧中间层与兼容层，不保留双轨实现。

## 2. 已执行项（最终）

### A. 协议与加载

1. 三类类型落地：`CommonStrategySpec`、`SearchSpaceSpec`、`TestStrategySpec`。
2. `build_strategy_bundle()` 作为策略唯一入口。
3. `spec_loader` 强校验策略入口与返回类型。
4. 搜索扫描排除 `common.py`，避免误识别。

### B. 搜索空间组织

1. `search_spaces` 强制子目录组织。
2. 每个子目录必须有 `common.py`。
3. 策略文件从 `common.py` 派生。
4. 日志写入同子目录 `logs/`。

### C. 执行链重构

1. 删除 `core/template.py`。
2. `strategy_searcher` 拆分为：
   - `searcher_args.py`
   - `searcher_runtime.py`
   - `searcher_serialize.py`
   - `searcher_output.py`
   - `strategy_searcher.py`（薄 orchestrator）
3. `executor.py` 保持统一阶段执行入口。

### D. 日志系统统一

1. 删除旧字符串日志（`key=value` 与 `*.brief=` 前缀）。
2. 控制台阶段输出统一标准 JSON（含 `stage`、`level`、`performance`）。
3. `backtest/optimize/sensitivity/walk_forward` 全部统一口径。

### E. 注册器与机器人

1. 注册器字段精简为：
   - `log_path`
   - `symbol`
   - `mode`
   - `enabled`
   - `position_size_pct`
   - `leverage`
2. 参数来源按 `mode` 固定推导，不再手填 `param_source`。
3. 同一 `symbol` 仅允许一个 `enabled=true` 条目，冲突即失败。

### F. 测试侧兼容层清理

1. 删除 `test_strategies/base.py`。
2. 删除 `StrategyConfig` 投影转换。
3. `get_all_strategies()` 直接返回 `TestStrategySpec`。
4. 相关测试夹具与共享 runner 全部改为 `TestStrategySpec`。

### G. 旧入口清理

1. 删除 `runner/pipeline.py`。
2. 删除 `runner.__init__` 里 pipeline 导出。
3. `strategy_hub.__init__` 不再依赖 template 中间层。

## 3. 验证结果

1. `just check` 通过。
2. `just workflow --strategies sma_2tf --symbols BTC/USDT --mode backtest` 可执行并正常落日志。
3. `py_entry/Test/strategy_hub/test_strategy_hub_precheck_entrypoints.py` 通过。

## 4. 验收清单（当前状态）

1. 无 `core/template.py`。
2. 无 `runner/pipeline.py`。
3. 无 `test_strategies/base.py` 与 `StrategyConfig` 运行依赖。
4. 搜索策略均可通过 `build_strategy_bundle()` 加载。
5. `just workflow` 为统一主入口并保持可组合模式执行。

## 5. 后续维护约束

1. 新增搜索策略必须遵守“子目录 + common.py + 派生策略文件”。
2. 新增日志字段优先 Rust 输出，Python 仅透传展示。
3. 禁止恢复旧兼容层与双入口执行链。

## 6. 运行约束补充（2026-03-04）

1. 机器人启动阶段不再扫描仓库全量策略名；仅对“已注册且 enabled 的策略条目”执行 `strategy_name` 唯一性校验。
2. 机器人运行阶段只使用启动时装载的已注册策略内存映射，不做全量策略扫描。
3. `just workflow` 入口保持全量扫描：启动时遍历 `search + test` 全部策略，执行重复名与加载合法性校验。
4. 关闭模块发现缓存能力：`spec_loader.discover_modules()` 每次按当前文件系统实时扫描，不保留缓存状态。

## 7. 本轮执行更新报告（2026-03-04）

1. `registry/loader.py` 已移除全局策略名校验调用，改为“已注册条目策略名唯一性”校验。
2. `strategy_name_guard.py` 维持无缓存实现，`workflow` 入口仍执行全量校验。
3. `spec_loader.py` 已删除模块发现缓存与缓存清理函数，相关导出同步移除。
4. 新增 `test_registry_loader.py` 覆盖“已注册策略重名报错/唯一名通过”两类场景。
5. 验证结果：`just check` 通过，`just test` 通过。
