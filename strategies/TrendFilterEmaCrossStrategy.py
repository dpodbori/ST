# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'fast_ema': st.number_input("Fast EMA Period", value=9, min_value=1, step=1),
        'slow_ema': st.number_input("Slow EMA Period", value=21, min_value=1, step=1),
        'filter_sma': st.number_input("Filter SMA Period", value=200, min_value=1, step=1),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
    }

# Define the Trend Filtered EMA Crossover Strategy
class TrendFilterEmaCrossStrategy(bt.Strategy):
    params = (
        ('fast_ema', 9),
        ('slow_ema', 21),
        ('filter_sma', 200),       # Period for the long-term SMA filter
        ('order_percentage', 0.95),
    )

    def __init__(self):
        self.data_close = self.datas[0].close

        # Initialize EMAs for entry/exit signals
        self.ema_fast = bt.indicators.EMA(self.data_close, period=self.params.fast_ema)
        self.ema_slow = bt.indicators.EMA(self.data_close, period=self.params.slow_ema)
        self.ema_crossover = bt.indicators.CrossOver(self.ema_fast, self.ema_slow)

        # Initialize SMA for the long-term trend filter
        self.sma_filter = bt.indicators.SMA(self.data_close, period=self.params.filter_sma)

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
        if len(self.data_close) < self.params.filter_sma:
            return

        # Check for open orders
        if self.order:
            return

        # Determine the long-term market state based on the price vs SMA filter
        long_term_bullish = self.data_close[0] > self.sma_filter[0]

        # --- Entry Logic ---
        if not self.position:
            # Only consider buying if the long-term trend is bullish
            if long_term_bullish:
                # Check for the bullish EMA crossover signal
                if self.ema_crossover > 0:
                    self.log(f'BUY SIGNAL (Filtered EMA Cross): Close={self.data_close[0]:.2f}, Price > SMA{self.params.filter_sma}={self.sma_filter[0]:.2f}')
                    cash = self.broker.get_cash()
                    size = (cash * self.params.order_percentage) / self.data_close[0]
                    self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                    self.order = self.buy(size=size)

        # --- Exit Logic ---
        else: # Already in a long position
            # Exit if the short-term EMA crossover gives a sell signal
            if self.ema_crossover < 0:
                self.log(f'SELL SIGNAL (Exit - EMA Cross): Close={self.data_close[0]:.2f}')
                self.order = self.close()
            # Optional: Could also add an exit if long_term_bullish becomes False (price closes below 200 SMA)
            # elif not long_term_bullish:
            #     self.log(f'SELL SIGNAL (Exit - Price below Filter SMA): Close={self.data_close[0]:.2f}')
            #     self.order = self.close()
