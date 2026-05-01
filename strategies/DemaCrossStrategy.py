# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'fast_dema': st.number_input("Fast DEMA Period", value=12, min_value=1, step=1),
        'slow_dema': st.number_input("Slow DEMA Period", value=26, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }

# Define the DEMA Crossover Strategy
class DemaCrossStrategy(bt.Strategy):
    params = (
        ('fast_dema', 12),
        ('slow_dema', 26),
        ('order_percentage', 0.95),
    )

    def __init__(self):
        self.data_close = self.datas[0].close

        # Initialize DEMAs
        self.dema_fast = bt.indicators.DEMA(self.data_close, period=self.params.fast_dema)
        self.dema_slow = bt.indicators.DEMA(self.data_close, period=self.params.slow_dema)

        # Initialize the crossover signal indicator
        self.crossover = bt.indicators.CrossOver(self.dema_fast, self.dema_slow)

        # Order tracking
        self.order = None

    def log(self, txt, dt=None):
        ''' Logging function '''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]: return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED (Exit/Reverse), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed: return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')


    def next(self):
        # Check for open orders
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # Not in the market, look for a buy signal
            if self.crossover > 0: # Fast DEMA crossed above Slow DEMA
                self.log(f'BUY SIGNAL (DEMA Cross): Close Price={self.data_close[0]:.2f}')
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                self.order = self.buy(size=size)

        else: # Already in the market (long position assumed for simplicity)
            # Look for a sell signal to close the position and potentially reverse
            if self.crossover < 0: # Fast DEMA crossed below Slow DEMA
                self.log(f'SELL SIGNAL (DEMA Cross - Exit/Reverse): Close Price={self.data_close[0]:.2f}')
                # Simple stop-and-reverse: Close current position.
                # In a real system you might just close or implement short selling logic.
                self.order = self.close() # Closes the existing position
