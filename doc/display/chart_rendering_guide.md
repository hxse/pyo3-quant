# 图表渲染指南：Jupyter vs Marimo

## 概述

本项目的图表基于 **LightWeight Charts**（Svelte 5 编译的 UMD bundle），通过 Python 封装层同时支持 Jupyter Notebook (.ipynb) 和 Marimo (.py) 两种环境。

### 渲染模式矩阵

```
              Jupyter          Marimo
anywidget     ✅ 轻量交互       ✅ 轻量 + 离线缓存
HTML embed    ✅ 离线缓存/导出   ❌ 不需要
```

### `target` 参数

`DisplayConfig` 通过 `target` 字段区分运行环境：

| `target` | `embed_data` | 渲染路径 | 返回类型 |
|----------|-------------|---------|---------|
| `"jupyter"`（默认） | `False`（默认） | `render_as_widget()` | `ChartDashboardWidget` |
| `"jupyter"` | `True` | `render_as_html()` | `IPython.display.HTML` |
| `"marimo"` | 忽略 | `render_as_marimo_widget()` | `mo.ui.anywidget(...)` |

## 架构

```
RunResult.display(config=DisplayConfig)
    │
    ├─ target="marimo" → render_as_marimo_widget()
    │   - 复用 render_as_widget() 创建 ChartDashboardWidget
    │   - 外层用 mo.ui.anywidget() 包装
    │   - 文件：py_entry/runner/display/marimo_renderer.py
    │
    ├─ target="jupyter" + embed_data=False → render_as_widget() → ChartDashboardWidget (anywidget)
    │   - 数据通过 traitlets.Bytes 二进制传输（无 base64 开销）
    │   - JS 端接收后转 base64 传给 Svelte 图表组件
    │   - 文件：py_entry/runner/display/widget_renderer.py
    │          py_entry/runner/display/chart_widget.py
    │          py_entry/runner/display/chart_widget.js
    │
    └─ target="jupyter" + embed_data=True → render_as_html() → IPython.display.HTML
        - 数据 base64 编码后嵌入 <script type="text/plain"> 标签
        - JS/CSS 可内联（embed_files=True）或外部引用
        - 文件：py_entry/runner/display/html_renderer.py
               py_entry/runner/display/html_renderer.js
```

---

## Jupyter Notebook (.ipynb) 支持

### 两种模式对比

| 特性 | anywidget 模式 | HTML 内嵌模式 |
|------|--------------|-------------|
| 文件体积 | 小（数据不存入 .ipynb） | 大（base64 数据 + JS/CSS 全部存入 .ipynb） |
| 重启后能否看图 | 不能，需重新运行 cell | **能**，输出已保存在 .ipynb JSON 中 |
| 交互性 | 完整交互 | 完整交互 |
| 数据传输效率 | 高（二进制传输，无 base64 开销） | 较低（~33% base64 膨胀） |
| 导出/分享 | 不支持离线查看 | 支持（自包含 HTML） |

### 推荐用法

```python
# 场景 1：开发调试（轻量、快速）
config = DisplayConfig(embed_data=False)
result.display(config=config)

# 场景 2：保存结果供日后查看（离线缓存）
config = DisplayConfig(embed_data=True, embed_files=True)
result.display(config=config)
```

---

## Marimo (.py) 支持

### 核心原理

Marimo 的笔记本文件是**纯 Python 代码**（`.py`），不包含任何 cell 输出。因此 HTML 内嵌模式没有离线缓存优势。

**Marimo 只需要 anywidget 模式**，原因：
- Marimo 自动运行 + `mo.persistent_cache` = 打开即看图（等同于 Jupyter 的 HTML 离线缓存）
- anywidget 同时满足"小文件"和"离线缓存"两个需求
- `target="marimo"` 时 `embed_data` 参数被忽略

### 推荐用法

```python
import marimo as mo

@app.cell
def _(mo, run_button):
    from py_entry.example.custom_backtest import run_custom_backtest

    if run_button.value:
        with mo.persistent_cache("backtest_result"):
            result = run_custom_backtest()
    else:
        result = None
    return (result,)


@app.cell
def _(mo, result):
    from py_entry.io import DashboardOverride, DisplayConfig

    mo.stop(result is None)

    config = DisplayConfig(
        target="marimo",
        width="100%",
        aspect_ratio="16/9",
        override=DashboardOverride(
            show=["0,0,0,1"],
            showInLegend=["0,0,0,1"],
            showRiskLegend="1,1,1,1",
            showLegendInAll=True,
        ).to_dict(),
    )
    result.display(config=config)
    return
```

### Marimo 的离线缓存机制

虽然不存输出，但 Marimo 有两个特性弥补了这个差距：

**1. 自动运行：打开即执行**

Marimo 打开笔记本时会**自动运行所有 cell**（不像 Jupyter 需要手动 Run All）。

**2. `mo.persistent_cache`：磁盘缓存计算结果**

对于耗时的回测计算，可以用 `mo.persistent_cache` 将结果缓存到磁盘（`__marimo__/cache/` 目录）。下次打开时：

1. Marimo 自动运行 cell
2. `persistent_cache` 检测到缓存未过期，直接从磁盘恢复数据（毫秒级）
3. anywidget 渲染图表（渲染本身很快）

**效果等同于 Jupyter 的 HTML 离线缓存，但实现路径不同。**

### `mo.persistent_cache` 的失效条件

缓存会在以下情况失效（自动重新计算）：
- cell 的代码发生变化（不含注释和格式变更）
- cell 的上游依赖发生变化
- 手动删除 `__marimo__/cache/` 目录

---

## 平台对比总结

```
                    Jupyter (.ipynb)              Marimo (.py)
                    ─────────────────             ─────────────
文件存输出？          是（JSON 含输出）              否（纯 Python）
重启后自动运行？       否（需手动 Run All）           是（自动运行所有 cell）
离线缓存方案          HTML 内嵌 → 输出存在文件中      mo.persistent_cache → 数据缓存到磁盘
推荐 target          "jupyter"（默认）              "marimo"
推荐渲染模式          anywidget（开发）              anywidget（所有场景）
                    HTML embed（缓存/导出）
```

### "打开就能看图"的实现路径

```
Jupyter:
  打开 .ipynb → 输出已在文件中 → HTML embed 直接可见 ✅
  打开 .ipynb → 手动 Run All → anywidget 重新渲染 ✅

Marimo:
  打开 .py → 自动运行 → persistent_cache 命中 → 数据瞬间恢复 → anywidget 渲染 ✅
  打开 .py → 自动运行 → persistent_cache 未命中 → 重新计算（慢） → anywidget 渲染 ✅
```

---

## 注意事项

### Marimo 的 anywidget 兼容性

- Marimo 原生支持 anywidget（[官方文档](https://docs.marimo.io/api/inputs/anywidget/)）
- `target="marimo"` 时自动完成 `mo.ui.anywidget()` 包装，用户无需手动处理
- `target="marimo"` 且 marimo 未安装时，会抛出清晰的 `ImportError`

### Marimo 的 HTML 渲染限制

- `mo.Html()` / `mo.as_html()` **不执行 `<script>` 标签**
- 需要用 `mo.iframe()` 包装才能执行脚本
- 因此 `target="marimo"` 强制使用 anywidget 模式，避免此问题
