## 输入数据要求

* **ohlcv DataFrame**
  - 必须包含列名：`time`, `open`, `high`, `low`, `close`, `volume`
  - 若任一列名缺失 → 直接报错
  - **只读**：回测过程中不写入，尽量避免 `clone`
  - 若出现 `NaN` → 直接报错

* **signal DataFrame**
  - 必须包含布尔列：`enter_long`, `exit_long`, `enter_short`, `exit_short`
  - 若任一列名缺失 → 直接报错
  - **只读**：不写入，尽量避免 `clone`
  - 若出现 `NaN` → 直接报错
  - 为了提高性能, 方便处理, 用polars的方法转换成整数列

* **skip_mask Series**
  - 类型为布尔 `Series`
  - **只读**：不写入，尽量避免 `clone`
  - 若出现 `NaN` → 直接报错

---

## 参数获取（BacktestParams）

- 参数从 `BacktestParams` 结构体获取，**无默认值，强制用户显式传入**
- 所有 `Param<T>` 类型参数通过 `.value` 访问

### 1. 百分比止损/止盈/跟踪止损
- `sl_pct`, `tp_pct`, `tsl_pct`：`Param<f64>`，相对于**进场价**的百分比
  - 若 `value <= 0` → 不启用该机制，且**不返回对应结果列**
  - 多头示例：
    * pct固定止损(多头)：`止损价 = 进场价 × (1 - sl_pct)`
    * pct固定止损(空头)：`止损价 = 进场价 × (1 + sl_pct)`
    * pct固定止盈(多头)：`止盈价 = 进场价 × (1 + tp_pct)`
    * pct固定止盈(空头)：`止盈价 = 进场价 × (1 - tp_pct)`
    * pct初始跟踪止损(多头)：`止损价 = 进场价 × (1 - sl_pct)`
    * pct初始跟踪止损(空头)：`止损价 = 进场价 × (1 + sl_pct)`
    * pct更新跟踪止损(多头)：`更新止损价 = max(上一个跟踪止损价,锚定高点 × (1 - tsl_pct))`
    * pct更新跟踪止损(空头)：`更新止损价 = min(上一个跟踪止损价,锚定低点 × (1 + tsl_pct))`

### 2. ATR 止损/止盈/跟踪止损
- `sl_atr`, `tp_atr`, `tsl_atr`：`Param<f64>`，ATR 倍数
- `atr_period`：`Param<i64>`，ATR 计算周期
  - 若任一 `value <= 0` → 不启用，且**不返回对应结果列**
  - 多头示例：
    * atr固定止损(多头)：`止损价 = 进场价 - ATR × sl_atr`
    * atr固定止损(空头)：`止损价 = 进场价 + ATR × sl_atr`
    * atr固定止盈(多头)：`止盈价 = 进场价 + ATR × tp_atr`
    * atr固定止盈(空头)：`止盈价 = 进场价 - ATR × tp_atr`
    * atr初始跟踪止损(多头)：`初始止损价 = 进场价 - ATR × tsl_atr`
    * atr初始跟踪止损(空头)：`初始止损价 = 进场价 + ATR × tsl_atr`
    * atr更新跟踪止损(多头)：`更新止损价 = max(上一个跟踪止损价, 锚定高点 - ATR × tsl_atr)`
    * atr更新跟踪止损(空头)：`更新止损价 = min(上一个跟踪止损价, 锚定低点 + ATR × tsl_atr)`

### 3. 跟踪止损行为控制
- `tsl_use_high`: `bool`
  - `true` → 以当前 bar 的 `high`/`low` 为锚点更新止损价, 并且以 `high`/`low` 为触发离场价格判断
  - `false` → 以当前 bar 的 `close` 为锚点更新止损价, 并且以 `close` 为触发离场价格判断
  - **同时影响 `tsl_pct` 和 `tsl_atr`**
- `tsl_per_bar_update`: `bool`
  - `true` → 每根 bar 都更新 TSL
  - `false` → 仅在突破**进场之后持仓以来最高/最低点**时更新
  - **同时影响 `tsl_pct` 和 `tsl_atr`**
    - tsl_per_bar_update=true
      - 新高之后的横盘, tsl_atr会上升, tsl_pct不变
    - tsl_per_bar_update=false
      - 新高之后的横盘, tsl_atr不变, tsl_pct不变
    - 虽然影响不到tsl_pct, 但是为了统一处理, 就都影响吧


