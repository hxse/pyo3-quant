"""searcher_args 参数解析约束测试。"""

from __future__ import annotations

import pytest

from py_entry.strategy_hub.core.searcher_args import parse_csv


def test_parse_csv_keeps_input_order() -> None:
    """无重复时保持输入顺序。"""

    assert parse_csv("BTC/USDT, ETH/USDT ,SOL/USDT") == [
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
    ]


def test_parse_csv_rejects_duplicate_items() -> None:
    """重复 symbols 必须显式报错，禁止静默去重。"""

    with pytest.raises(ValueError, match="重复项"):
        parse_csv("BTC/USDT,BTC/USDT")
