# TODO: 参数依赖统一方案（Param 枚举化）

> 关联文档：`doc/todo/TODO_signal_text_dsl.md`
>
> 这两篇文档理论上属于同一个任务的两个子议题：
>
> * 参数系统升级
> * Signal 模板 DSL 升级
>
> 两者不应割裂设计，原因是：
>
> * 参数依赖 DSL 需要数值表达式 parser
> * Signal 文本 DSL 也需要数值表达式 parser
> * 更合理的方案是共享底层 numeric expression parser，而不是各写一套
>
> 因此，阅读和执行时应将两篇文档视为同一任务下的关联设计。

本文档描述一套面向当前项目的参数依赖设计方案。目标不是发明一个通用参数图系统，而是在不污染回测引擎的前提下，为 **Rust 优化器** 和 **WF 预热计算** 提供一套统一、优雅、可落地的参数依赖表达方式。

这套方案的核心结论是：

*   **不要额外引入 `ParamPlan` 或第二套参数图配置。**
*   **不要让回测引擎理解参数依赖。**
*   **直接把 `Param` 升级为“声明型参数枚举”，并且解析权必须完全收敛到 Rust。**

也就是说，策略作者仍然只维护一份参数定义树；依赖关系就写在 `Param` 里面。运行前、优化中、WF 预热前，由 **Rust** 把这棵声明树解析成最终的 `.value` 参数树，再交给回测引擎执行。Python 只负责构造和传递声明，不负责解释 `Param`。

---

## 1. 设计目标

本方案只解决以下问题：

*   支持参数之间的顺序依赖。
*   支持动态搜索边界。
*   支持派生参数。
*   让 Rust 优化器能够理解参数依赖。
*   让 WF 预热计算能够按依赖关系求“最坏参数集”。

本方案明确 **不** 解决以下问题：

*   不做任意 DAG 配置编辑器。
*   不做独立的 `ParamPlan` 第二套维护结构。
*   不让回测引擎直接消费依赖表达式。
*   不要求 Optuna 完整支持参数依赖。

换句话说，当前约束非常明确：

*   **回测引擎只关心 `.value`**
*   **Rust 优化器关心依赖**
*   **WF 预热关心依赖**
*   **Optuna 可以暂时不关心依赖**
*   **Python 不参与 `Param` 解析**

这个边界和项目当前用法是吻合的。

---

## 2. 为什么不采用 `ParamPlan + Param`

`ParamPlan + Param` 的问题不是不能实现，而是会让策略作者维护两份东西：

*   一份是 `Param`
*   一份是依赖关系计划

这会直接带来几个问题：

*   参数定义和依赖定义分离，容易漂移。
*   审阅时需要同时看两套结构，心智负担变大。
*   框架内部会出现“哪一份才是真值”的问题。
*   很多简单依赖关系被拆成两处配置，写起来不自然。

因此，本项目更适合采用 **单一真值源**：

*   所有参数语义都收敛到 `Param`
*   依赖关系也属于 `Param` 的一部分
*   框架内部只负责解析，不要求用户维护第二套对象

---

## 3. 核心方案：把 `Param` 升级为声明型枚举

### 3.1 总体思路

外部 API 仍然统一叫 `Param`，但内部不再只是“一个带 `value/min/max` 的普通结构体”，而是一个声明型枚举。

建议语义上分成三类：

1.  `Fixed`
2.  `Search`
3.  `Derived`

其中：

*   `Fixed` 表示固定值
*   `Search` 表示可优化参数
*   `Derived` 表示由别的参数推导得到的参数

这三类已经足够覆盖当前需要的主要场景。

### 3.2 建议的数据模型

下面是概念模型，不要求一字不差照抄实现细节，但语义应保持一致。

```rust
enum ParamDef {
    Fixed {
        value: f64,
        dtype: ParamType,
    },
    Search {
        default: f64,
        min: Expr,
        max: Expr,
        step: f64,
        dtype: ParamType,
        log_scale: bool,
    },
    Derived {
        expr: Expr,
        dtype: ParamType,
    },
}
```

