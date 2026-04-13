# Python precheck 删除

## 1. 旧入口为什么会存在

`validate_wf_indicator_readiness(...)` 最早是为了在真正跑 WF 之前先做一次 Python 侧 fail-fast，避免 notebook 流程拖到最后才发现 warmup 不够。

这个出发点可以理解，但在 `03-10` 之后已经不再成立为正式设计，因为：

1. warmup 真值链已经收口到 Rust 正式主流程。
2. Python precheck 会和正式入口形成第二套 gate。
3. workflow、文档和测试会继续围绕旧入口构建。

## 2. 本任务的正式选择

本任务的结论很简单：

1. 删除 `validate_wf_indicator_readiness(...)`。
2. 删除 workflow 对该入口的依赖。
3. 不补新的公开 explain / precheck API。

## 3. 为什么不补新的 explain 壳层

因为这会在名义上删旧入口，实际上继续保留第二个公开入口。

对当前任务来说，这种做法没有净收益，只有继续拖着双轨往前走。

## 4. 如果未来确实需要解释工具

那应当单开新 task，并明确写清：

1. 它只做只读解释。
2. 它不参与 gate。
3. 它不定义第二套 fail-fast。
