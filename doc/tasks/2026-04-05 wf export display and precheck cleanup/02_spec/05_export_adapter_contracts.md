# Export / Display 正式契约

## 1. 总目标

single backtest 与 WF stitched 共享 display / bundle 消费链路，但各自拥有独立结果解释层。

## 2. 正式分层

导出链路正式分成三层：

1. Python 结果视图层
   - `SingleBacktestView`
   - `WalkForwardView`
   - 这一层只表达结果语义；`prepare_export(...)` 的对象级语义以 `06_python_runner_view_and_bundle_contracts.md` 为准
2. 结果适配层
   - single adapter：把 single backtest 结果翻译成标准化导出负载。
   - WF adapter：把 WF stitched 结果翻译成标准化导出负载。
3. 通用打包层
   - 只负责把标准化导出负载写成 buffers / zip。
   - 最终收口为 `PreparedExportBundle`
   - 不直接理解业务结果对象和业务 schedule 对象

packager 不负责决定文件语义，只消费已经冻结好的 payload key-path。

## 3. `prepare_export(...)` 与 bundle / `display(...)`

`prepare_export(...)` 与 `PreparedExportBundle` 的对象 contract 以 [06_python_runner_view_and_bundle_contracts.md](./06_python_runner_view_and_bundle_contracts.md) 为唯一正式定义处。

本文只冻结它们在 export adapter / packager 链路中的角色，不重复定义对象级行为约束：

1. `prepare_export(...)` 是 view 到 bundle 的正式导出入口。
2. `display(...)`、`save(...)`、`upload(...)` 正式消费 `PreparedExportBundle`，而不是结果视图对象。
3. single 与 WF 若共享 display 链路，共享的是 bundle 消费边界，而不是同一个结果对象类型。

这里的 `prepare_export(...)` 不是一个“拿到任意 view 后再动态猜该走哪个 adapter”的黑盒。

正式语义更简单：

1. `SingleBacktestView.prepare_export(...)` 固定委托 single adapter
2. `WalkForwardView.prepare_export(...)` 固定委托 WF adapter
3. adapter 生成 `ExportPayload`
4. packager 把 `ExportPayload` 打成 `PreparedExportBundle`

也就是说，adapter 的归属由 view 类型在定义时就写死，不靠运行时猜测。

## 4. 两条正式调用路径

single 路径固定为：

1. `Backtest.run()` 先得到 `SingleBacktestView`
2. `SingleBacktestView.prepare_export(...)` 固定委托 single adapter
3. single adapter 生成符合 `ExportPayload` schema 的标准化导出负载
4. 通用 packager 把导出负载写成 `PreparedExportBundle`
5. `PreparedExportBundle.display(...)` 只消费这份已经成形的 bundle

WF stitched 路径固定为：

1. `Backtest.walk_forward()` 先得到 `WalkForwardView`
2. `WalkForwardView.prepare_export(...)` 固定委托 WF adapter
3. WF adapter 生成符合 `ExportPayload` schema 的标准化导出负载
4. 通用 packager 把导出负载写成 `PreparedExportBundle`
5. `PreparedExportBundle.display(...)` 最终仍只消费这份已经成形的 bundle

`prepare_export(...)` 的正式职责只是：

1. 调本 view 固定绑定的 adapter 生成标准化导出负载
2. 调 packager 生成 `PreparedExportBundle`

它不是新的业务解释层，也不自己决定 `param_set/param.json` 或 `backtest_schedule/backtest_schedule.json` 的语义。

## 5. 最小调用示意

single 的正式调用示意应当简单到只有两步：

```python
view = backtest.run()
bundle = view.prepare_export(config)
bundle.display()
```

如果要保存或上传，也仍然是对 `bundle` 操作：

```python
view = backtest.run()
bundle = view.prepare_export(config)
bundle.save(save_config)
bundle.upload(upload_config)
```

WF stitched 的正式调用示意和 single 只有第一步不同：

```python
wf_view = backtest.walk_forward(wf_config)
bundle = wf_view.prepare_export(config)
bundle.display()
```

这就是正式调用体验：

1. 执行先拿到 mode-specific view
2. view 再纯投影成 bundle
3. display/save/upload 只吃 bundle

## 6. Python wrapper 与导出边界

1. `SingleBacktestView` 只表达 single backtest 结果语义。
2. `WalkForwardView` 只表达 WF 结果语义。
3. WF stitched 通过 `WalkForwardView` 直接进入 WF adapter。
4. `backtest_schedule` 若属于 WF stitched 的正式解释资产，只能由 WF adapter 在适配阶段展开。
5. `PreparedExportBundle` 只表达导出产物和消费入口，不回写结果语义。

## 7. 标准化导出负载

本任务冻结一份标准化导出负载 schema。本文用 `ExportPayload` 作为 spec 别名；具体 carrier type 名称可以变化，但 schema 与语义固定。

例如：

```python
@dataclass
class ExportPayload:
    data_frames: dict[str, pl.DataFrame]
    json_dicts: dict[str, dict | list]
    chart_config: dict | None = None
```

它的正式语义是：

1. `data_frames` 只承载已经决定路径和文件语义的表数据。
2. `json_dicts` 只承载已经展开成 JSON 友好结构的解释数据。
3. packager 只按 key-path 写文件，不承担业务对象展开职责。

packager 的正式输入是“符合 `ExportPayload` schema 的标准化导出负载”，不是某个具体类名强耦合的对象。

它不直接接收：

1. `SingleBacktestView`
2. `WalkForwardView`
3. `WalkForwardResult`
4. `WindowArtifact`
5. `StitchedArtifact`

## 8. adapter 与正式路径的最小对照

single adapter 必须负责产出：

1. `param_set/param.json`
2. single 所需的 `backtest_results/*`
3. single 所需的 `data_pack/*`

WF adapter 必须负责产出：

1. `backtest_schedule/backtest_schedule.json`
2. stitched 所需的 `backtest_results/*`
3. stitched 所需的 `data_pack/*`

两类 adapter 都允许产出：

1. `template_config/template_config.json`
2. `engine_settings/engine_settings.json`
3. `chartConfig.json`

## 9. Zip 结构 contract

1. Python 内部适配边界以 adapter / packager 分层组织。
2. 最终导出 Zip 文件树与 display 消费端依赖的正式文件路径保持固定。
3. WF stitched 以 `backtest_schedule/backtest_schedule.json` 作为正式解释资产。
4. single 导出以 `param_set/param.json` 作为正式参数解释资产。
5. `display(...)` 只消费 bundle 中已经成形的正式路径，不重新解释上游业务对象。

## 10. 禁止事项

1. 禁止让通用 packager 直接理解 WF schedule 业务对象。
2. 禁止让 `WalkForwardView` 通过伪造 single 结果视图进入导出链路。
3. 禁止让结果视图对象缓存 `export_buffers` / `export_zip_buffer`。
4. 禁止以“前端不变”为理由保留新的内部双轨兼容层。
5. 禁止让 adapter 之外的层直接决定 `backtest_schedule/backtest_schedule.json` 或 `param_set/param.json` 的业务内容。