这里的重点是：

*   `Search` 持有的是 **搜索定义**
*   `Derived` 持有的是 **计算表达式**
*   它们都不是运行时最终值

---

## 4. 为什么 `Search` 不应直接带 `value`

这是本方案最关键的取舍之一。

`Search` 表面上看似乎应该带一个 `value` 字段，方便优化器不断修改它；但实际上这样会把三种不同语义混在一起：

*   默认值
*   当前 trial 的采样值
*   最终最优值

一旦把这三者都塞进同一个 `value` 字段，会出现几个问题：

*   参数定义对象带状态，语义变脏。
*   并行优化时，容易让“参数定义”和“本次试验结果”纠缠在一起。
*   `run()`、`optimize()`、`walk_forward()` 三种模式下，`value` 的含义不一致。
*   结果导出时，到底导出的是定义还是本次运行结果，会变得模糊。

因此，这里应该明确分层：

*   `ParamDef` 负责描述参数
*   `ResolvedParam` 负责承载本次运行的最终值

建议内部有一个运行态结果结构：

```rust
struct ResolvedParam {
    value: f64,
    dtype: ParamType,
}
```

也就是说：

*   用户维护的是声明型 `Param`
*   框架解析后得到 `ResolvedParam.value`
*   回测引擎永远只读取解析后的 `.value`

这是最干净的边界。

---

## 5. 表达式系统：采用字符串 DSL，并由 Rust 解析

为了支持依赖关系，`Search.min/max` 和 `Derived.expr` 需要引用别的参数。

结合项目现有 signal 模板的实际风格，本方案更适合采用：

*   **字符串表达式**
*   **Rust 解析**

而不是：

*   Python lambda
*   Python 端 AST builder
*   `ref(...)` 这种程序化拼接写法

原因很直接：

*   当前 signal 模板本来就是字符串 DSL，由 Rust 解析。
*   参数依赖如果继续用 `ref(...)` 风格，会和现有模板风格分叉。
*   让策略作者继续写“模板字符串”，更符合当前项目的使用习惯。

因此，这里推荐增加一个独立的 **参数表达式 DSL**。

它的语法风格应借鉴 signal parser，但不直接复用 signal condition parser。

### 5.1 建议支持的表达式节点

建议 DSL 支持以下最小能力：

*   数值字面量：`20`、`0.5`
*   参数引用：`$signal.rsi_mid`
*   四则运算：`+ - * /`
*   括号：`(...)`
*   常用函数：`floor()`、`ceil()`、`round()`、`min()`、`max()`、`clamp()`

也就是说，表达式例如：

*   `$indicators.ohlcv_30m.sma_slow.period - 1`
*   `floor($indicators.ohlcv_30m.sma_slow.period * $signal.false_ratio)`
*   `$signal.rsi_mid - $signal.rsi_lower_gap`
*   `($signal.rsi_mid + $signal.rsi_upper_gap) / 2`
*   `floor(($backtest.atr_period + $signal.window) / 2)`

这个集合已经足够覆盖绝大多数参数依赖需求。

这里还必须明确一条硬约束：

*   **四则运算必须支持递归嵌套**
*   **`()` 必须支持显式优先级控制**

也就是说，numeric expression parser 不能只支持一层线性运算，而必须至少支持：

*   `a + b * c`
*   `(a + b) * c`
*   `(a + (b * c)) / d`
*   `floor((a + b) / 2)`

原因很简单：

*   这是量化交易策略里的高频真实场景
*   均值、比例、归一化、价差、窗口平滑等写法都会反复用到
*   如果不支持递归嵌套，只会逼用户拆出大量低价值中间变量
*   最终既不优雅，也会让模板变脏

### 5.2 不建议继续扩展的东西

以下能力短期内不建议支持：

*   任意布尔表达式
*   条件分支表达式
*   自定义函数回调
*   动态遍历其他参数集合
*   任意 Python 语法

原因很简单：一旦表达式系统过强，策略层会很快失控，最后变成半个脚本语言。

