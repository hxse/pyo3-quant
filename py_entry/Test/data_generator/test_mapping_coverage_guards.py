"""Phase 3：数据覆盖补拉与 mapping 防线测试。"""

from __future__ import annotations

from typing import Any

from py_entry.data_generator import OhlcvDataFetchConfig, generate_data_pack
from py_entry.io.types import RequestConfig


def _rows(times: list[int]) -> list[list[float]]:
    """构造最小 OHLCV 行数据。"""
    return [[t, 1.0, 1.0, 1.0, 1.0, 1.0] for t in times]


def _build_fetch_cfg(
    *,
    timeframes: list[str],
    base_data_key: str,
    since: int,
    limit: int,
    end_backfill_min_step_bars: int = 5,
) -> OhlcvDataFetchConfig:
    """构建最小 fetched 配置。"""
    return OhlcvDataFetchConfig(
        config=RequestConfig.create(
            username="u",
            password="p",
            server_url="http://x",
            max_retries=0,
        ),
        exchange_name="binance",
        market="future",
        symbol="BTC/USDT",
        timeframes=timeframes,
        since=since,
        limit=limit,
        enable_cache=True,
        enable_test=True,
        mode="sandbox",
        base_data_key=base_data_key,
        end_backfill_min_step_bars=end_backfill_min_step_bars,
    )


def test_start_side_backfill_moves_since_until_cover(monkeypatch):
    """start 侧补拉：source_start > base_start 时必须前移 since 重拉。"""
    calls: list[tuple[str, int | None, int | None]] = []

    def fake_get_ohlcv_data(req) -> Any:
        calls.append((req.timeframe, req.since, req.limit))
        if req.timeframe == "15m":
            # 中文注释：base 时间边界固定在 [2h, 2h15m, 2h30m]。
            return _rows([7_200_000, 8_100_000, 9_000_000])
        if req.timeframe == "1h":
            # 中文注释：首轮 start 不覆盖，前移 since 后返回可覆盖数据。
            if req.since == 7_200_000:
                return _rows([10_800_000, 14_400_000, 18_000_000])
            return _rows([7_200_000, 10_800_000, 14_400_000])
        raise AssertionError(f"unexpected timeframe={req.timeframe}")

    monkeypatch.setattr(
        "py_entry.data_generator.data_generator.get_ohlcv_data",
        fake_get_ohlcv_data,
    )

    cfg = _build_fetch_cfg(
        timeframes=["15m", "1h"],
        base_data_key="ohlcv_15m",
        since=7_200_000,
        limit=3,
    )
    out = generate_data_pack(cfg)

    # 中文注释：验证 start 补拉触发了至少 2 次 1h 请求。
    calls_1h = [c for c in calls if c[0] == "1h"]
    assert len(calls_1h) >= 2
    assert out.source["ohlcv_1h"]["time"][0] <= out.source["ohlcv_15m"]["time"][0]


def test_end_side_backfill_increases_limit_with_min_step(monkeypatch):
    """end 侧补拉：不足覆盖时按 max(missing, min_step) 增加 limit。"""
    calls: list[tuple[str, int | None, int | None]] = []

    def fake_get_ohlcv_data(req) -> Any:
        calls.append((req.timeframe, req.since, req.limit))
        if req.timeframe == "15m":
            return _rows([0, 900_000, 1_800_000, 2_700_000, 3_600_000])
        if req.timeframe == "1h":
            # 中文注释：首轮仅返回 1 根，触发 end 补拉；补拉后返回 2 根满足覆盖。
            if (req.limit or 0) <= 5:
                return _rows([0])
            return _rows([0, 3_600_000])
        raise AssertionError(f"unexpected timeframe={req.timeframe}")

    monkeypatch.setattr(
        "py_entry.data_generator.data_generator.get_ohlcv_data",
        fake_get_ohlcv_data,
    )

    cfg = _build_fetch_cfg(
        timeframes=["15m", "1h"],
        base_data_key="ohlcv_15m",
        since=0,
        limit=5,
        end_backfill_min_step_bars=5,
    )
    out = generate_data_pack(cfg)

    calls_1h = [c for c in calls if c[0] == "1h"]
    # 中文注释：首轮 limit=5，下一轮至少 +5（而不是 +1）。
    assert len(calls_1h) >= 2
    assert calls_1h[0][2] == 5
    second_limit = calls_1h[1][2]
    assert isinstance(second_limit, int)
    assert second_limit >= 10

    # 中文注释：最终仍由 build_time_mapping 校验，容器应成功构建。
    base_end = int(out.source["ohlcv_15m"]["time"][-1])
    src_end = int(out.source["ohlcv_1h"]["time"][-1])
    assert src_end + 3_600_000 > base_end
