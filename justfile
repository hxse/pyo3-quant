# Pyo3-Quant Justfile
# 使用 `just` 命令运行常用开发任务
# 安装 just: cargo install just 或 sudo apt install just

# 列出所有可用命令
default:
    @just --list

# ==================== 环境设置 ====================

# 首次设置开发环境 (一键配置)
setup:
    bash scripts/setup_dev_env.sh

# 同步 Python 依赖
sync:
    uv sync

# 安装 maturin import hook (推荐的开发模式)
hook-install:
    source ./.venv/bin/activate && python -m maturin_import_hook site install --args="--release"

# 卸载 maturin import hook
hook-uninstall:
    source ./.venv/bin/activate && python -m maturin_import_hook site uninstall

# 使用 maturin develop 编译 (传统开发模式)
develop:
    source ./.venv/bin/activate && maturin develop --release

# 清理 Rust 编译缓存
clean:
    cargo clean

# ==================== 运行 ====================

# 运行任意 Python 模块 (支持斜杠或点号格式)
# 例: just run py_entry/example/basic_backtest
# 例: just run py_entry.example.basic_backtest
run path:
    PYTHONPATH=. uv run --no-sync python {{ path }}

# 运行基础回测示例
run-basic:
    PYTHONPATH=. uv run --no-sync python py_entry/example/basic_backtest.py

# 运行自定义回测示例
run-custom:
    PYTHONPATH=. uv run --no-sync python py_entry/example/custom_backtest.py

# 计时运行基础回测
run-time path:
    PYTHONPATH=. /usr/bin/time -f "\n执行时间: %e 秒" uv run --no-sync python {{ path }}

# 运行 debug 目录下的脚本 (例: just debug debug_compare)
debug name:
    PYTHONPATH=. uv run --no-sync python py_entry/debug/{{name}}.py

# ==================== 测试 ====================

# 运行所有 Python 测试
test:
    uv run --no-sync python -m pytest py_entry/Test

# 运行指定的测试文件或目录 (例: just test-path py_entry/Test/backtest)
test-path path:
    uv run --no-sync python -m pytest {{path}}

# 运行策略相关性分析测试 (默认 reversal_extreme)
test-correlation strategy="reversal_extreme":
    uv run --no-sync python -m pytest py_entry/Test/backtest/correlation_analysis/test_correlation.py -k "{{strategy}}" -s -v


# ==================== 代码检查 ====================

# 运行 Rust cargo check
check-rust:
    cargo check

# 运行 Python 类型检查 (ty)
check-py:
    uvx ty check

check: check-rust check-py

# ==================== 代码格式化 ====================

# 格式化 Python 代码 (ruff)
fmt-py:
    uvx ruff format

# 格式化 Rust 代码
fmt-rust:
    cargo fmt

# 格式化所有代码 (Python + Rust)
fmt: fmt-py fmt-rust

# ==================== Lint ====================

# 运行 Python linter (ruff)
lint-py:
    uvx ruff check

# 自动修复 Python lint 错误
lint-fix-py:
    uvx ruff check --fix

# 运行 Rust linter (clippy)
lint-rust:
    cargo clippy

# 自动修复 Rust lint 错误
lint-fix-rust:
    cargo clippy --fix --allow-dirty --allow-staged

# 运行所有 linter
lint: lint-py lint-rust

# 自动修复所有代码错误 (Python + Rust)
fix: lint-fix-py lint-fix-rust

# ==================== 构建 ====================

# 构建 wheel 包
build:
    maturin build --release

# 构建并安装 wheel 包
build-install:
    maturin build --release && uv pip install target/wheels/*.whl --force-reinstall