---

## 6. 参数引用路径设计

参数依赖必须能稳定引用别的参数，因此需要统一路径规范。

建议路径使用当前参数树的业务路径，并直接写在字符串表达式里：

*   `$indicators.ohlcv_30m.sma_slow.period`
*   `$indicators.ohlcv_4h.macd_htf.fast_period`
*   `$signal.rsi_oversold`
*   `$backtest.atr_period`

这个路径体系有几个好处：

*   可读性高，和当前搜索空间定义方式自然对应。
*   不需要额外生成内部 alias。
*   审阅时能直接看出依赖关系。
*   框架内部可直接映射到 `SingleParamSet`。

要求写死：

*   路径必须唯一
*   路径解析失败直接报错
*   不允许模糊匹配

---

## 7. 参数依赖的求值顺序

### 7.1 必须采用“声明顺序优先”

虽然内部也可以做依赖图和拓扑排序，但对外约束应尽量简单：

*   **参数只能引用已经在前面定义过的参数**
*   **禁止前向引用**

这样带来的好处非常大：

*   策略作者更容易理解
*   大多数参数关系天然就是“先慢后快、先中心后边界、先尺度后派生”
*   内部仍可做环检测，但绝大多数情况下不会触发复杂路径

对于项目当前典型场景，这种“有序参数声明”完全足够。

### 7.2 框架内部仍应保留校验

即使要求只能引用前面的参数，框架内部仍然要做：

*   未定义引用检查
*   循环依赖检查
*   类型检查
*   除零等非法表达式检查

一旦发现错误，应直接 fail-fast，不做兜底。

---

## 8. 三种运行模式下的解析方式

同一棵 `Param` 声明树，在不同场景下会用不同模式解析。

建议统一提供三种解析模式：

1.  `run_default`
2.  `optimize_trial`
3.  `warmup_worst_case`

### 8.1 `run_default`

用于普通回测和默认执行。

规则：

*   `Fixed` 直接取 `value`
*   `Search` 取 `default`
*   `Derived` 用当前上下文计算

最终得到一棵纯 `.value` 参数树，交给回测引擎。

### 8.2 `optimize_trial`

用于 Rust 优化器。

规则：

*   `Fixed` 直接取固定值
*   `Search` 先根据上下文解析出动态 `min/max`，再采样
*   `Derived` 在上游值确定后直接计算

每得到一个参数的最终值，就写入当前 trial 上下文，供后续参数继续引用。

### 8.3 `warmup_worst_case`

用于 WF 预热与指标契约相关的最坏情况估计。

规则：

*   `Fixed` 直接取固定值
*   `Search` 不做采样，而是取“对 warmup 更坏的值”
*   `Derived` 按当前最坏上下文继续计算

这里的核心不是“简单取 `max`”，而是：

*   先按依赖关系解析出动态边界
*   再按 warmup 语义选取最坏值

这比当前简单地“`optimize=True` 就取 `max`”更正确。

---

## 9. WF 预热口径

当前 WF 预热的一个问题是，它默认把可优化参数直接按 `max` 来看待。这个逻辑在没有依赖时是简化成立的，但一旦引入依赖参数，就不够用了。

例如：

*   `sma_slow.period` 是 `Search`
*   `sma_fast.period.max = sma_slow.period - 1`
*   `sma_false_length = floor(sma_slow.period * false_ratio)`

此时如果只机械地对每个参数单独取 `max`，会出几个问题：

*   某些动态上界本身依赖别的参数，无法先验确定。
*   某些派生参数的“最大值”不是静态给定的，而是运行时算出来的。
*   某些参数对 warmup 的最坏情况未必总是简单的固定 `max`。

因此，WF 应复用和优化器相同的参数解析器，只是使用不同模式：

*   优化器模式：采样
*   WF 模式：求最坏值

这才是长期正确的统一口径。

---

## 10. 回测引擎边界：只看最终 `.value`

这个边界必须明确写死。

回测引擎不应该知道：

*   `Fixed`
*   `Search`
*   `Derived`
*   `Expr`
*   动态边界
*   参数依赖

