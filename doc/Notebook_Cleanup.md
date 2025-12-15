# Jupyter Notebook 自动清理配置

本项目使用 `pre-commit` + `nbstripout` 自动清理 Jupyter Notebook 输出，确保提交到 GitHub 的代码干净整洁。

## 🚀 首次设置（适用于 clone 项目后）

```bash
# 方式 1: 使用自动化脚本（推荐）
bash scripts/setup_dev_env.sh

# 方式 2: 手动设置
uv sync                           # 安装所有依赖
uv run pre-commit install         # 安装 git hooks
uv run nbstripout --install       # 配置 git filter（重要！）
```

就这么简单！✨

## 💡 什么是 Notebook 清理？

**清理前的 notebook（不应该提交）**：
- ❌ 包含执行输出（print、图表等）
- ❌ 包含执行计数（`[1]`, `[2]` 等）
- ❌ 包含大量元数据（kernelspec、widgets state 等）
- ❌ 文件体积大，难以进行代码审查

**清理后的 notebook（应该提交）**：
- ✅ 只保留代码单元格的源代码
- ✅ 移除所有输出
- ✅ 移除执行计数
- ✅ 文件体积小，方便 git diff
- ✅ 便于代码审查和协作

**举例**：

清理前的单元格：
```json
{
  "cell_type": "code",
  "execution_count": 42,
  "outputs": [
    {
      "name": "stdout",
      "output_type": "stream",
      "text": "Hello World\n"
    }
  ],
  "source": ["print('Hello World')"]
}
```

清理后的单元格：
```json
{
  "cell_type": "code",
  "execution_count": null,
  "outputs": [],
  "source": ["print('Hello World')"]
}
```

这样 git diff 会更清晰，只关注代码变更，而不是输出变更。


## 📝 工作流程

设置完成后，每次 `git commit` 时会自动：

1. 清理所有 `.ipynb` 文件的输出
2. 移除执行计数
3. 清理不必要的元数据
4. 只提交纯净的代码

## 🛡️ 双重保护机制

本项目采用**双重保护**确保 notebook 输出不会被提交：

### 1️⃣ Git Filter（第一道防线）
- 在 `git add` 时自动清理
- **如果没配置会报错** ✅ 这是好事！强制所有开发者正确配置
- 配置方式：`uv run nbstripout --install`

### 2️⃣ Pre-commit Hook（第二道防线）
- 在 `git commit` 时再次检查和清理
- 即使第一道防线失效也能兜底
- 配置方式：`uv run pre-commit install`

**为什么需要双重保护？**
- 更安全：两层检查确保不会遗漏
- 强制性：git filter 报错能提醒开发者配置环境
- 灵活性：pre-commit 可以运行更多检查

## 🛠️ 常用命令

```bash
# 手动清理单个 notebook
uv run nbstripout demo.ipynb

# 手动清理所有 notebook
find . -name "*.ipynb" | xargs uv run nbstripout

# 手动运行所有 pre-commit 检查
uv run pre-commit run --all-files

# 跳过 pre-commit（不推荐）
git commit --no-verify
```

## ❓ 常见问题

### Q: 我需要在每台机器上都运行设置脚本吗？

**A**: **是的，必须运行！**

每次 clone 项目后需要运行一次：
```bash
bash scripts/setup_dev_env.sh
```

这是因为 git hooks 和 git filter 配置存储在本地 `.git/` 目录，不会被 git 追踪。

### Q: 如果我忘记运行设置脚本会怎样？

**A**: 当你尝试 `git add *.ipynb` 时会报错：

```bash
error: external filter 'nbstripout' failed
fatal: demo.ipynb: smudge filter nbstripout failed
```

**这是好事！** ✅ 它提醒你需要先配置环境。运行：
```bash
bash scripts/setup_dev_env.sh
```

### Q: 为什么要强制报错，而不是自动跳过？

**A**: 强制报错的好处：

1. ✅ **确保一致性**：所有开发者都必须正确配置
2. ✅ **防止错误提交**：不会因为忘记配置而提交带输出的 notebook
3. ✅ **提醒作用**：明确告诉开发者需要做什么

如果不报错，可能会有人提交带输出的 notebook 污染仓库。

### Q: 双重保护如何工作？

**A**: 工作流程：

```
修改 notebook
    ↓
git add demo.ipynb  ← Git Filter 清理（第一道防线）
    ↓
git commit          ← Pre-commit Hook 检查（第二道防线）
    ↓
✅ 提交干净的代码
```

- Git Filter：实时清理，如果没配置会报错
- Pre-commit Hook：提交前最后检查

### Q: 我可以禁用自动清理吗？

**A**: 可以，但**强烈不推荐**：

```bash
# 跳过 pre-commit（不推荐）
git commit --no-verify

# 但无法跳过 git filter，除非你禁用 .gitattributes
```

### Q: Git Filter 和 Pre-commit 有什么区别？

**A**:

| 特性 | Git Filter | Pre-commit Hook |
|------|-----------|----------------|
| 触发时机 | `git add` | `git commit` |
| 能否跳过 | 不能 | 可以（`--no-verify`） |
| 配置位置 | `.git/config` | `.git/hooks/` |
| 报错行为 | 没配置会报错 | 没配置不会报错 |
| 作用范围 | 只处理指定文件 | 可以运行多种检查 |

**推荐同时使用两者**，双重保险更安全。

## 📚 技术细节

- **依赖管理**: `pre-commit` 和 `nbstripout` 已添加到 `pyproject.toml` 的开发依赖中
- **配置文件**: `.pre-commit-config.yaml` 配置了自动清理规则
- **属性文件**: `.gitattributes` 配置了 notebook 的 diff 显示方式