### 4. 离场执行模式
- `exit_in_bar`: `bool`
  - `true` → SL/TP 在**当前 bar 触发并结算**（in_bar 模式）
    - 结算价格就是SL/TP计算的止损点
  - `false` → SL/TP 在**下一 bar 开盘价结算**（next_bar 模式）
  - **仅影响 SL/TP，不影响 TSL**
  - **`enter_long` `enter_short` 进场始终为 next_bar 模式（开盘价进场）**
  - **`exit_long` `exit_short`离场始终为 next_bar 模式（开盘价离场）**

### 补充, 仓位和结算:
  - 仓位信号, 永远在当下判断, 用当下bar的价格去和止盈止损比较
    - 如果是in_bar, 就用当下bar的最高或最低价和止盈止损价比较
    - 如果是next_bar, 就用当下bar的收盘价和止盈止损价格比较
  - 结算时机, 仓位信号只是标注仓位状态, 跟结算无关
    - 如果是当前仓位信号是离场信号, 并且离场模式是in_bar, 就在当下bar结算, 结算价就是实际止盈止损价
    - 如果是当前仓位信号是离场信号, 如果离场模式是next_bar, 就在下一根bar开盘价结算
  - 反手并不是特例, 依然遵循这个模式, 跟普通进场和离场遵循一样的逻辑
    - 把反手分成散布, 1. 进场前, 先把已有仓位平仓 2. 开仓一个反向仓位 3. 反向仓位最后也触发离场
    - 1. 平仓已有仓位, 就是在当下bar判断信号, 然后根据离场模式, 判断结算时机
      - 跟其他离场模式一样的
    - 2. 开仓一个反向仓位, 就是在当下bar判断信号, 然后在下一个bar开盘价进场
      - 跟其他进场模式一样的
    - 3. 反向仓位最后也触发离场, 就是在当下bar判断信号, 然后根据离场模式, 判断结算时机
      - 跟其他离场模式一样的

### 特殊案例:
  - 1,2,3,4代表索引
  - 仓位状态: 1. 进多 2. 平多进空 3. 平空进多, 4. 平多
  - 离场模式: 1. 不离场 2. next_bar离场 3. in_bar离场 4. in_bar离场
  - 结算状态: 1. 不结算 2. 进多(开盘价) 3. 平多(开盘价), 进空(开盘价), 平空(止盈止损价), 4. 进多(开盘价), 平多(止盈止损价)
  - 触发来源: 1.无 2. 进多(索引1) 3. 平多进空(索引2), 平空(索引3) 4. 进多(索引3) 平多(索引4)
  - 判断方式, 需要结合当前仓位状态和离场模式, 以及上一个仓位状态和离场模式进行判断
  - 即使是特殊案例, 也依然符合设计模式

### 5. 资金与风控
- `initial_capital`: `f64`，初始本金（USD）
- `stop_pct`, `resume_pct`：`Param<f64>`
  - `stop_pct > 0` → 启用暂停开仓
  - `resume_pct > 0` → 启用恢复开仓
  - 否则跳过该功能
  - 不影响已有仓位, 只是限制对新仓位的处理

### 6. 费用模型
- `fee_fixed`: `f64`，固定手续费（USD）
- `fee_pct`: `f64`，百分比手续费
  - **仅在离场时扣除一次**，开仓不扣
  - 建议用户自行通过提高手续费实现**悲观估算（含滑点、价差、网络延迟）**

---

## 仓位与资金管理规则

- **单仓位系统**：任意时刻只持有一个方向仓位（多/空/无）
- **全仓操作**：每次进场使用**全部可用余额**
- **反手逻辑**：
  - 先结算已有平仓（扣手续费）
  - 再以剩余资金开新仓（不扣手续费）
- **无杠杆**：默认 1 倍，杠杆由用户在外层计算, 回测引擎内部不做处理

---

## 信号分类（严格进场，宽松离场）

所有信号判断基于**当前 bar 完整数据**

- **反手信号（平空进多）**：
  - 条件：`持空` + `enter_long=true` + `exit_long=false` + `enter_short=false` + (`exit_short=true` 或 short 方向任一 SL/TP/TSL 触发)
  - 否则忽略

- **反手信号（平多进空）**：
  - 条件：`持多` + `enter_short=true` + `exit_short=false` + `enter_long=false` + (`exit_long=true` 或 long 方向任一 SL/TP/TSL 触发)
  - 否则忽略