回测引擎只应该接收：

*   一棵已经解析完毕的普通参数树
*   每个参数最终都有 `.value`

也就是说，回测引擎的输入仍然应等价于今天的 `SingleParamSet<Param(value)>`。

参数依赖属于：

*   参数定义层
*   优化层
*   WF 预热层

而不是回测执行层。

---

## 11. Optuna 的处理原则

由于 Optuna 只是备胎，本方案不要求它完整支持参数依赖。

建议规则非常直接：

*   Optuna 只支持没有依赖的 `Fixed/Search`
*   一旦发现 `Search.min/max` 使用了动态引用，或者出现 `Derived` 被下游引用为采样边界，直接报错

这样做有几个好处：

*   实现简单
*   不会污染主链路
*   不需要为了备胎方案强行把系统做复杂

以后如果真的有需要，再给 Optuna 补支持也不迟。

---

## 12. 典型场景写法示例

### 12.1 慢线先定，快线受慢线约束

目标：

*   先优化 `sma_slow`
*   再把 `sma_slow - 1` 作为 `sma_fast` 的动态上界

示意：

```python
indicators = {
    "ohlcv_30m": {
        "sma_slow": {
            "period": Param.search(
                default=60,
                min="20",
                max="200",
                step=1,
                dtype=ParamType.Integer,
            ),
        },
        "sma_fast": {
            "period": Param.search(
                default=20,
                min="2",
                max="$indicators.ohlcv_30m.sma_slow.period - 1",
                step=1,
                dtype=ParamType.Integer,
            ),
        },
    }
}
```

### 12.2 比例派生长度

目标：

*   `false_ratio` 参与优化
*   `sma_false_length = floor(sma_slow * false_ratio)`

示意：

```python
signal_params = {
    "false_ratio": Param.search(
        default=0.5,
        min="0.2",
        max="0.8",
        step=0.05,
    ),
    "sma_false_length": Param.derived(
        expr="floor($indicators.ohlcv_30m.sma_slow.period * $signal.false_ratio)",
        dtype=ParamType.Integer,
    ),
}
```

### 12.3 RSI 三线顺序约束

比起分别独立优化 `oversold / mid / overbought`，更推荐采用“中心线 + 双边距离”的写法。

目标：

*   保证 `oversold < mid < overbought`
*   避免三条线独立优化后出现顺序错乱

示意：

```python
signal_params = {
    "rsi_mid": Param.search(
        default=50,
        min="45",
        max="55",
        step=1,
    ),
    "rsi_lower_gap": Param.search(
        default=20,
        min="5",
        max="25",
        step=1,
    ),
    "rsi_upper_gap": Param.search(
        default=20,
        min="5",
        max="25",
        step=1,
    ),
    "rsi_oversold": Param.derived(
        expr="$signal.rsi_mid - $signal.rsi_lower_gap",
        dtype=ParamType.Integer,
    ),
    "rsi_overbought": Param.derived(
        expr="$signal.rsi_mid + $signal.rsi_upper_gap",
        dtype=ParamType.Integer,
    ),
}
```

这种写法比直接给三条阈值线各自独立设范围更稳。

---

## 13. 常见参数依赖模式

当前项目中最常见、也最值得内建支持的依赖模式主要有以下几类。

### 13.1 有序对

典型形式：

*   `fast < slow`
*   `short_window < long_window`

用途：

*   SMA / EMA / MACD 快慢线
*   双窗口波动率
*   短期/长期滤波

### 13.2 中心线与上下边界

典型形式：

*   `lower = center - gap`
*   `upper = center + gap`

用途：

*   RSI 阈值
*   CCI 阈值
*   任意振荡指标的中轴与双边阈值

### 13.3 比例派生

典型形式：

*   `child = parent * ratio`

用途：

*   假突破长度
*   回看窗口比例
*   某些平滑长度或过滤长度

### 13.4 风报比派生

典型形式：

*   `tp = sl * rr_ratio`

用途：

