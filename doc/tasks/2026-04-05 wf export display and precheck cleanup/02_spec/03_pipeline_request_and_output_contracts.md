# 内部 Pipeline Request / Output 契约

## 1. 本文冻结的真值

本文只冻结内部单次执行主链的两个真值对象：

1. `PipelineRequest`
2. `PipelineOutput`

`03-10` 已冻结的 warmup / window / stitched 主算法不在本文展开；single / batch 的公开 `stop_stage × artifact_retention` 语义也以 [02_public_execution_settings.md](./02_public_execution_settings.md) 为准。

## 2. `PipelineRequest`

公开 `SettingContainer` 会先被编译成严格的 `PipelineRequest`，内部执行器只消费这个对象。

正式内部请求固定为：

```text
PipelineRequest =
    ScratchToIndicator
    | ScratchToSignalsStopStageOnly
    | ScratchToSignalsAllCompletedStages
    | ScratchToBacktestStopStageOnly
    | ScratchToBacktestAllCompletedStages
    | ScratchToPerformanceStopStageOnly
    | ScratchToPerformanceAllCompletedStages
    | SignalsToBacktestStopStageOnly {
        signals: DataFrame,
      }
    | SignalsToBacktestAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
      }
    | SignalsToPerformanceStopStageOnly {
        signals: DataFrame,
      }
    | SignalsToPerformanceAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
      }
    | BacktestToPerformanceStopStageOnly {
        backtest: DataFrame,
      }
    | BacktestToPerformanceAllCompletedStages {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
      }
```

约束如下：

1. `indicators_raw` 表示 raw indicators，不携带 `time` 列。
2. `signals` 与 `backtest` 的高度必须等于 `data.mapping.height()`。
3. `BacktestTo*` 只用于 performance 续算。
4. 本任务不定义 `FromIndicators` 变体。

## 3. 公开设置到内部请求的编译矩阵

这张表与 [02_public_execution_settings.md](./02_public_execution_settings.md) 第 3 节中的公开结果矩阵描述的是同一组 `SettingContainer { stop_stage, artifact_retention }` 组合。

区别只在于：

1. 那里定义公开结果必须保留什么。
2. 这里定义这些公开组合必须被编译成哪个 `PipelineRequest`。

固定编译关系如下：

1. `SettingContainer { stop_stage: Indicator, artifact_retention: AllCompletedStages }` -> `ScratchToIndicator`
2. `SettingContainer { stop_stage: Indicator, artifact_retention: StopStageOnly }` -> `ScratchToIndicator`
3. `SettingContainer { stop_stage: Signals, artifact_retention: AllCompletedStages }` -> `ScratchToSignalsAllCompletedStages`
4. `SettingContainer { stop_stage: Signals, artifact_retention: StopStageOnly }` -> `ScratchToSignalsStopStageOnly`
5. `SettingContainer { stop_stage: Backtest, artifact_retention: AllCompletedStages }` -> `ScratchToBacktestAllCompletedStages`
6. `SettingContainer { stop_stage: Backtest, artifact_retention: StopStageOnly }` -> `ScratchToBacktestStopStageOnly`
7. `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }` -> `ScratchToPerformanceAllCompletedStages`
8. `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }` -> `ScratchToPerformanceStopStageOnly`

`Indicator × *` 两个公开组合共享同一个内部请求，因为它们的正式公开结果 shape 相同。

## 4. `PipelineOutput`

内部执行器返回严格的 `PipelineOutput`。

正式内部输出固定为：

```text
PipelineOutput =
    IndicatorsOnly {
        indicators_raw: IndicatorResults,
      }
    | SignalsOnly {
        signals: DataFrame,
      }
    | IndicatorsSignals {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
      }
    | BacktestOnly {
        backtest: DataFrame,
      }
    | IndicatorsSignalsBacktest {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
      }
    | PerformanceOnly {
        performance: PerformanceMetrics,
      }
    | IndicatorsSignalsBacktestPerformance {
        indicators_raw: IndicatorResults,
        signals: DataFrame,
        backtest: DataFrame,
        performance: PerformanceMetrics,
      }
```

输出约束如下：

1. `indicators_raw` 不携带 `time` 列。
2. `signals` 与 `backtest` 的高度必须等于 `data.mapping.height()`。
3. `performance` 只出现在 `PerformanceOnly` 与 `IndicatorsSignalsBacktestPerformance`。
4. 每个请求只对应一种固定输出 shape。

## 5. `PipelineRequest -> PipelineOutput` 固定映射

1. `ScratchToIndicator` -> `IndicatorsOnly`
2. `ScratchToSignalsStopStageOnly` -> `SignalsOnly`
3. `ScratchToSignalsAllCompletedStages` -> `IndicatorsSignals`
4. `ScratchToBacktestStopStageOnly` -> `BacktestOnly`
5. `ScratchToBacktestAllCompletedStages` -> `IndicatorsSignalsBacktest`
6. `ScratchToPerformanceStopStageOnly` -> `PerformanceOnly`
7. `ScratchToPerformanceAllCompletedStages` -> `IndicatorsSignalsBacktestPerformance`
8. `SignalsToBacktestStopStageOnly` -> `BacktestOnly`
9. `SignalsToBacktestAllCompletedStages` -> `IndicatorsSignalsBacktest`
10. `SignalsToPerformanceStopStageOnly` -> `PerformanceOnly`
11. `SignalsToPerformanceAllCompletedStages` -> `IndicatorsSignalsBacktestPerformance`
12. `BacktestToPerformanceStopStageOnly` -> `PerformanceOnly`
13. `BacktestToPerformanceAllCompletedStages` -> `IndicatorsSignalsBacktestPerformance`
