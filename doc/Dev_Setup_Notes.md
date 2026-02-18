# 开发环境说明（精简版）

本文档仅保留 `justfile` 之外的必要信息。
日常开发命令以 `justfile` 为唯一入口。

## 1. 首次初始化

```bash
just setup
```

等价脚本：

```bash
bash scripts/setup_dev_env.sh
```

如果提示缺少 `patchelf`：

```bash
sudo apt install patchelf
```

## 2. 日常开发入口（以 justfile 为准）

查看全部命令：

```bash
just
```

常用命令：

```bash
just sync
just run
just check
just test
just fmt
```

指定脚本运行：

```bash
just run path=py_entry/example/custom_backtest.py
```

## 3. 工作流约束

1. 先 `just check`，再 `just test`。
2. 不要绕过 `justfile` 直接拼底层命令（除非排障）。
3. `just run` / `just check` 会触发 `develop` 与 `stub`，属于预期行为。

## 4. 仅在排障时使用的手动命令

```bash
uv run --no-sync maturin develop --release
uv run --no-sync cargo run --bin stub_gen
uvx ty check
```

只有当 `just` 流程异常时，才建议单独执行这些命令定位问题。
