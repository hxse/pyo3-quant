"""sma_2tf 变体：启用跟踪止损 tsl。"""

from __future__ import annotations

from py_entry.strategy_hub.core.spec import SearchSpaceSpec
from py_entry.strategy_hub.search_spaces.sma_2tf.common import build_sma_2tf_bundle

STRATEGY_NAME = "sma_2tf_tsl"


def build_strategy_bundle() -> SearchSpaceSpec:
    """统一策略入口。"""

    return build_sma_2tf_bundle(
        strategy_name=STRATEGY_NAME,
        use_sl=False,
        use_tsl=True,
    )
