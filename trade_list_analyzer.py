import backtrader as bt


class TradeListAnalyzer(bt.Analyzer):
    def __init__(self):
        self.trades = []
        self.orders = []

    # I tried to use trades for the statistic, but you cannot get size of the entry order. But maybe it can be used with notify_trade.
    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                'entry_bar': trade.baropen,
                'exit_bar': trade.barclose,
                'entry_price': trade.price,
                'exit_price': trade.price,
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_comm': trade.pnlcomm,
                'commission': trade.commission,
                'long': trade.long,
            })

    def notify_order(self, order):
        if order.status in [order.Completed, order.Partial]:
            dt = bt.num2date(order.executed.dt)
            unix_dt = int(dt.timestamp())
            self.orders.append({
                'date': unix_dt,
                'price': order.executed.price,
                'commission': order.executed.comm,
                'status': order.Status[order.status],
                'order_type': "BUY" if order.isbuy() else "SELL" if order.issell() else "UNKNOWN",
                'size': order.executed.size,
                'position_after_trade': order.executed.psize
            })

    def get_analysis(self):
        return self.orders