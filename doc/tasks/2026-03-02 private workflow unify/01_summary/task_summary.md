# 私有工作流统一重构任务摘要（单策略单变体定稿）

## 任务目标
本任务目标是“协议层彻底统一，外部能力不降级”：
1. `search_spaces` 写法强制一致（`common.py + 派生`）；`test_strategies` 推荐一致但允许按测试场景简化。
2. 公共策略类型只保留最小交集字段。
3. 搜索与测试在公共类型上做扩展，不复制核心字段。
4. `just workflow`、`demo.ipynb`、registry 全链路统一消费同一协议。
5. 机器人侧保持“单品种单策略”运行约束。
6. `search_spaces` 必须按子文件夹组织策略；日志目录必须镜像相同子文件夹结构。

## 相对前版修订声明（本版生效）
1. `CommonStrategySpec` 从 `variants` 改为单字段 `variant`。
2. `variant_name`、`variant_labels` 从公共执行协议移除。
3. 注册器不再手填 `strategy_name`，策略名从日志解析并校验。
4. 注册器不再手填 `param_source`，参数来源按 `mode` 固定推导。
5. 日志定位键为 `(log_path, symbol, mode)`，并强约束“单日志文件仅允许单策略结果”。
6. 删除 `core/template.py` 中间层，统一走 `spec_loader + executor`。
7. 删除 `runner/pipeline.py` 旧独立链路，避免双入口。
8. 删除 `test_strategies/base.py` 与旧 `StrategyConfig` 投影兼容层，测试侧直接消费 `TestStrategySpec`。
9. `strategy_searcher` 拆分为参数解析/执行序列化/输出落盘三个模块，主入口保持薄 orchestrator。

## 范围
本任务仅处理：
1. `py_entry/strategy_hub/core/`
2. `py_entry/strategy_hub/search_spaces/`
3. `py_entry/strategy_hub/test_strategies/`
4. `py_entry/strategy_hub/registry/`
5. `py_entry/strategy_hub/demo.ipynb`

说明：`scanner` 不在本任务范围。

## 三类类型（核心）

### 1) 公共策略类型（最小交集）
定义 `CommonStrategySpec`，只保留执行必需字段：
1. `name`
2. `version`
3. `data_config`
4. `variant`

`variant` 只保留执行参数：
1. `indicators_params`
2. `signal_params`
3. `backtest_params`
4. `signal_template`

说明：
1. 一个策略文件只表达一个策略。
2. 公共执行协议只认策略级 `name`。
3. 本次不引入“单文件多变体”执行能力。
4. 策略变体（如“带止损/不带止损”）通过同一子文件夹下的多个独立策略文件表达。

### 2) 搜索空间类型
`SearchSpaceSpec(CommonStrategySpec)` 扩展字段：
1. `research`（`opt_cfg/sens_cfg/wf_cfg`）
2. 搜索元信息（`source`）

### 3) 测试策略类型
`TestStrategySpec(CommonStrategySpec)` 扩展字段：
1. 可选 `research`
2. `btp_strategy_class`
3. `custom_params`
4. `chart_layout`
5. 测试元信息（如 `test_group`）

约束：
1. 两个子类必须继承公共类型。
2. 执行链路默认只依赖公共字段。
3. 扩展字段只在对应场景读取。

## 类型选型
1. 协议类型（`CommonStrategySpec`/`SearchSpaceSpec`/`TestStrategySpec`）使用 `dataclass(frozen=True)`。
2. 外部输入边界（注册器 JSON、日志 JSON）使用 Pydantic 做结构校验。
3. 运行时覆盖（symbol/params）只在 Runtime 对象进行，不回写 Spec。

## 统一模块入口
所有策略模块统一只导出：

`build_strategy_bundle()`

返回：
1. search 模块返回 `SearchSpaceSpec`
2. test 模块返回 `TestStrategySpec`

禁止旧入口并存：
1. `get_config`
2. `get_live_config`
3. `build_search_space`
4. `@register_strategy`

