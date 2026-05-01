import backtrader as bt
import streamlit as st


def show_parameters():    
    return {
        'bb_period': st.number_input("Bollinger Bands Period", value=20, min_value=1, step=1),
        'bb_devfactor': st.number_input("Bollinger Bands Deviation Factor", value=2.0, min_value=0.0, step=0.1),
    }

class BBMeanReversion(bt.Strategy):
    """
    Implements a Bollinger Bands Mean Reversion strategy.
    """
    params = (
        ('bb_period', 20),
        ('bb_devfactor', 2.0),
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.bband = bt.indicators.BollingerBands(
            self.datas[0],
            period=self.params.bb_period,
            devfactor=self.params.bb_devfactor
        )
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                         f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                         f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

    def next(self):
        if self.order:
            return
        if not self.position:
            if self.dataclose[0] < self.bband.lines.bot[0]:
                self.log(f'BUY CREATE, Close: {self.dataclose[0]:.2f}, '
                         f'Lower BB: {self.bband.lines.bot[0]:.2f}')
                self.order = self.buy()
        else:
            if self.position.size > 0 and self.dataclose[0] > self.bband.lines.mid[0]:
                self.log(f'CLOSE LONG CREATE, Close: {self.dataclose[0]:.2f}, '
                         f'Middle BB: {self.bband.lines.mid[0]:.2f}')
                self.order = self.close()

    def stop(self):
        self.log(f'(BB Period {self.params.bb_period}, BB DevFact {self.params.bb_devfactor}) '
                 f'Ending Value {self.broker.getvalue():.2f}')