- **多头离场信号**：
  - 条件：`持多` + (`exit_long=true` 或 long 方向任一 SL/TP/TSL 触发)
  - 否则忽略

- **空头离场信号**：
  - 条件：`持空` + (`exit_short=true` 或 short 方向任一 SL/TP/TSL 触发)
  - 否则忽略

- **多头进场信号**：
  - 条件：`无仓位` + `enter_long=true` + `exit_long=false` + `enter_short=false` + `exit_short=false`
  - 否则忽略

- **空头进场信号**：
  - 条件：`无仓位` + `enter_short=true` + `exit_short=false` + `enter_long=false` + `exit_long=false`
  - 否则忽略

---

## 信号优先级（由高到低）

- **skip_mask = true**：
  - 若有仓位 → **next_bar 离场**（开盘价）
  - 若无仓位 → 跳过后续所有信号
- **ATR 止损/止盈点为 NaN** → 跳过开仓
- **余额或净值归零** -> 跳过开仓
- **反手信号**
- **离场信号**
- **进场信号**

> **一次触发，后续全部忽略**，形成互斥决策链

---

## 离场优先级（同方向多信号）

- **不同方向离场信号**：因信号分类互斥，不会同时出现，无需处理
- **同方向多信号**：
  - `sl(in_bar)` > `tp(in_bar)` > `sl(next_bar)` / `tp(next_bar)` / `tsl(next_bar)` / `exit_signal(只有next_bar)`
  - **in_bar 信号优先于所有 next_bar 信号**

### in_bar 多止损合并规则（取最悲观）
- 若同时触发多个 `in_bar` 止损/止盈：
  - 计算所有候选离场价
  - **多头**：取 **最低价**（亏最多或赚最少）
  - **空头**：取 **最高价**
  - 示例：
    * `sl_pct` + `sl_atr` → 取 `min(止损价1, 止损价2)`
    * `sl_pct` + `tp_atr` → 直接取 `sl_pct`（止损比止盈更悲观）

### next_bar 信号（无合并问题）
- `exit_long/short`, `tsl`, `sl(next_bar)`, `tp(next_bar)` 均在下一 bar 开盘价离场
- 价格相同，无需比较

---

## 回测输出（DataFrame）

### 固定列
- `balance`：账户余额, 带复利
- `equity`：账户净值（含未实现盈亏）, 带复利
  - 不能小于0, 亏损大于净值, 就直接当下清仓, 并且净值和余额归零, 净值和余额归零后禁止开仓
- `cumulative_return`:累计回报率, 带复利
  - 每 bar 计算：(当前 equity / initial_capital) - 1
  - 初始 bar：0.0（或 NaN）
- `position`：仓位状态（`i8`）
  - `0`=无仓位, `1`=进多, `2`=持多, `3`=平多, `4`=平空进多
  - `-1`=进空, `-2`=持空, `-3`=平空, `-4`=平多进空
- `exit_mode`：离场模式（`u8`）
  - `0`=无离场, `1`=in_bar 离场, `2`=next_bar 离场, `3`=上一个bar是 next_bar 离场模式
  - **仅在 `position=±3, ±4` 时有效**
- `entry_price`：进场价格
- `exit_price`：实际离场价格（根据 `exit_mode` 结算）
- `pct_return`：本笔交易盈亏百分比
- `fee`: 单笔离场结算手续费。仅在离场时记录。其余为 0.0。(固定手续费+百分比手续费)
- `fee_cum`：当前历史累计手续费。记录从回测开始到当前 K 线为止，账户累计支付的所有手续费总额。(固定手续费+百分比手续费)

### 可选列（动态生成）
- 若参数 `> 0` → 添加对应列，记录**持仓期间的止损/止盈价**
  - `sl_price`, `tp_price`, `tsl_price`, `atr`

### 状态记录规则（与实盘完全对齐）
- **所有 `position` 和 `exit_mode` 均在【信号触发 bar】记录**
- **信号触发bar**就是回测循环的**当前索引bar**
- **实际结算时机**：
  - `exit_mode=1` → **信号触发bar** 按 `sl_price`/`tp_price` 结算
  - `exit_mode=2` → **信号触发bar的下一 bar 开盘价** 结算

#### 实盘对接说明
- **in_bar 模式**：
  - 开仓同时提交止盈止损单至交易所, 由交易所自动触发
  - 回测在**同 bar 标记状态 + 按止盈止损点结算**
- **next_bar 模式**：
  - 程序监控上一个完整 bar 交易信号，下一 bar 开盘下单
  - 回测在**触发 bar 标记状态**，**下一 bar 开盘价结算**

