import backtrader as bt
import numpy as np
from hurst import compute_Hc # Import the Hurst exponent calculation function
import streamlit as st


def show_parameters():
    """
    Streamlit UI for strategy parameters.
    """
    return {
        'hurst_window': st.number_input("Hurst Window Size", value=100, min_value=20, step=10),
        'hurst_threshold': st.number_input("Hurst Threshold", value=0.55, min_value=0.0, max_value=1.0, step=0.01),
        'sma_fast': st.number_input("Fast SMA Period", value=20, min_value=1, step=1),
        'sma_slow': st.number_input("Slow SMA Period", value=50, min_value=1, step=1),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=0.05, min_value=0.01, max_value=1.0, step=0.01),
        'printlog': st.checkbox("Print Log", value=True)
    }
# Use '%matplotlib qt5' or '%matplotlib inline' depending on your environment
# %matplotlib qt5

# --- Step 1: Define the Hurst Exponent Indicator ---
# --- Step 1: Define the Hurst Exponent Indicator (Corrected) ---
class HurstExponentIndicator(bt.Indicator):
    """
    Calculates the Hurst Exponent over a rolling window using the 'hurst' library.
    (Corrected to handle data input correctly)
    """
    lines = ('hurst',)
    params = (
        ('window', 100),
        ('fitting_kind', 'price'),
    )
    plotinfo = dict(
        subplot=True,
        plotname='Hurst Exponent'
    )
    plotlines = dict(
        hurst=dict(_name='H', _plotskip=False)
    )

    def __init__(self):
        # self.data already refers to the close LineSeries passed from the strategy
        # REMOVED: self.dataclose = self.data.close

        # Basic check for window size
        if self.p.window < 20:
            print(f"Warning: Hurst window ({self.p.window}) might be too small.")

        # Ensure the indicator calculates only when enough data is present
        self.addminperiod(self.p.window)

    def next(self):
        # Get the window of data directly from self.data (which is the close series)
        # Using list() conversion ensures compatibility with compute_Hc input type
        try:
             data_window = list(self.data.get(size=self.p.window))
        except IndexError:
             # Not enough data in the buffer yet for .get() with this size
             self.lines.hurst[0] = np.nan
             return


        # Ensure we have the exact number of data points needed after .get()
        if len(data_window) < self.p.window:
            self.lines.hurst[0] = np.nan
            return

        # Calculate Hurst exponent
        try:
            # Pass the list to compute_Hc
            H, c, data = compute_Hc(data_window, kind=self.p.fitting_kind, simplified=True)
            self.lines.hurst[0] = H
        except Exception as e:
            # Log error or handle as needed
            # print(f"Warning: Hurst calculation failed at {self.data.datetime.date(0)}: {e}")
            self.lines.hurst[0] = np.nan # Assign NaN if calculation fails


