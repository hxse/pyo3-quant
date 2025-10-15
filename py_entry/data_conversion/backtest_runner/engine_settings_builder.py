from abc import ABC, abstractmethod

from py_entry.data_conversion.input import EngineSettings, ExecutionStage


class BaseEngineSettingsBuilder(ABC):
    @abstractmethod
    def build_engine_settings(self) -> EngineSettings:
        pass


class DefaultEngineSettingsBuilder(BaseEngineSettingsBuilder):
    def build_engine_settings(self) -> EngineSettings:
        return EngineSettings(
            execution_stage=ExecutionStage.PERFORMANCE,
            return_only_final=False,
            skip_risk=True,
        )
