# Pyo3-Quant Justfile
# 使用 `just` 命令运行常用开发任务
# 安装 just: cargo install just 或 sudo apt install just

# 列出所有可用命令
default:
    @just --list

# ==================== 环境设置 ====================

python_libdir := `uv run --no-sync python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))"`
export LD_LIBRARY_PATH := python_libdir + ":" + env_var_or_default("LD_LIBRARY_PATH", "")
export PYTHONPATH := "."

# 首次设置开发环境 (一键配置)
setup:
    bash scripts/setup_dev_env.sh

# 同步 Python 依赖
sync:
    uv sync

# 安装 maturin import hook (推荐的开发模式)
# hook-install:
#     uv run --no-sync python -m maturin_import_hook site install --args="--release"

# 卸载 maturin import hook
# hook-uninstall:
#     uv run --no-sync python -m maturin_import_hook site uninstall

# 使用 maturin develop 编译 (传统开发模式)
develop:
    uv run --no-sync maturin develop --release
    just stub

# 生成 Python 类型存根 (.pyi)
stub: stub-clean
    uv run --no-sync cargo run --bin stub_gen
    just fmt-py

# 清理生成的 Python 类型存根
stub-clean:
    find python/pyo3_quant -name "*.pyi" -delete

# 清理所有构建产物
clean: stub-clean
    uv run --no-sync cargo clean

# ==================== 运行 ====================

# 运行 Python 示例；默认运行 custom_backtest
# 例: just run
# 例: just run path=py_entry/example/real_data_backtest.py
run path="py_entry/example/custom_backtest.py": develop
    uv run --no-sync python {{ path }}

# 运行性能基准测试 (pyo3-quant vs VectorBT)
benchmark: develop
    uv run --no-sync --with vectorbt python -m py_entry.benchmark.run_benchmark

# 运行复杂度仿真测试 (Numba Complexity Test)
benchmark-check: develop
    uv run --no-sync --with vectorbt python -m py_entry.benchmark.numba_complexity_test

# 计时运行基础回测
# 注意: /usr/bin/time 是系统命令，不应加 uv run
run-time path: develop
    /usr/bin/time -f "\n执行时间: %e 秒" uv run --no-sync python {{ path }}

# 运行 debug 目录下的脚本 (例: just debug debug_compare)
debug name: develop
    uv run --no-sync python py_entry/debug/{{name}}.py

# ==================== 测试 ====================

# 运行 Python 测试 (可选 path 参数，例: just test-py path="py_entry/Test/backtest")
test-py path="py_entry/Test": develop
    uv run --no-sync python -m pytest {{path}}

# 运行 Rust 单元测试
test-rust:
    uv run --no-sync cargo test

# 运行所有测试
test: test-rust test-py

# 运行策略相关性分析测试 (默认 reversal_extreme)
test-correlation strategy="reversal_extreme": develop
    uv run --no-sync python -m pytest py_entry/Test/backtest/correlation_analysis/test_correlation.py -k "{{strategy}}" -s -v


# ==================== 代码检查 ====================

# 运行 Rust cargo check
check-rust:
    uv run --no-sync cargo check

# 运行 Python 类型检查 (ty)
check-py: develop
    uvx ty check

# 检查 private research/live 同名策略文件是否一致（research 不存在时自动跳过）
live-sync-check:
    uv run --no-sync python scripts/live_sync_check.py

check: check-rust check-py live-sync-check

# ==================== 代码格式化 ====================

# 格式化 Python 代码 (ruff)
fmt-py:
    uvx ruff format

# 格式化 Rust 代码
fmt-rust:
    uv run --no-sync cargo fmt

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
    uv run --no-sync cargo clippy

# 自动修复 Rust lint 错误
lint-fix-rust:
    uv run --no-sync cargo clippy --fix --allow-dirty --allow-staged

# 运行所有 linter
lint: lint-py lint-rust

# 自动修复所有代码错误 (Python + Rust)
fix: lint-fix-py lint-fix-rust

# ==================== 构建 ====================

# 构建 wheel 包
build:
    just stub
    uv run --no-sync maturin build --release

# 构建并安装 wheel 包
build-install: build
    uv pip install target/wheels/*.whl --force-reinstall

# ==================== 扫描器 (独立模块，使用天勤量化) ====================

# 安装扫描器依赖
scanner-install:
    uv sync --group scanner

# 运行趋势共振扫描器（持续运行）
scanner-run: develop
    uv run --no-sync --group scanner python -m py_entry.scanner.main

# 运行扫描器（单次扫描）
scanner-once: develop
    uv run --no-sync --group scanner python -m py_entry.scanner.main --once

# 运行扫描器（Mock 模式，离线测试）
scanner-mock: develop
    uv run --no-sync --group scanner python -m py_entry.scanner.main --once --mock

# 运行扫描器单元测试
scanner-test: develop
    uv run --no-sync --group scanner python -m pytest py_entry/Test/scanner/ -v

# 运行趋势共振扫描器（调试模式，包含以 debug_ 开头的测试策略）
scanner-debug: develop
    uv run --no-sync --group scanner python -m py_entry.scanner.main --debug

# 查看最新行情数据及指标数值 (EMA, CCI, MACD)
scanner-inspect: develop
    uv run --no-sync --group scanner python py_entry/debug/inspect_scanner_data.py
