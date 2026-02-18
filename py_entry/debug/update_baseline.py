import json
from pathlib import Path
from py_entry.strategies import get_strategy
from py_entry.runner import Backtest


def regenerate_baseline():
    print("Generating new performance.json baseline...")

    strategy = get_strategy("reversal_extreme")

    runner = Backtest(
        data_source=strategy.data_config,
        indicators=strategy.indicators_params,
        signal=strategy.signal_params,
        backtest=strategy.backtest_params,
        signal_template=strategy.signal_template,
        engine_settings=strategy.engine_settings,
    )
    result = runner.run()

    if not result.summary:
        print("Error: No backtest results generated.")
        return

    current_performance = result.summary.performance

    # Path to performance.json
    json_path = Path(
        "/home/hxse/pyo3-quant/py_entry/Test/backtest/demo_sma_crossover/performance.json"
    )

    with open(json_path, "w") as f:
        json.dump(current_performance, f, indent=4)

    print(f"Updated {json_path}")
    print("New performance metrics:")
    print(json.dumps(current_performance, indent=4))


if __name__ == "__main__":
    regenerate_baseline()
