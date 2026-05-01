# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'fast_ema': st.number_input("Fast EMA Period", value=9, min_value=1, step=1),
        'slow_ema': st.number_input("Slow EMA Period", value=21, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }

# Define the EMA Crossover Strategy
class EmaCrossStrategy(bt.Strategy):
    params = (
        ('fast_ema', 9),
        ('slow_ema', 21),
        ('order_percentage', 0.95), # Use 95% of portfolio value for orders
    )

    def __init__(self):
        # Keep a reference to the close prices
        self.data_close = self.datas[0].close

        # Initialize EMAs
        self.ema_fast = bt.indicators.EMA(self.data_close, period=self.params.fast_ema)
        self.ema_slow = bt.indicators.EMA(self.data_close, period=self.params.slow_ema)

        # Initialize the crossover signal indicator
        self.crossover = bt.indicators.CrossOver(self.ema_fast, self.ema_slow)

        # Order tracking
        self.order = None

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self) # Record bar number when order was executed

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')


    def next(self):
        # Check if we are in the market
        if not self.position:
            # Not in the market, look for a buy signal
            if self.crossover > 0: # Fast EMA crossed above Slow EMA
                self.log(f'BUY SIGNAL DETECTED: Close Price={self.data_close[0]:.2f}')
                # Calculate order size
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                # Place the buy order for the next bar
                self.order = self.buy(size=size)

        else:
            # Already in the market, look for a sell signal to close the position
            if self.crossover < 0: # Fast EMA crossed below Slow EMA
                self.log(f'SELL SIGNAL (Exit) DETECTED: Close Price={self.data_close[0]:.2f}')
                # Place the sell order for the next bar to close the position
                self.order = self.close() # Closes the existing position