# --- Step 2: Define the Hurst Filtered Trend Strategy ---
class HurstFilteredTrendStrategy(bt.Strategy):
    """
    A trend-following strategy (SMA Crossover) filtered by the Hurst Exponent.
    Only takes trend signals when Hurst > threshold (indicating trending regime).
    Uses a trailing stop-loss for exits.
    """
    params = (
        # Hurst parameters
        ('hurst_window', 100),       # Window for Hurst calculation
        ('hurst_threshold', 0.55),   # Hurst value above which trend signals are enabled

        # Trend parameters (SMA Crossover example)
        ('sma_fast', 20),            # Fast SMA period
        ('sma_slow', 50),            # Slow SMA period

        # Exit parameter
        ('trail_percent', 0.05),     # Trailing stop percentage

        # Logging
        ('printlog', True),
    )

    def __init__(self):
        # Instantiate the Hurst Exponent Indicator
        self.hurst = HurstExponentIndicator(
            self.data.close, # Pass the close price series
            window=self.p.hurst_window
        )

        # Instantiate the trend indicators (SMA Crossover)
        sma_fast = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.sma_fast)
        sma_slow = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.sma_slow)
        self.sma_cross = bt.indicators.CrossOver(sma_fast, sma_slow) # 1 for cross up, -1 for cross down

        # Order trackers (same as previous examples)
        self.order = None
        self.stop_order = None

        if self.params.printlog:
            print("-" * 50)
            print("Strategy Parameters:")
            print(f" Hurst Window: {self.p.hurst_window}")
            print(f" Hurst Threshold: {self.p.hurst_threshold}")
            print(f" SMA Fast: {self.p.sma_fast}")
            print(f" SMA Slow: {self.p.sma_slow}")
            print(f" Trail Percent: {self.p.trail_percent * 100:.2f}%")
            print("-" * 50)

    def log(self, txt, dt=None, doprint=False):
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        # Identical order notification logic as the previous TSL example
        if order.status in [order.Submitted, order.Accepted]: return
        if order.status == order.Completed:
            if self.order and order.ref == self.order.ref:
                entry_type = "BUY" if order.isbuy() else "SELL"
                exit_func = self.sell if order.isbuy() else self.buy
                self.log(f'{entry_type} EXECUTED @ {order.executed.price:.2f}, Size: {order.executed.size:.4f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}', doprint=True)
                if self.p.trail_percent and self.p.trail_percent > 0.0:
                    self.stop_order = exit_func(exectype=bt.Order.StopTrail, trailpercent=self.p.trail_percent)
                    self.log(f'Trailing Stop Placed for {entry_type} order ref {self.stop_order.ref} at {self.p.trail_percent * 100:.2f}% trail', doprint=True)
                self.order = None
            elif self.stop_order and order.ref == self.stop_order.ref:
                exit_type = "STOP BUY (Cover)" if order.isbuy() else "STOP SELL (Exit Long)"
                self.log(f'{exit_type} EXECUTED @ {order.executed.price:.2f}, Size: {order.executed.size:.4f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}', doprint=True)
                self.stop_order = None
                self.order = None # Also reset entry order tracker
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Failed: Status {order.getstatusname()}, Ref: {order.ref}', doprint=True)
            if self.order and order.ref == self.order.ref: self.order = None
            if self.stop_order and order.ref == self.stop_order.ref:
                 self.log(f'WARNING: Trailing Stop Order Failed!', doprint=True)
                 self.stop_order = None

    def notify_trade(self, trade):
        # Identical trade notification logic
        if not trade.isclosed: return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}', doprint=True)

    def next(self):
        # Check if indicators/orders are ready
        # Accessing self.hurst[0] requires Hurst calculation to be done
        if self.order or len(self.hurst) == 0 or len(self.sma_cross) == 0:
            return

        current_hurst = self.hurst.hurst[0] # Use self.hurst[0] also works
        current_cross = self.sma_cross[0]
        current_close = self.data.close[0]
        current_position_size = self.position.size

        # Check if Hurst calculation failed
        if np.isnan(current_hurst):
            # Decide how to handle failed Hurst calculation (e.g., do nothing)
            # self.log(f"Skipping bar - Hurst value is NaN", doprint=False)
            return

        # --- Regime Filter ---
        is_trending_regime = current_hurst > self.p.hurst_threshold

        # Log current state for debugging (optional)
        # self.log(f'Close: {current_close:.2f}, Hurst: {current_hurst:.3f}, Cross: {current_cross:.0f}, Regime Trend: {is_trending_regime}, Position: {current_position_size}')

        # --- Trading Logic ---
        if current_position_size == 0: # If FLAT
            # Safety check
            if self.stop_order:
                self.log("Warning: Position flat but stop order exists. Cancelling.", doprint=True)
                self.cancel(self.stop_order)
                self.stop_order = None

            # Check if in trending regime to allow entries
            if is_trending_regime:
                if current_cross > 0: # Buy signal: Fast SMA crosses above Slow SMA
                    self.log(f'BUY CREATE (Hurst Trend Regime & SMA Cross > 0), H={current_hurst:.3f}, Close={current_close:.2f}', doprint=True)
                    self.order = self.buy()
                elif current_cross < 0: # Sell signal: Fast SMA crosses below Slow SMA
                    self.log(f'SELL CREATE (Hurst Trend Regime & SMA Cross < 0), H={current_hurst:.3f}, Close={current_close:.2f}', doprint=True)
                    self.order = self.sell()
            # else: # In non-trending regime (H <= threshold) - Do nothing for entry
            #     pass

        else: # If IN A POSITION
            # Do nothing here - exits are handled by the trailing stop
            pass

    def stop(self):
        # Cleanup logic (same as before)
        if self.stop_order:
            self.log(f"Strategy stopped. Cancelling pending stop order ref: {self.stop_order.ref}", doprint=True)
            self.cancel(self.stop_order)
