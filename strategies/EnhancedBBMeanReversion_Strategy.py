import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'bb_period': st.number_input("Bollinger Bands Period", value=20, min_value=1, step=1),
        'bb_devfactor': st.number_input("Bollinger Bands Deviation Factor", value=2.0, min_value=0.1, step=0.1),
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'rsi_period': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_lower': st.number_input("RSI Lower Threshold", value=30, min_value=0, max_value=100, step=1),
        'rsi_upper': st.number_input("RSI Upper Threshold", value=70, min_value=0, max_value=100, step=1),
        'printlog': st.checkbox("Print Log", value=True)
    }


class EnhancedBBMeanReversion(bt.Strategy):
    """
    Enhanced Bollinger Bands Mean Reversion Strategy with extra filters.

    Entry Conditions for Long:
      - Price closes below the lower Bollinger Band.
      - ADX is below adx_threshold (indicating a sideways market).
      - RSI is below rsi_lower (indicating oversold conditions).

    Entry Conditions for Short (if enabled):
      - Price closes above the upper Bollinger Band.
      - ADX is below adx_threshold.
      - RSI is above rsi_upper (indicating overbought conditions).

    Exit Conditions:
      - Close long when the price crosses back above the middle band.
      - Close short when the price crosses back below the middle band.
    """
    params = (
        ('bb_period', 20),
        ('bb_devfactor', 2.0),
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('rsi_period', 14),
        ('rsi_lower', 30),
        ('rsi_upper', 70),
        ('printlog', True),
    )

    def log(self, txt, dt=None, doprint=False):
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.bband = bt.indicators.BollingerBands(
            self.datas[0],
            period=self.params.bb_period,
            devfactor=self.params.bb_devfactor
        )
        self.adx = bt.indicators.ADX(self.datas[0], period=self.params.adx_period)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        self.order = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

    def next(self):
        if self.order:
            return
        if self.adx[0] >= self.params.adx_threshold:
            self.log(f"Market trending (ADX {self.adx[0]:.2f} >= {self.params.adx_threshold}), skipping new entries.")
            return
        if not self.position:
            if (self.dataclose[0] < self.bband.lines.bot[0] and self.rsi[0] < self.params.rsi_lower):
                self.log(f'LONG ENTRY SIGNAL: Close: {self.dataclose[0]:.2f}, Lower BB: {self.bband.lines.bot[0]:.2f}, RSI: {self.rsi[0]:.2f}')
                self.order = self.buy()
        else:
            if self.position.size > 0 and self.dataclose[0] > self.bband.lines.mid[0]:
                self.log(f'EXIT LONG SIGNAL: Close: {self.dataclose[0]:.2f}, Mid BB: {self.bband.lines.mid[0]:.2f}')
                self.order = self.close()

    def stop(self):
        self.log(f'(BB Period {self.params.bb_period}, BB DevFact {self.params.bb_devfactor}, '
                 f'ADX Thresh {self.params.adx_threshold}, RSI [< {self.params.rsi_lower} / > {self.params.rsi_upper}]) '
                 f'Ending Value {self.broker.getvalue():.2f}', doprint=True)
