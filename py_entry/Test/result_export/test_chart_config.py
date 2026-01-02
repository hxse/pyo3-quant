import zipfile
import json
import io

from py_entry.types import ChartConfig
from py_entry.runner import FormatResultsConfig


def test_chart_config_generation(runner_with_results):
    runner = runner_with_results

    # 1. Generate Config
    print(
        f"DEBUG: Before generate, data={runner.data_dict is not None}, results={len(runner.results) if runner.results else 0}"
    )
    # Using unified export method which generates chart config internally

    runner.format_results_for_export(
        FormatResultsConfig(export_index=0, dataframe_format="csv", add_index=True)
    )
    print(f"DEBUG: After generate, config={runner.chart_config}")

    if runner.results and runner.results[0].indicators:
        print(f"DEBUG: Indicators keys: {list(runner.results[0].indicators.keys())}")

    config = runner.chart_config
    assert config is not None
    assert isinstance(config, ChartConfig)

    # 2. Verify Structure (新架构: [Grid Slots][Panes][Series])
    # 预期结构:
    # Grid Slot 0: ohlcv_15m (包含多个 Panes)
    #   - Pane 0: Candle + Volume + BBands
    #   - Pane 1: bbands_bandwidth
    #   - Pane 2: bbands_percent
    # Grid Slot 1: ohlcv_1h (包含多个 Panes)
    #   - Pane 0: Candle + Volume
    #   - Pane 1: RSI + HLines
    # Grid Slot 2: ohlcv_4h (包含多个 Panes)
    #   - Pane 0: Candle + Volume + SMA

    # 检查是否有 Grid Slots
    assert len(config.chart) >= 2, (
        f"Expected at least 2 grid slots, got {len(config.chart)}"
    )

    # --- Grid Slot 0: ohlcv_15m ---
    grid_slot_0 = config.chart[0]
    assert len(grid_slot_0) >= 1, "Grid slot 0 should have at least 1 pane"

    # Pane 0 应该包含 Candle
    pane_0 = grid_slot_0[0]
    assert isinstance(pane_0, list), "Pane should be a list of series"
    assert len(pane_0) > 0, "Pane 0 should have at least one series"
    assert pane_0[0].type == "candle", (
        f"First series should be candle, got {pane_0[0].type}"
    )

    # 辅助函数：在所有 series 中查找指标
    def has_indicator_in_panes(panes, name_part):
        """在多个 panes 中查找包含指定名称的指标"""
        for pane in panes:
            for item in pane:
                if item.dataName:
                    names = (
                        item.dataName
                        if isinstance(item.dataName, list)
                        else [item.dataName]
                    )
                    if any(name_part in col for col in names):
                        return True
        return False

    # 检查 BBands 是否存在于 Grid Slot 0 的某个 pane 中
    assert has_indicator_in_panes(grid_slot_0, "bbands"), (
        "BBands indicator not found in grid slot 0"
    )

    # --- 查找包含 RSI 的 Grid Slot ---
    rsi_grid_slot = None
    rsi_grid_index = -1
    for idx, grid_slot in enumerate(config.chart):
        if has_indicator_in_panes(grid_slot, "rsi"):
            rsi_grid_slot = grid_slot
            rsi_grid_index = idx
            break

    assert rsi_grid_slot is not None, "RSI grid slot not found"
    assert rsi_grid_index >= 1, (
        f"RSI should be in slot 1 or later, found at {rsi_grid_index}"
    )

    # --- 在 RSI Grid Slot 中查找 HLines ---
    # 收集所有 panes 中的 hline series
    hlines = []
    for pane in rsi_grid_slot:
        hlines.extend([item for item in pane if item.type == "hline"])

    assert len(hlines) >= 3, f"Expected at least 3 hlines, found {len(hlines)}"

    vals = sorted([item.hLineOpt.value for item in hlines if item.hLineOpt is not None])
    # 应该包含 RSI 的关键水平线: 30, 50, 70
    assert 30 in vals, f"Expected RSI lower line (30) in {vals}"
    assert 50 in vals, f"Expected RSI center line (50) in {vals}"
    assert 70 in vals, f"Expected RSI upper line (70) in {vals}"

    # 3. Verify ZIP
    zip_bytes = runner.export_zip_buffer
    assert zip_bytes is not None
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # Check files exist
        files = zf.namelist()
        assert "chartConfig.json" in files
        # 检查是否包含数据文件 (名称取决于实际生成，通常是 data_dict/source_ohlcv_15m.csv)
        assert any("data_dict/source_ohlcv_15m" in f for f in files)

        # Check content of config
        with zf.open("chartConfig.json") as f:
            saved_config = json.load(f)
            assert saved_config["template"] == config.template
