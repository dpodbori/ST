import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'rebal_day': st.number_input("Rebalance Day (0=Monday)", value=0, min_value=0, max_value=6, step=1),
        'ema_period': st.number_input("EMA Period", value=50, min_value=1, step=1),
        'bb_period': st.number_input("Bollinger Bands Period", value=20, min_value=1, step=1),
        'bb_devfactor': st.number_input("Bollinger Bands Deviation Factor", value=2.0, min_value=0.1, step=0.1),
        'rsi_period': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_oversold': st.number_input("RSI Oversold Level", value=30, min_value=0, max_value=100, step=1),
        'rsi_overbought': st.number_input("RSI Overbought Level", value=70, min_value=0, max_value=100, step=1),
        'atr_period': st.number_input("ATR Period", value=14, min_value=1, step=1),
        'atr_mult': st.number_input("ATR Multiplier for Stop Loss", value=3.0, min_value=0.1, step=0.1),
    }

class DualRegimeWeeklyStrategy(bt.Strategy):
    """
    Strategy that switches between trending and ranging regimes on a weekly basis.
    """
    params = (
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('rebal_day', 0),
        ('ema_period', 50),
        ('bb_period', 20),
        ('bb_devfactor', 2.0),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('atr_period', 14),
        ('atr_mult', 3.0),
    )

    def __init__(self):
        self.adx = bt.indicators.ADX(self.data, period=self.p.adx_period)
        self.ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.ema_period)
        self.bb = bt.indicators.BollingerBands(
            self.data.close, period=self.p.bb_period, devfactor=self.p.bb_devfactor
        )
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.last_week = None
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Size: {order.executed.size}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Size: {order.executed.size}')
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            self.order = None

    def next(self):
        dt = self.data.datetime.date(0)
        current_week = dt.isocalendar()[1]
        if dt.weekday() != self.p.rebal_day: return
        if self.last_week == current_week: return
        self.last_week = current_week
        if self.position:
            self.log('Rebalancing: Closing existing position')
            self.close()
        regime = 'trending' if self.adx[0] > self.p.adx_threshold else 'ranging'
        self.log(f'New week - Regime: {regime}, Price: {self.data.close[0]:.2f}, ADX: {self.adx[0]:.2f}')
        if regime == 'trending':
            if self.data.close[0] > self.ema[0]:
                self.log(f'Trending regime: Price above EMA ({self.ema[0]:.2f}), entering long.')
                self.order = self.buy()
            else:
                self.log(f'Trending regime: Price below EMA ({self.ema[0]:.2f}), entering short.')
                self.order = self.sell()
        else:
            if self.data.close[0] <= self.bb.bot[0] and self.rsi[0] < self.p.rsi_oversold:
                self.log(f'Ranging regime: Price at lower band ({self.bb.bot[0]:.2f}) and RSI oversold ({self.rsi[0]:.2f}), entering long.')
                self.order = self.buy()
            elif self.data.close[0] >= self.bb.top[0] and self.rsi[0] > self.p.rsi_overbought:
                self.log(f'Ranging regime: Price at upper band ({self.bb.top[0]:.2f}) and RSI overbought ({self.rsi[0]:.2f}), entering short.')
                self.order = self.sell()
            else:
                self.log('Ranging regime: No clear mean reversion signal detected; staying out of the market.')

    def stop(self):
        self.log(f'Final Portfolio Value: {self.broker.getvalue():.2f}')
