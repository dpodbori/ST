# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'ema_periods': st.multiselect("EMA Periods", options=[5, 8, 11, 14, 17, 20], default=[5, 8, 11, 14, 17, 20]),
        'slope_period': st.number_input("Slope Period", value=10, min_value=1, step=1),
        'exit_ema_cross_short': st.number_input("Exit EMA Cross Short Period", value=5, min_value=1, step=1),
        'exit_ema_cross_long': st.number_input("Exit EMA Cross Long Period", value=11, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
        'min_slope_threshold': st.number_input("Minimum Slope Threshold", value=0.01, min_value=0.0, step=0.001)
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
        
# Define the MA Ribbon Pullback Strategy
class MaRibbonPullbackStrategy(bt.Strategy):
    params = (
        # Define the periods for the ribbon EMAs
        ('ema_periods', (5, 8, 11, 14, 17, 20)),
        ('slope_period', 10), # Period to calculate slope of the slowest EMA
        ('exit_ema_cross_short', 5), # Faster EMA for exit crossover
        ('exit_ema_cross_long', 11), # Slower EMA for exit crossover
        ('order_percentage', 0.95),
        ('min_slope_threshold', 0.01) # Minimum upward slope for slowest EMA to consider trend 'up'
                                     # Adjust based on asset volatility and timeframe
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.data_low = self.datas[0].low # Need low price to check for touch

        # Create the ribbon EMA indicators
        self.ribbon_emas = []
        for period in self.params.ema_periods:
            self.ribbon_emas.append(bt.indicators.EMA(self.data_close, period=period))

        # Reference the fastest and slowest EMAs for conditions
        self.ema_fastest = self.ribbon_emas[0]
        self.ema_slowest = self.ribbon_emas[-1]

        # Calculate slope of the slowest EMA using linear regression
        # Slope = (N * Sum(XY) - Sum(X) * Sum(Y)) / (N * Sum(X^2) - (Sum(X))^2)
        # We need X (time index) and Y (EMA value)
        # Using a simpler approximation: (EMA[0] - EMA[-period]) / period
        self.slowest_ema_slope = Slope(self.ema_slowest, period=self.params.slope_period)

        # EMA cross for exit signal
        self.ema_exit_fast = bt.indicators.EMA(self.data_close, period=self.params.exit_ema_cross_short)
        self.ema_exit_slow = bt.indicators.EMA(self.data_close, period=self.params.exit_ema_cross_long)
        self.exit_crossover = bt.indicators.CrossOver(self.ema_exit_fast, self.ema_exit_slow)


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
        if len(self.data_close) < max(self.params.ema_periods) + self.params.slope_period:
             return

        # Define expansion state (simplified)
        # 1. Fastest EMA is above slowest EMA
        # 2. Slowest EMA slope is positive and above threshold
        is_expanding_up = (self.ema_fastest[0] > self.ema_slowest[0] and
                           self.slowest_ema_slope[0] > self.params.min_slope_threshold)

        # Check for pullback touch (using low price)
        # Price low touches or goes slightly below the fastest EMA
        pullback_touch = self.data_low[0] <= self.ema_fastest[0]

        # --- Entry Logic ---
        if not self.position:
            if is_expanding_up and pullback_touch:
                self.log(f'BUY SIGNAL (Pullback): Close={self.data_close[0]:.2f}, Low={self.data_low[0]:.2f}, FastEMA={self.ema_fastest[0]:.2f}, Slope={self.slowest_ema_slope[0]:.3f}')
                cash = self.broker.get_cash()
                size = (cash * self.params.order_percentage) / self.data_close[0]
                self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                self.order = self.buy(size=size)
            # (Optional: Add short entry logic for downward expansion and pullback to resistance)

        # --- Exit Logic ---
        else: # We are in a long position
            # Exit if the faster exit EMA crosses below the slower exit EMA
            if self.exit_crossover < 0:
                 self.log(f'SELL SIGNAL (Exit - EMA Cross): Close={self.data_close[0]:.2f}')
                 self.order = self.close()