## 策略文件组织约束（新增）
1. 每个策略子目录必须有且仅有一个 `common.py` 作为公共构建入口。
2. 同目录下的各策略文件（含变体）只能从 `common.py` 派生，不允许各自重复拼装完整参数树。
3. `common.py` 负责放置公共指标、信号模板、回测参数骨架与研究配置，变体文件只传入差异化参数。
4. `search_spaces` 强制执行该约束；`test_strategies` 推荐采用同格式，但允许为测试最小样例做简化。
5. 研究配置默认口径：`common.py` 必须直接使用全局 `build_opt_cfg/build_sens_cfg/build_wf_cfg`，非必要不做策略级覆盖。
6. 仅在极少数明确需求下允许覆盖，且覆盖必须在 `common.py` 层集中表达，不允许散落到派生策略文件。

## 策略域与 live 域分层

### 策略域（策略文件）
策略文件只放策略定义与研究定义，禁止 live 字段。

### live 域（注册器 JSON）
live 只在注册器里定义，不进入策略类型。

注册器保留字段：
1. `log_path`
2. `symbol`
3. `mode`
4. `enabled`
5. `position_size_pct`
6. `leverage`

注册器删除字段：
1. `strategy_name`
2. `param_source`

## 注册器语义更新
1. 策略识别由 `log_path` 对应日志条目给出。
2. 参数来源不再手填，按 `mode` 固定：
   - `backtest` -> `backtest_default_params` + `backtest_start_time_ms`
   - `walk_forward` -> `last_window_best_params` + `last_window_start_time_ms`
3. 预检时校验日志文件只包含单一 `strategy_name`，不满足直接报错终止。
4. 机器人启用项强约束：同一 `symbol` 只能有一个 `enabled=true` 的策略条目。
5. 机器人启动阶段只校验“已注册且 enabled 的策略条目”内的 `strategy_name` 唯一性，不再扫描仓库全量策略名。
6. 机器人运行阶段只消费已注册策略（启动时装载到内存映射），循环中不做全量策略扫描。

## 调用链统一
1. `just workflow`：统一协议执行。
2. `demo.ipynb`：同一入口运行 test/search。
3. `registry`：只读日志与 live 控制字段。
4. `just workflow` 启动时继续扫描全量 `search/test` 策略，并执行全局策略名重复与加载合法性校验。

## Just 命令调用方式（灵活可组合）
1. 主入口唯一：`just workflow ...`（参数透传到搜索器）
2. `strategies` 与 `symbols` 都必须显式指定，不做隐式默认。
3. `strategies` 与 `modes` 都支持逗号组合；执行顺序按传入顺序串行执行。
4. `modes` 支持：
   - `backtest`
   - `optimize`
   - `sensitivity`
   - `walk_forward`
5. `--mode` 的顺序语义强约束：
   - `--mode backtest,walk_forward` 先执行 `backtest`，再执行 `walk_forward`。
   - `--mode walk_forward,backtest` 先执行 `walk_forward`，再执行 `backtest`。
   - 控制台输出按该顺序逐段打印。
   - 日志 `results` 也按该顺序依次追加与保存（多模式时合并到同一日志文件）。
   - 若 `mode` 重复出现，直接报错并终止执行（不做自动去重）。
6. 策略名支持短名与完整模块名：
   - 短名示例：`sma_2tf`、`sma_2tf_sl`
   - 完整模块名示例：`sma_2tf.sma_2tf_tsl`
   - 短名与完整模块名都必须唯一；出现重复时启动阶段直接报错并终止。
   - 支持子目录通配语法糖：`sma_2tf.*`（表示 `sma_2tf` 子目录下全部策略）。
   - 支持全量语法糖：`*`（表示扫描全部 `search_spaces` 策略）。

