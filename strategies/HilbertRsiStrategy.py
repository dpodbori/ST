import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'rsi_period': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_upper_filter': st.number_input("RSI Upper Filter", value=60, min_value=0, max_value=100, step=1),
        'rsi_lower_filter': st.number_input("RSI Lower Filter", value=40, min_value=0, max_value=100, step=1),
        'atr_period': st.number_input("ATR Period", value=14, min_value=1, step=1),
        'atr_ma_period': st.number_input("ATR MA Period", value=20, min_value=1, step=1),
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=3.0, min_value=0.0, max_value=100.0) / 100,
    }

# --- Strategy Definition ---
class HilbertRsiStrategy(bt.Strategy):
    """
    Hilbert Transform Sine Wave Crossover with RSI, ATR, ADX filters.
    Includes a percentage-based Trailing Stop Loss.
    """
    params = (
        ('rsi_period', 14),
        ('rsi_upper_filter', 60),
        ('rsi_lower_filter', 40),
        ('atr_period', 14),
        ('atr_ma_period', 20),
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('trail_percent', 0.03),  # Trailing stop percentage (e.g., 0.03 = 3%)
    )

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        # print(f'{dt.isoformat()} - {txt}') # Keep logs minimal unless debugging
        pass

    def __init__(self):
        # Data references
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low

        # Indicators (using plot=False to simplify chart)
        try:
            self.htsine_indicator = bt.talib.HT_SINE(self.dataclose, plot=False)
            self.htsine = self.htsine_indicator.sine
            self.htleadsine = self.htsine_indicator.leadsine
        except Exception as e:
             print(f"ERROR Initializing HT_SINE: {e}")
             raise
        self.rsi = bt.indicators.RelativeStrengthIndex(period=self.params.rsi_period, plot=False)
        self.sine_cross_lead = bt.indicators.CrossOver(self.htsine, self.htleadsine, plot=False)
        self.atr = bt.indicators.AverageTrueRange(period=self.params.atr_period, plot=False)
        self.atr_ma = bt.indicators.SimpleMovingAverage(self.atr, period=self.params.atr_ma_period, plot=False)
        self.adx_indicator = bt.indicators.AverageDirectionalMovementIndex(period=self.params.adx_period, plot=False)
        self.adx = self.adx_indicator.adx

        # Order tracking
        self.entry_order = None # Tracks the entry order
        self.stop_order = None  # Tracks the trailing stop order

        # Filter block counters (optional)
        self.atr_blocks = 0
        self.adx_blocks = 0

    def notify_order(self, order):
        # --- Handle Entry Order ---
        if order.status == order.Submitted and order == self.entry_order:
            # self.log(f'ENTRY {order.ordtypename()} Submitted: Ref {order.ref}')
            return
        if order.status == order.Accepted and order == self.entry_order:
            # self.log(f'ENTRY {order.ordtypename()} Accepted: Ref {order.ref}')
            return

        # --- Handle Stop Order ---
        if order.status == order.Submitted and order == self.stop_order:
            # self.log(f'STOP {order.ordtypename()} Submitted: Ref {order.ref}')
            return
        if order.status == order.Accepted and order == self.stop_order:
            # self.log(f'STOP {order.ordtypename()} Accepted: Ref {order.ref}')
            return

        # --- Handle Order Completion ---
        if order.status == order.Completed:
            if order.isbuy(): # Could be entry buy or stop buy (closing short)
                if order == self.entry_order: # This was the entry buy
                    # self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                    self.buyprice = order.executed.price # Store entry price if needed
                    self.buycomm = order.executed.comm
                    self.entry_order = None # Reset entry tracker

                    # Place Trailing Stop Sell Order
                    self.stop_order = self.sell(exectype=bt.Order.StopTrail,
                                                trailpercent=self.params.trail_percent)
                    trail_price_initial = order.executed.price * (1.0 - self.params.trail_percent) # Approx initial level
                    # self.log(f'TRAILING STOP SELL PLACED at {self.params.trail_percent*100:.1f}%, Initial Stop ~{trail_price_initial:.2f}, Ref: {self.stop_order.ref}')

                elif order == self.stop_order: # This was the stop buy (closing short)
                    # self.log(f'STOP BUY EXECUTED (Exit Short), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                    self.stop_order = None # Reset stop tracker

            elif order.issell(): # Could be entry sell or stop sell (closing long)
                 if order == self.entry_order: # This was the entry sell
                    # self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                    self.entry_order = None # Reset entry tracker

                    # Place Trailing Stop Buy Order
                    self.stop_order = self.buy(exectype=bt.Order.StopTrail,
                                               trailpercent=self.params.trail_percent)
                    trail_price_initial = order.executed.price * (1.0 + self.params.trail_percent) # Approx initial level
                    # self.log(f'TRAILING STOP BUY PLACED at {self.params.trail_percent*100:.1f}%, Initial Stop ~{trail_price_initial:.2f}, Ref: {self.stop_order.ref}')

                 elif order == self.stop_order: # This was the stop sell (closing long)
                    # self.log(f'STOP SELL EXECUTED (Exit Long), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                    self.stop_order = None # Reset stop tracker

        # --- Handle Order Rejection/Cancellation ---
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            status_text = order.getstatusname()
            if order == self.entry_order:
                # self.log(f'ENTRY ORDER {status_text}: Ref {order.ref}')
                self.entry_order = None
            elif order == self.stop_order:
                # self.log(f'STOP ORDER {status_text}: Ref {order.ref}')
                self.stop_order = None


    def notify_trade(self, trade):
        if not trade.isclosed:
            # Optional: log entry details
            # self.log(f'TRADE OPEN: Size={trade.size}, Price={trade.price:.2f}')
            return
        # self.log(f'TRADE CLOSED: PNL Gross={trade.pnl:.2f}, Net={trade.pnlcomm:.2f}')

    def next(self):
        # Check if an entry order is pending
        if self.entry_order:
            return
        # Check if a stop order is pending (means we are already in a position)
        if self.stop_order:
            return # Let the trailing stop manage the exit

        # Check if we are NOT in the market (and no orders pending)
        if not self.position:
            # --- Define Filter Conditions ---
            is_low_volatility = self.atr[0] < self.atr_ma[0]
            is_weak_trend = self.adx[0] < self.params.adx_threshold

            # Check original entry signals
            long_signal = self.sine_cross_lead[0] == 1 and self.rsi[0] < self.params.rsi_upper_filter
            short_signal = self.sine_cross_lead[0] == -1 and self.rsi[0] > self.params.rsi_lower_filter

            # Apply Filters to Entry Signals
            if long_signal:
                if is_low_volatility and is_weak_trend:
                    # self.log(f'LONG ENTRY SIGNAL: Close={self.dataclose[0]:.2f}')
                    self.entry_order = self.buy()
                else:
                    # Increment block counters if desired
                    if not is_low_volatility: self.atr_blocks += 1
                    if not is_weak_trend: self.adx_blocks += 1

            elif short_signal:
                if is_low_volatility and is_weak_trend:
                    # self.log(f'SHORT ENTRY SIGNAL: Close={self.dataclose[0]:.2f}')
                    self.entry_order = self.sell()
                else:
                    # Increment block counters if desired
                    if not is_low_volatility: self.atr_blocks += 1
                    if not is_weak_trend: self.adx_blocks += 1

        # --- Removed the previous 'else' block for opposite crossover exit ---
        # Exit is now handled by the trailing stop placed via notify_order


    def stop(self):
        """ Log filter blocks at the end """
        print("-" * 30)
        print("Strategy Stop - Filter Blocks:")
        print(f"ATR Blocks: {self.atr_blocks}")
        print(f"ADX Blocks: {self.adx_blocks}")
        print("-" * 30)
