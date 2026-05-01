# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'fast_ema': st.number_input("Fast EMA Period", value=9, min_value=1, step=1),
        'slow_ema': st.number_input("Slow EMA Period", value=21, min_value=1, step=1),
        'slow_sma': st.number_input("Slow SMA Period", value=50, min_value=1, step=1),
        'very_slow_sma': st.number_input("Very Slow SMA Period", value=200, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }

# Define the EMA Crossover Strategy with SMA Filter
class EmaCrossWithSmaFilterStrategy(bt.Strategy):
    params = (
        ('fast_ema', 9),
        ('slow_ema', 21),
        ('slow_sma', 50),       # Period for the slower SMA filter
        ('very_slow_sma', 200), # Period for the very slow SMA filter
        ('order_percentage', 0.95),
    )

    def __init__(self):
        # Keep a reference to the close prices
        self.data_close = self.datas[0].close

        # Initialize EMAs for entry signals
        self.ema_fast = bt.indicators.EMA(self.data_close, period=self.params.fast_ema)
        self.ema_slow = bt.indicators.EMA(self.data_close, period=self.params.slow_ema)
        self.ema_crossover = bt.indicators.CrossOver(self.ema_fast, self.ema_slow)

        # Initialize SMAs for the long-term filter
        self.sma_slow = bt.indicators.SMA(self.data_close, period=self.params.slow_sma)
        self.sma_very_slow = bt.indicators.SMA(self.data_close, period=self.params.very_slow_sma)

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
        # Determine the long-term market state based on the SMA filter
        long_term_bullish = self.sma_slow[0] > self.sma_very_slow[0]

        # Check if we are in the market
        if not self.position:
            # Not in the market, look for a buy signal IF the long-term trend is bullish
            if long_term_bullish and self.ema_crossover > 0: # Golden Cross state AND EMA bullish cross
                self.log(f'BUY SIGNAL (SMA Filter Active): Close Price={self.data_close[0]:.2f}, 50SMA={self.sma_slow[0]:.2f}, 200SMA={self.sma_very_slow[0]:.2f}')
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                self.order = self.buy(size=size)
            # (Optional: Add short entry logic here if long_term_bullish is False and EMA crossover is negative)

        else:
            # Already in the market (long position), look for an exit signal (EMA bearish cross)
            # We stay in the long position as long as the EMA cross exit signal doesn't occur,
            # regardless of whether the SMAs cross back temporarily (avoids premature exits).
            # A more conservative approach could force an exit if the Death Cross occurs.
            if self.ema_crossover < 0: # Fast EMA crossed below Slow EMA
                self.log(f'SELL SIGNAL (Exit): Close Price={self.data_close[0]:.2f}')
                self.order = self.close() # Closes the existing long position
