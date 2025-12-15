#!/bin/bash
# 开发环境快速初始化脚本
# 用于 git clone 后的首次设置

set -e

echo "========================================="
echo "🚀 初始化开发环境"
echo "========================================="
echo ""

# 1. 安装所有依赖（包括开发依赖）
echo "📦 步骤 1/5: 安装项目依赖..."
uv sync

echo ""

# 2. 检查并提示安装 patchelf（maturin_import_hook 需要）
echo "🔍 步骤 2/5: 检查系统依赖..."
if ! command -v patchelf &> /dev/null; then
    echo "  ⚠️  未检测到 patchelf，maturin_import_hook 需要此工具"
    echo "  请运行: sudo apt install patchelf"
    echo "  暂时跳过，继续下一步..."
else
    echo "  ✓ patchelf 已安装"
fi

echo ""

# 3. 配置 maturin_import_hook（用于开发时自动编译 Rust 模块）
echo "🦀 步骤 3/5: 配置 Rust 模块开发环境..."
if command -v patchelf &> /dev/null; then
    echo "  正在安装 maturin_import_hook..."
    uv run python -m maturin_import_hook site install --args="--release" || {
        echo "  ⚠️  maturin_import_hook 安装失败（可能需要先编译 Rust 模块）"
        echo "  你可以稍后手动运行: uv run python -m maturin_import_hook site install --args=\"--release\""
    }
else
    echo "  ⚠️  跳过 maturin_import_hook 配置（需要先安装 patchelf）"
    echo "  安装 patchelf 后运行: uv run python -m maturin_import_hook site install --args=\"--release\""
fi

echo ""

# 4. 安装 pre-commit hooks
echo "🔧 步骤 4/5: 安装 pre-commit hooks..."
uv run pre-commit install

echo ""

# 5. 配置 nbstripout git filter
echo "🎯 步骤 5/5: 配置 nbstripout..."
uv run nbstripout --install

echo ""
echo "========================================="
echo "✅ 开发环境初始化完成！"
echo "========================================="
echo ""
echo "📝 接下来的步骤："

# 检查是否需要提示安装 patchelf
if ! command -v patchelf &> /dev/null; then
    echo ""
    echo "⚠️  重要：请安装 patchelf（Rust 模块开发必需）："
    echo "    sudo apt install patchelf"
    echo ""
    echo "   然后运行:"
    echo "    uv run python -m maturin_import_hook site install --args=\"--release\""
fi

echo ""
echo "现在你可以："
echo "  - 开始编辑代码"
echo "  - 每次 commit 会自动清理 notebook 输出"
echo "  - 修改 Rust 代码后会自动重新编译（maturin_import_hook）"
echo ""
echo "常用命令："
echo "  - uv run python -m py_entry.example.basic_backtest  # 运行示例"
echo "  - uv run pytest py_entry/Test                       # 运行测试"
echo "  - uv run nbstripout <file>                          # 手动清理 notebook"
echo "  - uv run pre-commit run -a                          # 手动运行所有检查"
echo "  - uvx ruff format                                   # 格式化 Python 代码"
echo "  - cargo fmt                                         # 格式化 Rust 代码"
echo ""
echo "📚 详细文档："
echo "  - doc/Dev_Setup_Notes.md       # 开发环境详细说明"
echo "  - doc/Notebook_Cleanup.md      # Notebook 清理配置"
echo ""
