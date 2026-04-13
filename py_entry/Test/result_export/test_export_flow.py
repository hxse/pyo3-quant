from pathlib import Path
from unittest.mock import patch
from py_entry.io import SaveConfig
from py_entry.runner import FormatResultsConfig


def test_export_flow(runner_with_results, tmp_path):
    runner = runner_with_results
    bundle = runner.prepare_export(FormatResultsConfig(dataframe_format="csv"))

    assert bundle.buffers, "buffers should be populated"
    assert bundle.zip_buffer is not None, "zip_buffer should be populated"
    assert bundle.chart_config is not None, "chart_config should be generated"

    # Check for chartConfig.json
    has_chart_config = any(p.name == "chartConfig.json" for p, _ in bundle.buffers)
    assert has_chart_config, "chartConfig.json not found in export buffers"

    # --- 2. Verify save_results ---
    # Use tmp_path fixture for automatic cleanup
    output_path = tmp_path / "verify_test_export_flow"

    save_config = SaveConfig(output_dir=str(output_path))

    with patch(
        "py_entry.io.result_export.validate_output_path",
        side_effect=lambda x: Path(x),
    ) as _:
        bundle.save(save_config)

    assert output_path.exists(), "Output directory should exist"
    assert (output_path / "chartConfig.json").exists(), (
        "chartConfig.json should exist on disk"
    )
    assert (output_path / "backtest_results").exists(), (
        "backtest_results dir should exist"
    )
