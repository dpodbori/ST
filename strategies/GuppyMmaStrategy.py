# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'period': st.number_input("Slope Period", value=14, min_value=1, step=1),
    }

class Slope(bt.Indicator):
    lines = ('slope',)
    params = dict(period=14)

    plotinfo = dict(subplot=True) # Keep plotting info if desired
    plotlines = dict(slope=dict(_name='Slope (Init Style)')) # Keep plotlines

    def __init__(self):
        # Get the data from 'period' bars ago.
        # self.data(N) accesses the data N bars ago.
        # So self.data(-self.p.period) gets the value from 'period' bars ago.
        data_prev = self.data(-self.p.period)

        # Calculate the difference between current data and previous data
        delta_y = self.data(0) - data_prev # self.data(0) is the current value

        # The slope is delta_y / period.
        # Division requires ensuring period is not zero.
        # Backtrader indicator math handles operations line-wise.
        # We might need to handle the division carefully or assume period > 0.
        if self.p.period > 0:
            self.lines.slope = delta_y / self.p.period
        else:
            # If period is 0, slope is undefined or 0. Assign a line of zeros.
            # Create a zero line with the same length as self.data
            zero_line = self.data * 0.0
            self.lines.slope = zero_line
            
# Define the Guppy MMA Pullback Strategy
class GuppyMmaStrategy(bt.Strategy):
    params = (
        ('short_periods', (3, 5, 8, 10, 12, 15)),
        ('long_periods', (30, 35, 40, 45, 50, 60)),
        ('order_percentage', 0.95),
        ('min_slope_period', 20) # Period for checking slope of slowest long EMA
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.data_low = self.datas[0].low

        # Create short-term EMAs
        self.short_emas = []
        for period in self.params.short_periods:
            self.short_emas.append(bt.indicators.EMA(self.data_close, period=period))
        self.ema_short_fastest = self.short_emas[0]
        self.ema_short_slowest = self.short_emas[-1]


        # Create long-term EMAs
        self.long_emas = []
        for period in self.params.long_periods:
            self.long_emas.append(bt.indicators.EMA(self.data_close, period=period))
        self.ema_long_fastest = self.long_emas[0] # e.g., EMA 30
        self.ema_long_slowest = self.long_emas[-1] # e.g., EMA 60

        # Check slope of the slowest long-term EMA for trend direction confirmation
        self.long_slowest_slope = Slope(self.ema_long_slowest, period=self.params.min_slope_period)

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
            else: # Sell
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
        min_data_needed = max(self.params.long_periods) + self.params.min_slope_period
        if len(self.data_close) < min_data_needed:
            return

        # --- Define Uptrend State ---
        # 1. Short group is generally above long group (e.g., fastest short > fastest long)
        # 2. Slowest long EMA has a positive slope (confirming underlying investor uptrend)
        # 3. Optional: Slowest short EMA is above fastest long EMA (clean separation)
        groups_separated = self.ema_short_slowest[0] > self.ema_long_fastest[0]
        investor_trend_up = self.long_slowest_slope[0] > 0 # Simple check for positive slope

        is_uptrend_established = groups_separated and investor_trend_up

        # --- Define Pullback to Long-Term Group ---
        # Price low touches or penetrates the fastest EMA of the long-term group
        pullback_to_investors = self.data_low[0] <= self.ema_long_fastest[0]

        # --- Entry Logic ---
        if not self.position:
            if is_uptrend_established and pullback_to_investors:
                # Ensure price hasn't already collapsed below the *slowest* long EMA
                if self.data_close[0] > self.ema_long_slowest[0]:
                    self.log(f'BUY SIGNAL (Guppy Pullback): Close={self.data_close[0]:.2f}, Low={self.data_low[0]:.2f}, Testing Long Group EMA {self.params.long_periods[0]}={self.ema_long_fastest[0]:.2f}')
                    cash = self.broker.get_cash()
                    size = (cash * self.params.order_percentage) / self.data_close[0]
                    self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                    self.order = self.buy(size=size)

        # --- Exit Logic ---
        else: # We are in a long position
            # Exit if price closes below the slowest long-term EMA (EMA 60)
            if self.data_close[0] < self.ema_long_slowest[0]:
                 self.log(f'SELL SIGNAL (Exit - Close below EMA {self.params.long_periods[-1]}): Close={self.data_close[0]:.2f}, EMA {self.params.long_periods[-1]}={self.ema_long_slowest[0]:.2f}')
                 self.order = self.close()
