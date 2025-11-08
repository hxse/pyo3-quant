@/src/error/backtest_error@/src/error/signal_error@/src/error/indicator_error
这三个异常类, 让py的部分跟rust的部分对齐, 以rust的部分为准
比如检查 src/error/backtest_error/error.rs 是否和src/error/backtest_error/py_interface.rs里面的异常类一致, 以error.rs为准, 这三个文件夹都要检查

本次任务只涉及.rs文件, 不涉及.py文件
