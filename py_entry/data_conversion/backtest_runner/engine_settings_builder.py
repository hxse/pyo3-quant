from abc import ABC, abstractmethod

from py_entry.data_conversion.input import SettingContainer, ExecutionStage


class BaseEngineSettingsBuilder(ABC):
    @abstractmethod
    def build_engine_settings(self) -> SettingContainer:
        pass


class DefaultEngineSettingsBuilder(BaseEngineSettingsBuilder):
    def build_engine_settings(self) -> SettingContainer:
        return SettingContainer(
            execution_stage=ExecutionStage.PERFORMANCE,
            return_only_final=False,
        )
