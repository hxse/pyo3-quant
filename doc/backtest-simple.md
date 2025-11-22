我用一套严谨的逻辑来描述当前回测引擎的仓位和结算

这是单仓位交易系统, 不考虑多仓位, 不用考虑杠杆(默认1倍杠杆), 默认每次下单全部金额

先定义术语 0空, 1进多, 2持多, 3平多, 4平空进多, -1进空, -2持空, -3平空, -4平多进空
当下仓位信号, current_position -> cp
前一个仓位信号, previous_position -> pp

价格记录:
entry_long_price: elp
entry_short_price: esp
exit_long_price: xlp
exit_short_price: xsp

* 如果pp: 1, -1, 4, -4, 那么对应的elp, esp需要记录(open开盘价)
* 如果in_bar=true, 并且cp: 3,-3, 4,-4, 那么对应的xlp, xsp需要记录(止盈止损触发价), 还要结算余额, 结算净值, (用记录价格结算)
* 如果last_in_bar=false, 并且pp: 3,-3, 4,-4, 那么对应的xlp, xsp需要记录(open开盘价), 还要结算余额, 结算净值, (用记录价格结算)
* 如果cp: 2,-2, 那么需要结算净值(close收盘价)

仓位状态前值延续:
* pp: 1 -> cp: 2
* pp: -1 -> cp: -2
* pp: 3 -> cp: 0
* pp: -3 -> cp: 0
* 其他情况保持原样, pp: x -> cp: x
