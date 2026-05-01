# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'fastest_ema': st.number_input("Fastest EMA Period", value=5, min_value=1, step=1),
        'medium_ema': st.number_input("Medium EMA Period", value=10, min_value=1, step=1),
        'slowest_ema': st.number_input("Slowest EMA Period", value=20, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }
    
# Define the Triple EMA Crossover Strategy
class TripleEmaCrossStrategy(bt.Strategy):
    params = (
        ('fastest_ema', 5),
        ('medium_ema', 10),
        ('slowest_ema', 20),
        ('order_percentage', 0.95),
    )

    def __init__(self):
        # Keep a reference to the close prices
        self.data_close = self.datas[0].close

        # Initialize EMAs
        self.ema_fastest = bt.indicators.EMA(self.data_close, period=self.params.fastest_ema)
        self.ema_medium = bt.indicators.EMA(self.data_close, period=self.params.medium_ema)
        self.ema_slowest = bt.indicators.EMA(self.data_close, period=self.params.slowest_ema)

        # Initialize the crossover signal indicator for entry/exit trigger
        self.fast_medium_crossover = bt.indicators.CrossOver(self.ema_fastest, self.ema_medium)

        # Order tracking
        self.order = None

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED (Exit), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

    def next(self):
        # Determine the medium-term trend context (medium EMA vs slowest EMA)
        medium_term_bullish = self.ema_medium[0] > self.ema_slowest[0]

        # Check if we are in the market
        if not self.position:
            # Not in the market, look for a buy signal if medium-term trend is bullish
            if medium_term_bullish and self.fast_medium_crossover > 0: # Medium term up AND Fast crosses Medium
                self.log(f'BUY SIGNAL: Close Price={self.data_close[0]:.2f}, EMA Condition Met')
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                self.order = self.buy(size=size)
            # (Optional: Add short entry logic here if medium_term_bullish is False and fast_medium_crossover < 0)

        else:
            # Already in the market (long position), look for an exit signal
            # Exit when the fastest EMA crosses back below the medium EMA
            if self.fast_medium_crossover < 0:
                self.log(f'SELL SIGNAL (Exit): Close Price={self.data_close[0]:.2f}, Fast EMA crossed below Medium EMA')
                self.order = self.close() # Closes the existing long position
