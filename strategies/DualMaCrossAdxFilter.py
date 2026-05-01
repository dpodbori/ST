import backtrader as bt
import backtrader.indicators as btind  # Alias for clarity
import streamlit as st


def show_parameters():
    return {
        'fast_ma_period': st.number_input("Fast MA Period", value=9, min_value=1, step=1),
        'slow_ma_period': st.number_input("Slow MA Period", value=21, min_value=1, step=1),
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'ma_type': st.selectbox("Moving Average Type", ['EMA', 'SMA', 'DEMA', 'TEMA', 'WMA']),
    }


class DualMaCrossAdxFilter(bt.Strategy):
    """
    Implements a Dual Moving Average Crossover strategy filtered by ADX.

    Entry Conditions:
    - Long: Fast MA crosses above Slow MA AND ADX > adx_threshold.
    - Short: Fast MA crosses below Slow MA AND ADX > adx_threshold.

    Exit Conditions (Simple):
    - Exit Long: Fast MA crosses below Slow MA.
    - Exit Short: Fast MA crosses above Slow MA.
    """
    params = (
        ('fast_ma_period', 9),   # Period for the fast moving average
        ('slow_ma_period', 21),  # Period for the slow moving average
        ('adx_period', 14),      # Period for ADX calculation
        ('adx_threshold', 25.0), # Minimum ADX value to enable trades
        ('ma_type', 'EMA'),      # Type of Moving Average: 'EMA', 'SMA', 'DEMA', 'TEMA', etc.
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} | {txt}')

    def __init__(self):
        """Initializes the strategy"""
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low

        # Keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Select Moving Average type
        ma_map = {
            'EMA': btind.ExponentialMovingAverage,
            'SMA': btind.SimpleMovingAverage,
            'DEMA': btind.DoubleExponentialMovingAverage,
            'TEMA': btind.TripleExponentialMovingAverage,
            'WMA': btind.WeightedMovingAverage,
            # Add other MA types supported by backtrader if needed
        }
        ma_indicator = ma_map.get(self.params.ma_type, btind.SimpleMovingAverage) # Default to SMA if invalid type

        # Instantiate Moving Averages
        self.fast_ma = ma_indicator(period=self.params.fast_ma_period)
        self.slow_ma = ma_indicator(period=self.params.slow_ma_period)

        # Instantiate ADX indicator
        self.adx = btind.AverageDirectionalMovementIndex(period=self.params.adx_period)

        # Instantiate Crossover indicator for MAs
        self.ma_crossover = btind.CrossOver(self.fast_ma, self.slow_ma)

        # Optional: Calculate minimum periods needed for indicators to be ready
        self.min_periods = max(self.params.fast_ma_period, self.params.slow_ma_period, self.params.adx_period * 2) # ADX needs more time

    def notify_order(self, order):
        """Handles order notifications"""
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')

            self.bar_executed = len(self) # Bar number when order was executed

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')

        # Reset order variable after completion/failure
        self.order = None

    def notify_trade(self, trade):
        """Handles trade notifications"""
        if not trade.isclosed:
            return

        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def next(self):
        """Called on each bar/candle"""
        # Log closing price
        # self.log(f'Close: {self.data_close[0]:.2f}')

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if indicators are ready
        # Using indicator length check is more robust than self length
        if len(self.fast_ma) < self.params.fast_ma_period or \
           len(self.slow_ma) < self.params.slow_ma_period or \
           len(self.adx) < self.params.adx_period * 2: # ADX needs longer warmup
            return

        # Check if we are in the market
        if not self.position:
            # Not in the market, check for entry signals

            # Long Entry Condition: Fast MA crosses above Slow MA AND ADX > threshold
            if self.ma_crossover[0] > 0 and self.adx[0] > self.params.adx_threshold:
                self.log(f'LONG ENTRY SIGNAL: MA Cross={self.ma_crossover[0]:.0f}, ADX={self.adx[0]:.2f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy()

            # Short Entry Condition: Fast MA crosses below Slow MA AND ADX > threshold
            elif self.ma_crossover[0] < 0 and self.adx[0] > self.params.adx_threshold:
                self.log(f'SHORT ENTRY SIGNAL: MA Cross={self.ma_crossover[0]:.0f}, ADX={self.adx[0]:.2f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()

        else:
            # Already in the market, check for exit signals

            # Exit Long Condition: Fast MA crosses below Slow MA
            if self.position.size > 0 and self.ma_crossover[0] < 0:
                self.log(f'CLOSE LONG SIGNAL: MA Cross={self.ma_crossover[0]:.0f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.close()

            # Exit Short Condition: Fast MA crosses above Slow MA
            elif self.position.size < 0 and self.ma_crossover[0] > 0:
                self.log(f'CLOSE SHORT SIGNAL: MA Cross={self.ma_crossover[0]:.0f}')
                # Keep track of the created order to avoid a 2nd order
                self.order = self.close()

    def stop(self):
        """Called when strategy finishes"""
        self.log(f'(Fast MA Period {self.params.fast_ma_period:2d}) (Slow MA Period {self.params.slow_ma_period:2d}) (ADX Period {self.params.adx_period:2d}) (ADX Threshold {self.params.adx_threshold:.1f}) Ending Value {self.broker.getvalue():.2f}')

