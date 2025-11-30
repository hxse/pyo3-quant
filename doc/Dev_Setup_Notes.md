# 💻 WSL2 环境配置与 Rust/Maturin 开发工作流

本文档详细记录了在 WSL2 环境下，针对使用 Rust 扩展 Python 模块（通过 Maturin）的开发设置、编译优化以及常见操作流程。

---

## 🛠️ 环境依赖与 Rust 安装

本节包含初始化项目和安装 Rust 及其工具链的步骤。

### 1. 项目初始化 (使用 `uv`)

使用 `uv` 工具安装 `maturin` 并初始化项目结构。

* **安装 Maturin 工具:**
    ```bash
    uv tool install maturin
    ```
* **初始化 Rust 项目结构:**
    ```bash
    maturin init
    ```

### 2. Rust 编程环境安装

Rust 编译器和工具链是构建项目的核心依赖。

* **更新系统包列表:**
    ```bash
    sudo apt update
    ```
* **安装构建必需的工具 (`build-essential`):**
    ```bash
    sudo apt install build-essential
    ```
* **使用 `rustup` 安装 Rust:**
    ```bash
    curl --proto '=https' --tlsv1.2 -sSf [https://sh.rustup.rs](https://sh.rustup.rs) | sh
    ```
* **应用 Rust 环境变量:**
    （在新终端中通常会自动加载，但如果需要立即生效，请执行此命令）
    ```bash
    source "$HOME/.cargo/env"
    ```

---

## 🚀 编译优化与 Maturin 导入钩子

为了实现更快的开发循环和更高的编译性能，建议配置 `maturin_import_hook` 和自定义链接器。

### 1. 使用 `maturin_import_hook`

`maturin_import_hook` 允许您直接从源代码编译和导入 Rust 模块，无需手动生成和安装 `.whl` 文件。

* **安装 `patchelf` (系统级):**
    ```bash
    sudo apt install patchelf
    ```
* **安装 `patchelf` (虚拟环境内):**
    ```bash
    uv run pip install patchelf
    ```
* **添加 `maturin_import_hook` 作为开发依赖:**
    ```bash
    uv add --dev maturin_import_hook
    ```
* **激活虚拟环境:**
    ```bash
    source ./.venv/bin/activate
    ```
* **安装导入钩子并编译 Rust 模块:**
    此命令会即时编译 Rust 模块并使其可被 Python 导入。
    ```bash
    python -m maturin_import_hook site install --args="--release"
    ```
    > ℹ️ **注意:** 建议始终使用 `--release` 参数进行编译。**不带 `release` 参数时，由于额外的调试信息和优化级别较低，编译速度会异常缓慢。**

* **卸载导入钩子 (可选):**
    ```bash
    python -m maturin_import_hook site uninstall
    ```

### 2. 优化链接器 (使用 Mold)

Rust 1.90.0 版本后默认使用 `lld` 作为链接器。**Mold** 是一个性能更好的现代链接器，可以显著加快编译速度。

* **安装 Clang 和 Mold:**
    `Clang` 作为前端，`Mold` 作为链接器。
    ```bash
    sudo apt install clang mold -y
    ```
* **配置 Cargo 使用 Mold:**
    编辑或创建 `~/.cargo/config.toml` 文件。

    ```bash
    nano ~/.cargo/config.toml
    ```

    添加以下配置：
    ```toml
    [target.x86_64-unknown-linux-gnu]
    # 确保 clang 已安装
    rustflags = ["-C", "linker=clang", "-C", "link-arg=-fuse-ld=mold"]
    ```

* **清理旧的编译缓存:**
    配置更改后，执行 `cargo clean` 以确保下次编译使用新的链接器。
    ```bash
    cargo clean
    ```

---

## 🏃 日常开发 (Dev) 工作流

本节包含常用的开发和测试命令。

### 1. 环境同步与运行

* **同步 Python 依赖:**
    ```bash
    uv sync
    ```
* **直接运行 Python 脚本 (跳过同步):**
    ```bash
    uv run --no-sync python -m py_entry.example.basic_backtest
    ```


### 1. Rust 模块加载方式

有多种方式在开发环境中加载和测试 Rust 模块：

* **方法 A: 使用 `maturin_import_hook` (推荐的开发方式)**
    * **步骤 1:** 激活虚拟环境：
        ```bash
        source ./.venv/bin/activate
        ```
    * **步骤 2:** 安装导入钩子并编译 Rust 模块：
        ```bash
        python -m maturin_import_hook site install --args="--release"
        ```
        > 💡 **备注:** 一次安装，多次使用。**必须**使用 `--release` 编译以加速。
    * **步骤 3:** 运行 Python 脚本：
        ```bash
        python -m py_entry.example.basic_backtest
        ```

* **方法 B: 使用 `maturin develop`**
    * **步骤 1:** 激活虚拟环境：
        ```bash
        source ./.venv/bin/activate
        ```
    * **步骤 2:** 编译模块并链接到虚拟环境：
        ```bash
        maturin develop --release
        ```
        > 💡 **备注:** 这是 `maturin` 的传统开发模式，**每次运行前都需执行**此编译步骤。
    * **步骤 3:** 运行 Python 脚本：
        ```bash
        python -m py_entry.example.basic_backtest
        ```

* **方法 C: 安装 `.whl` 文件**
    * **步骤 1:** 安装 `.whl` 构建包：
        ```bash
        uv pip install whl_path
        ```
        > 💡 **备注:** 适用于测试最终的构建包，或者在 CI/CD 环境中。
    * **步骤 2:** 运行 Python 脚本：
        ```bash
        uv run --no-sync python -m py_entry.example.basic_backtest
        ```

---

## ⚙️ 代码质量与测试

### 1. 运行示例 (Example)

* **运行回测示例:**
    ```bash
    uv run --no-sync python -m py_entry.example.basic_backtest
    ```
* **测试执行与计时:**
    使用 `/usr/bin/time` 测量脚本执行时间。
    ```bash
    /usr/bin/time -f "\n%e" uv run --no-sync python -m py_entry.example.basic_backtest
    ```

### 2. 单元测试 (Test)

* **运行 Python/Pytest 测试:**
    ```bash
    uv run --no-sync python -m pytest py_entry/Test
    ```

### 3. 代码检查 (Check)

* **运行 `ty` 类型检查 (假设已安装):**
    ```bash
    uvx ty check
    ```
* **运行 Rust 模块检查 (不编译):**
    ```bash
    uv run --no-sync cargo check
    ```

### 4. 代码格式化 (Format)

* **运行 Python/Ruff 格式化:**
    ```bash
    uvx ruff format
    ```
* **运行 Rust/Cargo 格式化:**
    ```bash
    uv run --no-sync cargo fmt
    ```

