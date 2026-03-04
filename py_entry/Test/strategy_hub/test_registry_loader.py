"""registry loader 约束测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from py_entry.strategy_hub.registry.loader import load_registry_items


def _write_json(path: Path, payload: object) -> None:
    """写入测试 JSON。"""

    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_backtest_log(
    *,
    path: Path,
    strategy_name: str,
    strategy_module: str,
    symbol: str,
) -> None:
    """写入最小 backtest 日志载荷。"""

    _write_json(
        path,
        {
            "results": [
                {
                    "strategy_name": strategy_name,
                    "strategy_version": "1.0.0",
                    "strategy_module": strategy_module,
                    "symbol": symbol,
                    "mode": "backtest",
                    "base_data_key": "ohlcv_15m",
                    "backtest_default_params": {},
                    "backtest_start_time_ms": 1,
                }
            ]
        },
    )


def test_load_registry_items_should_reject_duplicate_registered_strategy_name(
    tmp_path: Path,
) -> None:
    """同名策略映射到不同模块时必须报错。"""

    log_a = tmp_path / "a.json"
    log_b = tmp_path / "b.json"
    _write_backtest_log(
        path=log_a,
        strategy_name="dup_strategy",
        strategy_module="py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf",
        symbol="BTC/USDT",
    )
    _write_backtest_log(
        path=log_b,
        strategy_name="dup_strategy",
        strategy_module="py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf_tsl",
        symbol="ETH/USDT",
    )

    registry_path = tmp_path / "registry.json"
    _write_json(
        registry_path,
        [
            {
                "log_path": "a.json",
                "symbol": "BTC/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
            {
                "log_path": "b.json",
                "symbol": "ETH/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
        ],
    )

    with pytest.raises(ValueError, match="同名策略必须映射到同一 strategy_module"):
        load_registry_items(registry_path)


def test_load_registry_items_should_allow_unique_registered_strategy_name(
    tmp_path: Path,
) -> None:
    """已注册条目策略名唯一时应成功加载。"""

    log_a = tmp_path / "a.json"
    log_b = tmp_path / "b.json"
    _write_backtest_log(
        path=log_a,
        strategy_name="sma_2tf",
        strategy_module="py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf",
        symbol="BTC/USDT",
    )
    _write_backtest_log(
        path=log_b,
        strategy_name="sma_2tf_tsl",
        strategy_module="py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf_tsl",
        symbol="ETH/USDT",
    )

    registry_path = tmp_path / "registry.json"
    _write_json(
        registry_path,
        [
            {
                "log_path": "a.json",
                "symbol": "BTC/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
            {
                "log_path": "b.json",
                "symbol": "ETH/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
        ],
    )

    resolved = load_registry_items(registry_path)
    assert len(resolved) == 2


def test_load_registry_items_should_allow_same_strategy_multi_symbol(
    tmp_path: Path,
) -> None:
    """同名同模块的多品种部署应允许。"""

    log_a = tmp_path / "a.json"
    log_b = tmp_path / "b.json"
    strategy_module = "py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf"
    _write_backtest_log(
        path=log_a,
        strategy_name="sma_2tf",
        strategy_module=strategy_module,
        symbol="BTC/USDT",
    )
    _write_backtest_log(
        path=log_b,
        strategy_name="sma_2tf",
        strategy_module=strategy_module,
        symbol="ETH/USDT",
    )

    registry_path = tmp_path / "registry.json"
    _write_json(
        registry_path,
        [
            {
                "log_path": "a.json",
                "symbol": "BTC/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
            {
                "log_path": "b.json",
                "symbol": "ETH/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            },
        ],
    )

    resolved = load_registry_items(registry_path)
    assert len(resolved) == 2


def test_load_registry_items_should_reject_ambiguous_symbol_mode_match(
    tmp_path: Path,
) -> None:
    """同一日志内同 (symbol, mode) 出现多条记录时必须报错。"""

    log_path = tmp_path / "a.json"
    _write_json(
        log_path,
        {
            "results": [
                {
                    "strategy_name": "sma_2tf",
                    "strategy_version": "1.0.0",
                    "strategy_module": "py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf",
                    "symbol": "BTC/USDT",
                    "mode": "backtest",
                    "base_data_key": "ohlcv_15m",
                    "backtest_default_params": {},
                    "backtest_start_time_ms": 1,
                },
                {
                    "strategy_name": "sma_2tf",
                    "strategy_version": "1.0.0",
                    "strategy_module": "py_entry.strategy_hub.search_spaces.sma_2tf.sma_2tf",
                    "symbol": "BTC/USDT",
                    "mode": "backtest",
                    "base_data_key": "ohlcv_15m",
                    "backtest_default_params": {},
                    "backtest_start_time_ms": 2,
                },
            ]
        },
    )

    registry_path = tmp_path / "registry.json"
    _write_json(
        registry_path,
        [
            {
                "log_path": "a.json",
                "symbol": "BTC/USDT",
                "mode": "backtest",
                "enabled": True,
                "position_size_pct": 0.5,
                "leverage": 1,
            }
        ],
    )

    with pytest.raises(ValueError, match="匹配日志条目必须唯一"):
        load_registry_items(registry_path)