示例：
```bash
# 单策略 + 单品种 + 回测+向前测试
just workflow --strategies sma_2tf --symbols BTC/USDT --mode backtest,walk_forward

# 单策略 + 多品种 + 回测+向前测试
just workflow --strategies sma_2tf --symbols BTC/USDT,ETH/USDT --mode backtest,walk_forward

# 单品种 + 多策略 + 回测+向前测试
just workflow --strategies sma_2tf,sma_2tf_sl --symbols BTC/USDT --mode backtest,walk_forward

# 子目录全策略（语法糖）
just workflow --strategies sma_2tf.* --symbols BTC/USDT --mode backtest,walk_forward

# 全部搜索空间策略（语法糖）
just workflow --strategies '*' --symbols BTC/USDT --mode backtest,walk_forward
```
说明：不支持“多策略 + 多品种”同时混合执行。

## 日志口径（更新）
1. 强约束：一个命令只生成一个日志文件，不允许一个命令写多个日志文件。
2. 默认不传 `--output` 时按拓扑落盘：
   - 单策略（单/多品种）：写入该策略子目录 `logs/`。
   - 单品种多策略：写入 `py_entry/strategy_hub/search_spaces/logs/<symbol>/`。
3. 示例结构：
   - `search_spaces/sma_2tf/sma_2tf.py`
   - `search_spaces/sma_2tf/sma_2tf_tsl.py`
   - `search_spaces/sma_2tf/sma_2tf_sl.py`
   - `search_spaces/sma_2tf/logs/`
4. 文件名：`UTC ISO秒级时间(冒号替换为下划线)_后缀.json`。
   - 单策略场景后缀为 `strategy_name`。
   - 单品种多策略场景后缀为命令参数哈希值。
5. 同名冲突：延迟 1 秒重试 3 次，失败报错建议重跑。
6. 保留部署参数与窗口时间元信息。
7. 旧日志系统全面下线：不再使用 `=== RESEARCH_PIPELINE_RESULT ===` 或 `key=value` 多行拼接输出。
8. 控制台阶段输出统一 JSON 风格，`backtest/optimize/sensitivity/walk_forward` 统一输出 `performance` 主体字段；不再在 Python 侧派生第二套统计口径。
9. 旧前缀形式（如 `backtest.brief=` / `walk_forward.detailed=`）全部下线，统一直接打印标准 JSON 对象（包含 `stage`，不再保留 `level` 分级字段）。
10. 旧结果日志接口 `LogLevel + result.log(...)` 全面下线，统一使用单一接口 `result.print_report()`（可配套 `build_report()` 获取结构化对象）。
11. `.gitignore` 需保留 `py_entry/strategy_hub/search_spaces/logs/` 目录（提交 `.gitkeep`），并忽略该目录下日志内容。

## 本轮已落地补充
1. `search_spaces/*/common.py` 已统一到“默认全局研究配置”写法：`opt_cfg=build_opt_cfg()`、`sens_cfg=build_sens_cfg()`、`wf_cfg=build_wf_cfg()`。
2. `sma_2tf` 及其变体已改为同口径，并在研究配置处明确注释“优化用全局配置，非必要不覆盖”。
3. `runner` 旧分级日志结构已清理完成：删除 `LogLevel` 与 `.log(...)`，统一为 `build_report()/print_report()` 单一路径。
4. `spec_loader` 模块发现缓存已移除，`discover_modules` 每次按当前文件系统实时扫描，避免缓存状态与代码状态偏离。

## 验收标准
1. 三类类型落地：`CommonStrategySpec`、`SearchSpaceSpec`、`TestStrategySpec`。
2. 公共类型字段为 `name/version/data_config/variant`，无 `variants`、无 `variant_name`。
3. 策略域不包含 live 字段。
4. 注册器不包含 `strategy_name/param_source`。
5. `test_strategies` 与 `search_spaces` 统一 `build_strategy_bundle()`。
6. 机器人注册预检能拦截“同 symbol 多启用策略”冲突。
7. `just workflow`、`demo`、registry 可用且行为不降级。

## 非目标
1. 不处理 scanner 策略体系。
2. 不保留长期兼容层。
3. 不引入与本任务无关的新命令语义。
