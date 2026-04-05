"""live 策略桥接回调（统一 Spec 协议）。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, cast

import polars as pl

from py_entry.data_generator import DirectDataConfig, OhlcvDataFetchConfig
from py_entry.runner import Backtest
from py_entry.runner.setup_utils import (
    build_backtest_params,
    build_indicators_params,
    build_performance_params,
    build_signal_params,
)
from py_entry.strategy_hub.core.spec import (
    CommonStrategySpec,
    SearchSpaceSpec,
)
from py_entry.strategy_hub.core.spec_loader import load_spec
from py_entry.strategy_hub.registry import RegistryResolvedItem, load_registry_items
from py_entry.types import SingleParamSet

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .signal import SignalState
from .strategy_params import StrategyParams


class LiveStrategyCallbacks:
    """将 strategy_hub 注册结果适配为 trading_bot 回调。"""

    def __init__(
        self,
        inner: Callbacks,
    ):
        self._inner = inner
        registry_path = self._default_registry_path()
        if not registry_path.exists():
            raise ValueError(f"注册器文件不存在: {registry_path}")

        self._params_override_by_key: dict[tuple[str, str], SingleParamSet] = {}
        self._entry_meta_by_key: dict[tuple[str, str], RegistryResolvedItem] = {}
        self._entry_by_key: dict[tuple[str, str], CommonStrategySpec] = {}

        entries = self._load_entries_from_registry(str(registry_path))
        self._entries = entries

        self._params = [self._to_strategy_params(entry) for entry in entries]

    def _default_registry_path(self) -> Path:
        """返回唯一固定注册器路径。"""

        root = Path(__file__).resolve().parents[2]
        return root / "py_entry" / "strategy_hub" / "registry" / "live_registry.json"

    def _load_entries_from_registry(
        self, registry_path: str
    ) -> list[CommonStrategySpec]:
        """从注册器加载策略条目并构建参数覆盖。"""

        items = load_registry_items(registry_path)
        entries: list[CommonStrategySpec] = []

        for item in items:
            module_name = item.strategy_module.split(
                "py_entry.strategy_hub.search_spaces.", 1
            )[-1]
            spec = load_spec(module_name, "search")
            if not isinstance(spec, SearchSpaceSpec):
                raise TypeError(f"search 模块必须返回 SearchSpaceSpec: {module_name}")

            data_cfg = self._require_ohlcv_data_config(spec)
            updated_data_cfg = data_cfg.model_copy(
                update={"symbol": item.symbol, "base_data_key": item.base_data_key}
            )
            updated_spec = replace(spec, data_config=updated_data_cfg)

            key = (item.symbol, item.base_data_key)
            self._entry_by_key[key] = updated_spec
            self._entry_meta_by_key[key] = item
            self._params_override_by_key[key] = self._build_params_override(
                updated_spec,
                item.params,
                ctx=(
                    f"strategy={item.strategy_name}, symbol={item.symbol}, "
                    f"base_data_key={item.base_data_key}"
                ),
            )
            entries.append(updated_spec)

        return entries

    def _build_params_override(
        self,
        spec: CommonStrategySpec,
        params: dict[str, Any],
        *,
        ctx: str,
    ) -> SingleParamSet:
        """将日志参数映射为可执行 SingleParamSet。"""

        variant = spec.variant
        param_set = SingleParamSet(
            indicators=build_indicators_params(variant.indicators_params),
            signal=build_signal_params(variant.signal_params),
            backtest=build_backtest_params(variant.backtest_params),
            performance=build_performance_params(spec.performance_params),
        )

        indicators_payload = params.get("indicators")
        if isinstance(indicators_payload, dict):
            for data_key, groups in indicators_payload.items():
                if not isinstance(groups, dict):
                    continue
                for indicator_name, kv in groups.items():
                    if not isinstance(kv, dict):
                        continue
                    for param_name, value in kv.items():
                        try:
                            current = param_set.indicators[data_key][indicator_name][
                                param_name
                            ]
                        except KeyError as exc:
                            raise ValueError(
                                f"{ctx} 参数不存在: indicators.{data_key}.{indicator_name}.{param_name}"
                            ) from exc
                        current.value = float(value)

        signal_payload = params.get("signal")
        if isinstance(signal_payload, dict):
            for key, value in signal_payload.items():
                try:
                    current = param_set.signal[key]
                except KeyError as exc:
                    raise ValueError(f"{ctx} 参数不存在: signal.{key}") from exc
                current.value = float(value)

        backtest_payload = params.get("backtest")
        if isinstance(backtest_payload, dict):
            for key, value in backtest_payload.items():
                if not hasattr(param_set.backtest, key):
                    raise ValueError(f"{ctx} 参数不存在: backtest.{key}")
                current = getattr(param_set.backtest, key)
                if hasattr(current, "value"):
                    current.value = float(value)
                else:
                    setattr(param_set.backtest, key, value)

        return param_set

    def _require_ohlcv_data_config(
        self, entry: CommonStrategySpec
    ) -> OhlcvDataFetchConfig:
        """强约束：live 策略必须使用 OhlcvDataFetchConfig。"""

        if not isinstance(entry.data_config, OhlcvDataFetchConfig):
            raise ValueError(
                f"live 策略 data_config 必须是 OhlcvDataFetchConfig: {entry.name}"
            )
        return entry.data_config

    def _infer_settlement_currency(self, symbol: str) -> str:
        """从交易对推导结算币种。"""

        raw = symbol.strip()
        if ":" in raw:
            currency = raw.rsplit(":", 1)[1].strip()
            if currency:
                return currency
        if "/" in raw:
            currency = raw.split("/", 1)[1].split(":", 1)[0].strip()
            if currency:
                return currency
        raise ValueError(f"无法从 symbol 推导结算币种: {symbol}")

    def _to_strategy_params(self, entry: CommonStrategySpec) -> StrategyParams:
        """将策略配置转换为 bot 运行参数。"""

        # 中文注释：统一复用唯一的数据配置校验入口，避免双份逻辑漂移。
        data_cfg = self._require_ohlcv_data_config(entry)
        exchange_name = cast(Literal["binance", "kraken"], data_cfg.exchange_name)
        key = (data_cfg.symbol, data_cfg.base_data_key)
        meta = self._entry_meta_by_key.get(key)
        if meta is None:
            raise ValueError(
                f"缺少 registry meta: symbol={data_cfg.symbol}, base_data_key={data_cfg.base_data_key}"
            )

        return StrategyParams(
            base_data_key=data_cfg.base_data_key,
            symbol=data_cfg.symbol,
            exchange_name=exchange_name,
            market=data_cfg.market,
            mode=data_cfg.mode,
            position_size_pct=meta.position_size_pct,
            leverage=meta.leverage,
            settlement_currency=self._infer_settlement_currency(data_cfg.symbol),
        )

    def get_strategy_params(self) -> CallbackResult[list[StrategyParams]]:
        """返回 live 策略列表给机器人主循环。"""

        return CallbackResult(success=True, data=self._params)

    def run_backtest(
        self,
        params: StrategyParams,
        df: pl.DataFrame,
    ) -> CallbackResult[pl.DataFrame]:
        """使用 live 策略执行回测并返回 DataFrame。"""

        try:
            entry = self._entry_by_key.get((params.symbol, params.base_data_key))
            if entry is None:
                return CallbackResult(
                    success=False,
                    message=(
                        f"未找到 symbol={params.symbol}, "
                        f"base_data_key={params.base_data_key} 对应的 live 策略"
                    ),
                )

            source_df = (
                df.rename({"timestamp": "time"})
                if "timestamp" in df.columns and "time" not in df.columns
                else df
            )
            data_source = DirectDataConfig(
                data={params.base_data_key: source_df},
                base_data_key=params.base_data_key,
            )

            variant = entry.variant
            bt = Backtest(
                data_source=data_source,
                indicators=variant.indicators_params,
                signal=variant.signal_params,
                backtest=variant.backtest_params,
                signal_template=variant.signal_template,
                engine_settings=entry.engine_settings,
                performance=entry.performance_params,
            )
            params_override = self._params_override_by_key.get(
                (params.symbol, params.base_data_key)
            )
            run_result = bt.run(params_override=params_override)
            backtest_df = run_result.result.backtest_result
            if backtest_df is None:
                return CallbackResult(success=False, message="回测结果为空")
            return CallbackResult(success=True, data=backtest_df)
        except Exception as exc:
            return CallbackResult(
                success=False, message=f"live run_backtest 失败: {exc}"
            )

    def parse_signal(
        self,
        df: pl.DataFrame,
        params: StrategyParams,
        index: int = -1,
    ) -> CallbackResult[SignalState]:
        """透传 parse_signal 给 inner。"""

        return self._inner.parse_signal(df, params, index=index)

    def __getattr__(self, item: str) -> Any:
        """未覆写接口统一透传。"""

        return getattr(self._inner, item)
