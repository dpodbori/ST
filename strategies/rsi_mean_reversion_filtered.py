import backtrader as bt
import streamlit as st


def show_parameters():    
    return {
        'rsi_period': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_overbought': st.number_input("RSI Overbought Level", value=70, min_value=0, max_value=100, step=1),
        'rsi_oversold': st.number_input("RSI Oversold Level", value=30, min_value=0, max_value=100, step=1),
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'atr_period': st.number_input("ATR Period", value=14, min_value=1, step=1),
        'atr_ratio_threshold': st.number_input("ATR/Price Ratio Threshold", value=0.02, min_value=0.0, step=0.01),
        'printlog': st.checkbox("Print Log", value=True),
    }

class RsiStrategyWithTrendFilters(bt.Strategy):
    params = (
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('adx_period', 14),
        ('adx_threshold', 25),         # Must be above this value for a strong trend
        ('atr_period', 14),
        ('atr_ratio_threshold', 0.02),   # ATR/Price ratio must be above this level
        ('printlog', True),
    )

    def __init__(self):
        # Reference to the closing price
        self.dataclose = self.datas[0].close

        # To track pending orders
        self.order = None

        # Base RSI indicator
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        
        # ADX indicator for trend strength
        self.adx = bt.indicators.AverageDirectionalMovementIndex(self.datas[0], period=self.params.adx_period)

        # ATR indicator for volatility measure
        self.atr = bt.indicators.ATR(self.datas[0], period=self.params.atr_period)

    def log(self, txt, dt=None, doprint=False):
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Order is submitted/accepted, do nothing
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}'
                )
            elif order.issell():
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}'
                )
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Reset order tracking when no order is pending
        self.order = None

    def next(self):
        # Don't take new orders if there is a pending order.
        if self.order:
            return

        # Calculate ATR/close ratio for current bar.
        atr_ratio = self.atr[0] / self.dataclose[0]
        
        # Filtering conditions: check if the ADX and ATR filters are met.
        trend_confirmed = self.adx[0] >= self.params.adx_threshold
        volatile_enough = atr_ratio >= self.params.atr_ratio_threshold

        if  trend_confirmed and volatile_enough:
            return
        
        # When not in the market, consider taking a new position:
        if not self.position:
            if (self.rsi < self.params.rsi_oversold):
                self.log(f'BUY CREATE at {self.dataclose[0]:.2f} | RSI: {self.rsi[0]:.2f} | ADX: {self.adx[0]:.2f} | ATR/Close: {atr_ratio:.4f}')
                self.order = self.buy()
        else:
            # In the market, consider exiting based on overbought RSI with confirmation.
            if (self.rsi > self.params.rsi_overbought):
                self.log(f'SELL CREATE at {self.dataclose[0]:.2f} | RSI: {self.rsi[0]:.2f} | ADX: {self.adx[0]:.2f} | ATR/Close: {atr_ratio:.4f}')
                self.order = self.sell()
