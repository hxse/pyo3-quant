from pathlib import Path
from unittest.mock import patch
from py_entry.io import SaveConfig


def test_export_flow(runner_with_results, tmp_path):
    runner = runner_with_results

    # Ensure runner has results
    print("Running backtest... (Performed by fixture)")

    # --- 1. Verify format_results_for_export ---
    print("Formatting results for export...")
    runner.format_results_for_export(
        export_index=0, dataframe_format="csv", add_index=True
    )

    # Assertions
    assert runner.export_buffers is not None, "export_buffers should be populated"
    assert runner.export_zip_buffer is not None, "export_zip_buffer should be populated"
    assert runner.chart_config is not None, "chart_config should be generated"

    print(f"Export buffers count: {len(runner.export_buffers)}")
    print(f"Zip buffer size: {len(runner.export_zip_buffer)} bytes")

    # Check for chartConfig.json
    has_chart_config = any(
        p.name == "chartConfig.json" for p, _ in runner.export_buffers
    )
    assert has_chart_config, "chartConfig.json not found in export buffers"
    print("✅ chartConfig.json found in buffers")

    # --- 2. Verify save_results ---
    # Use tmp_path fixture for automatic cleanup
    output_path = tmp_path / "verify_test_export_flow"

    print(f"Saving results to {output_path}...")
    save_config = SaveConfig(output_dir=str(output_path))

    with patch(
        "py_entry.io.result_export.validate_output_path",
        side_effect=lambda x: Path(x),
    ) as _:
        runner.save_results(save_config)

    assert output_path.exists(), "Output directory should exist"
    assert (output_path / "chartConfig.json").exists(), (
        "chartConfig.json should exist on disk"
    )
    assert (output_path / "backtest_results").exists(), (
        "backtest_results dir should exist"
    )

    print("✅ Files saved successfully")
    print("Verification Passed!")
