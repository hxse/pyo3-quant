# Chart Widget 补丁说明（P0~P5）

本文档只描述 `py_entry/runner/display/chart_widget.js` 中保留的稳定补丁，便于后续继续精简时快速判断“哪些能删、哪些不能删”。

## 补丁总览

| 补丁 | 适用环境 | 触发症状 | 当前方案 |
| --- | --- | --- | --- |
| P0 | 通用 | 仅靠前端环境推断，行为不可控 | `target` 显式分流，环境仅兜底 |
| P1 | 通用 | 首次挂载高度过小，图表被压缩 | 宿主容器设置最小可用高度 |
| P2 | 通用 | 父容器裁切导致显示不全/滚动异常 | 放宽当前宿主层 `overflow/max-height` |
| P3 | marimo 主修复 | `.contents/.marimo` 高度链断裂，子图高度塌陷 | 仅修复这条高度链 |
| P4 | 通用兜底 | 外层 output 容器裁切导致上下被截断 | 放宽宿主与最近 output 容器限制 |
| P5 | ipynb/marimo 分流 | ipynb 压扁、marimo 竖滚动条 | `aspect-ratio` 按 `target` 分流 |

## 关键设计原则

1. 只做容器层修复，不改业务数据与图表配置。
2. `target` 参数优先于环境推断，保证行为可复现。
3. 避免“重型布局干预”，保留最小稳定补丁集合。

## 运行时分流规则

1. Python 侧通过 `DisplayConfig(target=...)` 传入目标环境。
2. JS 侧优先读取 `model.get("target")`，仅在缺失时用 ShadowRoot 兜底推断。
3. `aspect-ratio` 规则：
   - `target="jupyter"`：保留 `aspect-ratio`（避免图表压扁）
   - `target="marimo"`：清空 `aspect-ratio`（避免竖向滚动条）

## 配置示例

```python
from py_entry.io import DisplayConfig

# ipynb 推荐
ipynb_cfg = DisplayConfig(target="jupyter", width="100%", aspect_ratio="16/9")

# marimo 推荐
marimo_cfg = DisplayConfig(target="marimo", width="100%", aspect_ratio="16/9")
```

## 精简建议（后续）

1. 如果要继续删补丁，优先从 P4 开始做 A/B 验证。
2. P3 和 P5 是当前 marimo/ipynb 同时稳定的核心分流，建议最后再动。
3. 每次只删一个补丁，并在 `marimo + ipynb` 双端回归后再继续。
