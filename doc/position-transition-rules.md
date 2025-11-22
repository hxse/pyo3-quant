# 仓位状态转换白名单规则

## 术语定义
- `0` = None (无仓位)
- `1` = EnterLong (进多)
- `2` = HoldLong (持多)
- `3` = ExitLong (平多)
- `4` = ExitShortEnterLong (平空进多/反手做多)
- `-1` = EnterShort (进空)
- `-2` = HoldShort (持空)
- `-3` = ExitShort (平空)
- `-4` = ExitLongEnterShort (平多进空/反手做空)

## 白名单：允许的状态转换

### 从 None (0) 可以转换到：
- `0 → 0` ✅ (保持无仓位)
- `0 → 1` ✅ (进多)
- `0 → -1` ✅ (进空)

### 从 EnterLong (1) 可以转换到：
- `1 → 2` ✅ (进多 → 持多)

### 从 HoldLong (2) 可以转换到：
- `2 → 2` ✅ (持多 → 持多)
- `2 → 3` ✅ (持多 → 平多)
- `2 → -4` ✅ (持多 → 平多进空/反手)

### 从 ExitLong (3) 可以转换到：
- `3 → 0` ✅ (平多 → 无仓位)
- `3 → 1` ✅ (平多 → 进多，允许立即再次进场)
- `3 → -1` ✅ (平多 → 进空，允许立即反向进场)

### 从 ExitShortEnterLong (4) 可以转换到：
- `4 → 2` ✅ (反手做多 → 持多)
- `4 → -4` ✅ (反手做多 → 反手做空)

### 从 EnterShort (-1) 可以转换到：
- `-1 → -2` ✅ (进空 → 持空)

### 从 HoldShort (-2) 可以转换到：
- `-2 → -2` ✅ (持空 → 持空)
- `-2 → -3` ✅ (持空 → 平空)
- `-2 → 4` ✅ (持空 → 平空进多/反手)

### 从 ExitShort (-3) 可以转换到：
- `-3 → 0` ✅ (平空 → 无仓位)
- `-3 → 1` ✅ (平空 → 进多，允许立即反向进场)
- `-3 → -1` ✅ (平空 → 进空，允许立即再次进场)

### 从 ExitLongEnterShort (-4) 可以转换到：
- `-4 → -2` ✅ (反手做空 → 持空)
- `-4 → 4` ✅ (反手做空 → 反手做多)

## 状态转换白名单矩阵

```
当前\下一个  0   1   2   3   4  -1  -2  -3  -4
    0       ✅  ✅  ❌  ❌  ❌  ✅  ❌  ❌  ❌
    1       ❌  ❌  ✅  ❌  ❌  ❌  ❌  ❌  ❌
    2       ❌  ❌  ✅  ✅  ❌  ❌  ❌  ❌  ✅
    3       ✅  ✅  ❌  ❌  ❌  ✅  ❌  ❌  ❌
    4       ❌  ❌  ✅  ❌  ❌  ❌  ❌  ❌  ✅
   -1       ❌  ❌  ❌  ❌  ❌  ❌  ✅  ❌  ❌
   -2       ❌  ❌  ❌  ❌  ✅  ❌  ✅  ✅  ❌
   -3       ✅  ✅  ❌  ❌  ❌  ✅  ❌  ❌  ❌
   -4       ❌  ❌  ❌  ❌  ✅  ❌  ✅  ❌  ❌
```

## 验证逻辑（Rust实现）

```rust
pub fn is_valid_transition(prev: i8, curr: i8, allow_reversal: bool) -> bool {
    match (prev, curr) {
        // None (0)
        (0, 0 | 1 | -1) => true,

        // EnterLong (1)
        (1, 2) => true,

        // HoldLong (2)
        (2, 2 | 3 | -4) => true,

        // ExitLong (3)
        (3, 0 | 1 | -1) => true,

        // ExitShortEnterLong (4)
        (4, 2 | -4) => true,

        // EnterShort (-1)
        (-1, -2) => true,

        // HoldShort (-2)
        (-2, -2 | -3 | 4) => true,

        // ExitShort (-3)
        (-3, 0 | 1 | -1) => true,

        // ExitLongEnterShort (-4)
        (-4, -2 | 4) => true,

        // 其他所有组合都不允许
        _ => false,
    }
}
```

## 验证逻辑（Python实现）

```python
def is_valid_transition(prev: int, curr: int, allow_reversal: bool = True) -> bool:
    """验证仓位状态转换是否合法"""
    valid_transitions = {
        0: {0, 1, -1},           # None
        1: {2},                  # EnterLong
        2: {2, 3, -4},           # HoldLong
        3: {0, 1, -1},           # ExitLong
        4: {2, -4},              # ExitShortEnterLong
        -1: {-2},                # EnterShort
        -2: {-2, -3, 4},         # HoldShort
        -3: {0, 1, -1},          # ExitShort
        -4: {-2, 4},             # ExitLongEnterShort
    }

    return curr in valid_transitions.get(prev, set())
