# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'ma_period': st.number_input("MA Period", value=20, min_value=1, step=1),
        'slope_period': st.number_input("Slope Period", value=10, min_value=1, step=1),
        'ma_type': st.selectbox("MA Type", options=['EMA', 'SMA']),
        'slope_entry_threshold': st.number_input("Slope Entry Threshold", value=0.05, min_value=-1.0, max_value=1.0, step=0.01),
        'slope_exit_threshold': st.number_input("Slope Exit Threshold", value=-0.10, min_value=-1.0, max_value=1.0, step=0.01),
        'min_prior_slope': st.number_input("Min Prior Slope", value=-0.05, min_value=-1.0, max_value=1.0, step=0.01),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }

# Slope Indicator (using __init__ style)
class Slope(bt.Indicator):
    lines = ('slope',)
    params = dict(period=14)

    plotinfo = dict(subplot=True) # Plot in separate panel below price
    plotlines = dict(slope=dict(_name='EMA Slope')) # Label for plot legend

    def __init__(self):
        # self.data(-N) gets value N bars ago. self.data(0) is current.
        data_prev = self.data(-self.p.period)
        delta_y = self.data(0) - data_prev

        if self.p.period > 0:
            self.lines.slope = delta_y / self.p.period
        else:
            # Handle period=0 case (assign zeros)
            self.lines.slope = self.data * 0.0

# Define the MA Slope Strategy
class MaSlopeStrategy(bt.Strategy):
    params = (
        ('ma_period', 30),         # Period for the EMA
        ('slope_period', 10),      # Period for calculating the slope of the EMA
        ('ma_type', 'EMA'),        # Type of MA
        ('slope_entry_threshold', 0.05), # Slope must cross ABOVE this to enter long
        ('slope_exit_threshold', -0.10), # Slope must cross BELOW this to exit long
        ('min_prior_slope', -0.05),# Slope should have been below this prior to entry signal
        ('order_percentage', 0.95),
    )

    def __init__(self):
        self.data_close = self.datas[0].close

        # Select MA type based on params
        ma_indicator = bt.indicators.EMA if self.params.ma_type == 'EMA' else bt.indicators.SMA
        self.ma = ma_indicator(self.data_close, period=self.params.ma_period)

        # Calculate the slope of the MA
        self.ma_slope = Slope(self.ma, period=self.params.slope_period)

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
                self.log(f'SELL EXECUTED (Exit), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed: return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

    def next(self):
        # Check if indicators have enough data
        min_data_needed = self.params.ma_period + self.params.slope_period
        if len(self.data_close) < min_data_needed:
            return

        # Check for open orders
        if self.order:
            return

        # Get current and previous slope values
        current_slope = self.ma_slope[0]
        previous_slope = self.ma_slope[-1]

        # --- Entry Logic ---
        if not self.position:
            # Condition 1: Slope was recently flat or negative
            was_flat_or_down = previous_slope < self.params.min_prior_slope
            # Condition 2: Slope just crossed above the positive entry threshold
            crossed_up = previous_slope <= self.params.slope_entry_threshold and \
                         current_slope > self.params.slope_entry_threshold

            if was_flat_or_down and crossed_up:
                self.log(f'BUY SIGNAL (Slope Turn): Close={self.data_close[0]:.2f}, Slope={current_slope:.3f}, Prev Slope={previous_slope:.3f}')
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                self.order = self.buy(size=size)

        # --- Exit Logic ---
        else: # We are in a long position
            # Exit if slope crosses below the negative exit threshold
            crossed_down = previous_slope >= self.params.slope_exit_threshold and \
                           current_slope < self.params.slope_exit_threshold

            if crossed_down:
                 self.log(f'SELL SIGNAL (Exit - Slope Turn Down): Close={self.data_close[0]:.2f}, Slope={current_slope:.3f}, Threshold={self.params.slope_exit_threshold}')
                 self.order = self.close()
