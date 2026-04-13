from __future__ import annotations

from dataclasses import dataclass

from py_entry.types import DataPack, SettingContainer, TemplateContainer


@dataclass(frozen=True, slots=True)
class RunnerSession:
    """Python runner 结果层共享上下文。"""

    data_pack: DataPack
    template_config: TemplateContainer
    engine_settings: SettingContainer
    enable_timing: bool = False