*   风险收益比统一建模
*   让止损和止盈之间保持清晰约束

### 13.5 多周期单调关系

典型形式：

*   `base_period <= htf_period <= vhtf_period`

用途：

*   多周期趋势过滤
*   多周期 MACD / RSI / EMA 结构

---

## 14. 建议的对外 API 风格

对外 API 应尽量保持和现在 `Param(...)` 的使用习惯接近，不要突然引入一整套新 DSL。

建议保留这种风格：

```python
Param.fixed(...)
Param.search(...)
Param.derived(...)
```

目标是：

*   一眼就能看懂
*   不需要学习一套独立脚本语言
*   不会让 search space 文件显著变脏
*   和 signal 模板的字符串风格保持一致

这里要特别强调：

*   参数依赖 DSL **借鉴** signal 模板的写法
*   但它应当是一个 **独立的参数表达式解析器**
*   不直接复用现有 signal condition parser

原因是两者语义不同：

*   signal parser 解析的是比较条件
*   param expr parser 解析的是数值表达式

### 14.1 应该复用什么，不应该复用什么

这里要把“复用”说清楚，避免后面实现时再次摇摆。

#### 应该复用的部分

参数表达式 DSL 和 signal 模板 DSL 应该复用的是 **底层解析积木**，例如：

*   `nom` 解析库本身
*   空白处理
*   数字字面量解析
*   标识符解析
*   `$...` 引用前缀解析
*   括号、逗号、函数名等基础 token 解析
*   通用错误包装与报错风格

也就是说，应该抽出共享的 lexer / parser primitive，让两套 DSL 都站在同一套底层解析组件上。

#### 不应该复用的部分

不应该直接复用的是 signal condition parser 的 **上层 grammar 和 AST**，例如：

*   `SignalCondition`
*   `LeftOperand Op RightOperand`
*   `x>`、`x<`、`in`、`xin`
*   `..` 区间语义
*   data operand 的 source / offset 语义
*   signal condition 专属的校验逻辑

原因很简单：

*   signal parser 解析的是“比较条件”
*   param expr parser 解析的是“数值表达式”

它们虽然都用字符串模板，也都可以用同一套底层解析工具，但：

*   grammar 不一样
*   AST 不一样
*   resolver 不一样

因此，正确做法是：

*   **复用 parser primitive**
*   **分离上层 grammar**
*   **分离 AST**
*   **分离 resolver**

一句话概括：

*   **复用解析组件，不复用 signal 条件语法本体。**

---

## 15. 框架内部的落地分层

### 15.1 Python 层职责

Python 层负责：

*   构建声明型 `Param`
*   组织 `SearchSpaceSpec`
*   把参数树传给 Rust

Python 层不负责：

*   解析 `Param`
*   解释依赖关系
*   拓扑求值
*   优化时动态采样
*   warmup 极值求解

这一条必须写死：

*   **Python 只能组装声明，不能解释声明**

否则后面一定会出现：

*   Python 解析一套
*   Rust 解析一套

然后两边口径逐渐漂移。

### 15.2 Rust 层职责

Rust 层负责：

*   校验参数引用合法性
*   解析 `Param`
*   解析表达式
*   在不同模式下生成最终 `.value`
*   供优化器与 WF 共用一套解析逻辑

Rust 层是参数依赖的唯一解释器。

这里的“唯一解释器”不是建议，而是硬约束：

*   `Param` 的业务语义只能在 Rust 中落地
*   Python 不允许出现平行解析实现

### 15.3 解析发生位置：每个模块入口一开始就 resolve

参数解析不应该散落在执行链路的中间，也不应该等到某个具体子阶段再临时解释。

正确规则是：

*   **每个消费参数的 Rust 模块，都在自己的入口函数起始处先做 resolve**
*   **模块内部后续逻辑一律只接收 resolved 参数**

也就是说，解析层和执行层之间必须有一道明确边界：

*   入口层负责把声明型参数转换成具体值参数
*   内部执行层负责消费具体值参数

这个规则适用于：