---

## 初始化与边界处理

- **初始状态**：`position=0`，无仓位
- **ATR NaN 处理**：
  - 若计算出的 SL/TP/TSL 为 `NaN`（通常为前导周期不足）
  - → 跳过本次开仓，优先级等同 `skip_mask` 之后
- **最后一根 bar**：
  - **无特殊处理**，按正常逻辑执行
  - 不添加标记

---

## 手续费与反手扣费逻辑

- **手续费仅在离场时扣除一次**
- **扣费时机**：
  - `in_bar 离场` → 当前 bar 扣除
  - `next_bar 离场` → 下一 bar 扣除
- **反手操作**：
  - **先平仓** → 扣一次手续费
  - **再开仓** → 不扣手续费
  - **后续离场** → 再扣一次手续费
    - 后续离场其实和普通离场一样,无需特殊处理
  - 扣费时机随“先平仓”和“后续离场”对应的 `exit_mode` 决定

---

## 盈亏计算方式

- **价格盈亏百分比** = `(离场价 - 进场价) / 进场价`（多头）或反之
- **实际盈亏** = (价格盈亏百分比 - 百分比手续费) × 下单金额 - 固定手续费
- **无杠杆**：回测仅验证策略，杠杆由用户外层估算

---

## 仓位管理（止损后暂停/恢复）

- **暂停开仓**：
  - 从**历史最高净值**开始
  - 若当前净值下跌超过 `stop_pct` → 暂停新开仓（不影响现有仓位）
- **恢复开仓**：
  - 从**历史最高净值到当前 bar 间的最低点**开始
  - 若净值较最低点上涨超过 `resume_pct` → 恢复开仓权限
  - **仍需等待进场信号**

---

## 年化回报率:
  - 年化回报率在当前回测模块无需计算, 应该在下一个绩效模块计算, 此处只是记录一下思路
  - cumulative_return
    - 公式: 每 bar 计算：(当前 equity / initial_capital) - 1
    - 最后一个值就是总回报率(Total Return)
  - 总天数, time列(毫秒级时间戳)
    - 公式: (最后一条时间戳 -第一条时间戳) / (每天毫秒数)
  - 年化基数
    - 日历天 365, 也可以用 252之类的
  - 时间缩放指数
    - 公式: 年化基数 / 总天数
  - 年化回报率(CAGR)
    - 公式: CAGR = (1 + Total Return) ^时间缩放指数 - 1

---

## 性能与实现约束

- **ATR 计算**：
  - 循环前调用 `atr_eager` 一次性计算
  - 使用 `ATRConfig::new(period)` 设置默认列名
- **数据获取**：
  - `ohlcv` 从 `processed_data.source["ohlcv"]` 获取，key 不存在 → 报错
- **内存连续性**：
  - 所有输入 `DataFrame` `Series` 必须 `.is_contiguous()`
  - 不连续 → 报错，要求用户在外层 `.rechunk()`
  - signal DataFrame是布尔列, 为了提高性能, 用polars的方法转换成整数列, 然后用`.is_contiguous()`处理
- **零拷贝循环**：
  - 使用 `contiguous_slice()` 获取 `&[f64]`，避免迭代器开销
- 循环中优先检查 `skip_mask[i]` 和 `atr[i].is_nan()`，短路后续计算
- **避免 `unsafe`**：接受微小性能损失
- ** 不要滥用 `clone` 非clone的写法优先
- **异常体系**：
  - 在 `src/error/` 中定义 `BacktestError` 子类，统一错误处理
- **拆分主循环**
  - 为了避免主循环太长难以维护, 不要在主循环中内联具体代码, 而是创建辅助模块, 把具体代码写到辅助模块里, 然后在主循环中调用辅助模块
- **参数结构体复用**
  - 参数结构体应该复用 `src/data_conversion/input/param_set.rs` 里的 `BacktestParams` 对象。如果现有结构体中的字段不够用，应在 `BacktestParams` 对象中添加新的键来承载所需的参数。

---

回测模块, 还涉及到几个外部文件, 这几个文件, 一般没什么必要改动就别改, 改的话, 也只改跟回测模块相关的, 不要改无关的
@/src/backtest_engine/backtester/mod.rs
@/src/data_conversion/input/data_dict.rs
@/src/data_conversion/input/param_set.rs
@/src/backtest_engine/indicators/atr.rs
src/error/backtest_error.rs
