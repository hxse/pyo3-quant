# wsl2
  * `uv tool install maturin`
  * `maturin init`
  * install rust
    * `sudo apt update`
    * `sudo apt install build-essential`
    * `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
    * `source "$HOME/.cargo/env"`
## maturin_import_hook
  * `sudo apt install patchelf`
  * `uv run pip install patchelf`
  * `uv add --dev maturin_import_hook`
  * `source ./.venv/bin/activate`
  * `python -m maturin_import_hook site install --args="--release"`
    * `python -m maturin_import_hook site uninstall`
    * 由于某些原因,不带release编译速度会特别慢
  * `/usr/bin/time -f "\n%e" python -m py_entry.main`
## linker
  * Rust 1.90.0之后, 默认链接器是lld, 但是mold性能更好, 建议换成mold
  * mold加速编译
    * `sudo apt install clang mold -y`
    * nano `~/.cargo/config.toml`
    ```
    [target.x86_64-unknown-linux-gnu]
    # 确保 clang 已安装
    rustflags = ["-C", "linker=clang", "-C", "link-arg=-fuse-ld=mold"]
    ```
    * `cargo clean`

# dev
  * `uv sync`
  * 方法1
  * `/usr/bin/time -f "\n%e" uv run --no-sync python -m py_entry.main`
  * 方法2
    * `source ./.venv/bin/activate`
    * `python -m maturin_import_hook site install --args="--release"`
    * `python -m py_entry.main`
      * `/usr/bin/time -f "\n%e" python -m py_entry.main`
  * 方法3
    * `source ./.venv/bin/activate`
    * `/usr/bin/time -f "\n%e" maturin develop --release`
    * `/usr/bin/time -f "\n%e" python -m py_entry.main`
  * 方法4
    * `uv pip install whl_path`
    * `/usr/bin/time -f "\n%e" python -m py_entry.main`
  * check
    * `uvx ty check`
    * `uv run --no-sync cargo check`
  * format
    * `uvx ruff format`
    * `uv run --no-sync cargo fmt`

# 关于polars的异混淆点
  * Python API (PyPolars)
    * 方法：`df.with_columns(...)`
    * 模式：逻辑上**不可变**，返回**新对象**。
    * 性能：基于 Copy-on-Write (零拷贝) 实现高效。
    * 用法：必须使用**变量遮蔽**：`df = df.with_columns(...)`
  * Rust Eager API
    * 方法：`df.with_column(...)`
    * 模式：**原地修改 (In-place)**，接收 `&mut self`。
    * 性能：直接修改内存，绝对高效。
    * 用法：必须使用**可变变量**：`let mut df; df.with_column(...)?;`
  * 根本差异 (Key Takeaway)
    * Python 的不可变性是**高效的哲学**。
    * Rust Eager API 的 `with_column` 是个**特例**，采用 `&mut self` 以追求最高性能和操作简洁性。