*   单次回测入口
*   批量回测入口
*   优化器入口
*   walk-forward 入口
*   指标契约 / warmup 预检入口

换句话说，不是只有某一个全局总入口 resolve 一次就结束，而是：

*   **谁的模块入口接收了声明型参数，谁就先 resolve**

这样做的好处是：

*   模块边界清晰
*   内部逻辑不需要感知 `Search / Derived / Expr`
*   每个模块可以根据自身语义选择 resolve 模式
*   不会出现执行到一半才发现参数还没物化的脏情况

### 15.4 三类典型入口的 resolve 模式

不同模块入口虽然都要先 resolve，但使用的模式不一样。

#### 回测入口

回测入口在函数开始处直接：

*   `resolve_for_run`

得到默认 concrete 参数，再把它交给后续 indicator / signal / backtest / performance 执行链路。

#### 优化器入口

优化器入口在函数开始处不应该先把整棵树直接解析成固定值，否则就失去搜索空间了。

优化器入口应当：

*   接收声明型参数树
*   在每个 trial 内部调用 `resolve_for_trial`
*   为当前 trial 生成 concrete 参数
*   再把 concrete 参数交给评估回测

所以优化器模块的“入口 resolve”本质上是：

*   入口先接管声明型参数
*   后续每轮 trial 在本模块内部最前面 resolve

也就是：**优化器内部允许持有声明型参数树，但真正评估前必须先 resolve。**

#### WF / 预热入口

WF 和指标契约相关逻辑在入口开始处应先：

*   `resolve_for_warmup`

得到最坏情况 concrete 参数，用它来计算：

*   指标契约
*   warmup bars
*   transition 约束

真正进入窗口训练时，优化部分再走优化器自己的 trial resolve 逻辑。

### 15.5 内部执行函数禁止再碰声明型 Param

一旦经过入口 resolve，后面的内部执行函数就不应该再理解声明型参数。

这条约束必须明确：

*   `execute_single_backtest` 这类纯执行核心只接收 resolved 参数
*   指标计算模块只接收 resolved 参数
*   信号模块只接收 resolved 参数
*   风控与绩效模块只接收 resolved 参数

如果某个内部函数还需要判断：

*   这是 `Fixed` 还是 `Search`
*   这里要不要解析 `Expr`

那就说明边界放错了。

这符合项目当前的一贯原则：

*   关键执行语义尽量收敛到 Rust
*   外层语言主要负责组织配置

---

## 16. 与现有代码的关系

当前代码里，优化器默认把所有 `optimize=True` 参数平铺后独立采样；WF 预检则会简单地把可优化参数按 `max` 处理。

这在没有依赖参数时可以工作，但在以下场景会失效：

*   `fast.max = slow - 1`
*   `derived = slow * ratio`
*   `oversold / mid / overbought` 需要保持顺序关系

因此，本方案的改造方向应是：

*   用声明型 `Param` 取代今天的纯值型 `Param`
*   在 Rust 中增加统一的参数解析器
*   优化器和 WF 共同复用这套解析器
*   回测引擎仍然只吃已解析的值

这样是局部破坏性更新，但整体代码品味更好，也符合项目“不保留脏兼容层”的原则。

---

## 17. 最终结论

本任务的推荐方案如下：

*   **不采用 `ParamPlan + Param` 双结构**
*   **直接把 `Param` 升级为声明型枚举**
*   **语义上保留 `Fixed / Search / Derived` 三类**
*   **通过一个极简 `Expr` 子集支持参数引用和派生**
*   **Rust 负责参数依赖解析**
*   **WF 复用同一套解析器求最坏值**
*   **回测引擎继续只消费最终 `.value`**
*   **Optuna 暂时不完整支持参数依赖，直接限制能力范围**

这套方案的优点是：

*   单一真值源，用户只维护一份参数定义
*   依赖关系表达自然
*   Rust 优化器和 WF 口径统一
*   回测引擎边界清晰，不被污染
*   整体复杂度明显低于“额外维护参数图”的方案

这就是当前项目最适合的参数依赖设计方向。
