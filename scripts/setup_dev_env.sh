#!/bin/bash
# 开发环境快速初始化脚本
# 用于 git clone 后的首次设置

set -e

echo "========================================="
echo "🚀 初始化开发环境"
echo "========================================="
echo ""

# 1. 安装所有依赖（包括开发依赖）
echo "📦 步骤 1/3: 安装项目依赖..."
uv sync
echo "   依赖安装完成。"
echo ""

# 2. 安装 pre-commit hooks
echo "� 步骤 2/3: 安装 pre-commit hooks..."
if command -v git &> /dev/null && [ -d ".git" ]; then
    uv run pre-commit install
else
    echo "  ⚠️  未检测到 git 仓库，跳过 pre-commit 安装。"
fi
echo ""

# 3. 配置 nbstripout git filter
echo "🎯 步骤 3/3: 配置 nbstripout..."
if command -v git &> /dev/null && [ -d ".git" ]; then
    uv run nbstripout --install
else
    echo "  ⚠️  未检测到 git 仓库，跳过 nbstripout 配置。"
fi

echo ""
echo "========================================="
echo "✅ 开发环境初始化完成！"
echo "========================================="
echo ""
echo "📝 接下来的步骤："
echo ""
echo "现在你可以使用 'just' 命令来管理项目："
echo "  - just setup             # (已完成) 初始化环境"
echo "  - just run <path>        # 运行脚本 (自动重新编译 Rust)"
echo "  - just test              # 运行所有测试"
echo "  - just scanner-run       # 运行扫描器"
echo "  - just check             # 运行代码检查"
echo ""
echo "提示：由于移除了 maturin import hook，现在每次运行 python 命令"
echo "      都会自动检查并编译 Rust 代码 (通过 just invoke)。"
echo ""
