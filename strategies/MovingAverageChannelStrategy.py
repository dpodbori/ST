# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'ma_period': st.number_input("Moving Average Period", value=30, min_value=1, step=1),
        'stop_loss_perc': st.number_input("Stop Loss Percentage", value=2.0, min_value=0.0, max_value=100.0) / 100,
        'take_profit_active': st.checkbox("Enable Take Profit based on Channel", value=True)
    }

# Define the Moving Average Channel Strategy
class MovingAverageChannelStrategy(bt.Strategy):
    params = (
        ('ma_period', 30),          # Period for the moving averages
        ('stop_loss_perc', 0.02),   # Stop loss percentage (e.g., 0.02 for 2%)
        ('take_profit_active', True), # Enable take profit based on channel
    )

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} | {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low

        self.order = None
        self.entryprice = None # Using entryprice for clarity
        self.entrycomm = None
        self.stop_order = None
        self.position_size_tracker = 0 # To track the size of the current position

        self.ma_high = bt.indicators.SimpleMovingAverage(
            self.datas[0].high, period=self.params.ma_period)
        self.ma_low = bt.indicators.SimpleMovingAverage(
            self.datas[0].low, period=self.params.ma_period)

        self.ma_high.plotinfo.plotname = 'MA High'
        self.ma_low.plotinfo.plotname = 'MA Low'

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            executed_price = order.executed.price
            executed_size = order.executed.size
            executed_value = order.executed.value
            executed_comm = order.executed.comm

            if order.isbuy():
                # Case 1: Buy to open a new long position
                if self.order and self.order.ref == order.ref and self.entryprice is None:
                    self.log(f'BUY ENTRY EXECUTED | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.entryprice = executed_price
                    self.entrycomm = executed_comm
                    self.position_size_tracker = executed_size
                    stop_price = self.entryprice * (1.0 - self.params.stop_loss_perc)
                    self.stop_order = self.sell(exectype=bt.Order.Stop, price=stop_price, size=self.position_size_tracker)
                    self.log(f'STOP LOSS PLACED for LONG | Price: {stop_price:.2f}')
                # Case 2: Buy to close a short position (Take Profit or other close signal)
                elif self.order and self.order.ref == order.ref and self.entryprice is not None and self.position_size_tracker < 0:
                    self.log(f'TAKE PROFIT (SHORT) EXECUTED / CLOSE SHORT | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.entryprice = None # Reset for next trade
                    self.position_size_tracker = 0
                    # self.stop_order should have been cancelled when TP order was placed
                # Case 3: Stop loss for a short position was hit
                elif self.stop_order and self.stop_order.ref == order.ref:
                    self.log(f'STOP LOSS (SHORT) HIT | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.stop_order = None
                    self.entryprice = None # Reset for next trade
                    self.position_size_tracker = 0

            elif order.issell():
                # Case 1: Sell to open a new short position
                if self.order and self.order.ref == order.ref and self.entryprice is None:
                    self.log(f'SELL SHORT ENTRY EXECUTED | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.entryprice = executed_price # Store entry price of short
                    self.entrycomm = executed_comm
                    self.position_size_tracker = executed_size # Will be negative
                    stop_price = self.entryprice * (1.0 + self.params.stop_loss_perc)
                    self.stop_order = self.buy(exectype=bt.Order.Stop, price=stop_price, size=abs(self.position_size_tracker))
                    self.log(f'STOP LOSS PLACED for SHORT | Price: {stop_price:.2f}')
                # Case 2: Sell to close a long position (Take Profit or other close signal)
                elif self.order and self.order.ref == order.ref and self.entryprice is not None and self.position_size_tracker > 0:
                    self.log(f'TAKE PROFIT (LONG) EXECUTED / CLOSE LONG | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.entryprice = None # Reset for next trade
                    self.position_size_tracker = 0
                    # self.stop_order should have been cancelled
                # Case 3: Stop loss for a long position was hit
                elif self.stop_order and self.stop_order.ref == order.ref:
                    self.log(f'STOP LOSS (LONG) HIT | Price: {executed_price:.2f}, Size: {executed_size}, Cost: {executed_value:.2f}, Comm: {executed_comm:.2f}')
                    self.stop_order = None
                    self.entryprice = None # Reset for next trade
                    self.position_size_tracker = 0

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.getstatusname()} (Ref: {order.ref})')
            if self.order and self.order.ref == order.ref: # If the failed order was one we were tracking (entry or TP)
                self.log(f'Tracked order {order.ref} failed.')
                # If it was an entry order, no SL would have been placed yet by this logic.
                # If it was a TP order, the original SL is still active. We might want to retry TP or let SL manage.
            elif self.stop_order and self.stop_order.ref == order.ref: # If a stop-loss order itself fails
                self.log('CRITICAL: Stop Loss Order FAILED. Position may be unprotected.')
                self.stop_order = None
                if self.position: # If still in a position
                    self.log('Attempting to close unprotected position immediately.')
                    self.order = self.close() # Emergency close

        # Reset the main order tracker if this order was the one being tracked
        if self.order and self.order.ref == order.ref:
            self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'TRADE PROFIT | GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
        # self.entryprice is reset in notify_order when a position-closing order completes

    def next(self):
        if len(self.ma_high) < self.params.ma_period : # Ensure MAs are calculated
             return

        if self.order: # An order (entry or TP) is pending
            return

        if not self.position: # Not in the market, look for entries
            if self.entryprice is not None: # Should be None if not in market and last trade closed properly
                self.log("Warning: Not in position, but entryprice is not None. Resetting.")
                self.entryprice = None # Defensive reset

            # --- Potential Buy Signal (Pullback) ---
            if self.datalow[0] <= self.ma_low[0] and self.dataclose[0] > self.ma_low[0]:
                if self.dataclose[0] < self.ma_high[0]:
                    self.log(f'BUY CREATE | Close: {self.dataclose[0]:.2f}')
                    self.order = self.buy()
            # --- Potential Sell Short Signal (Pullback) ---
            elif self.datahigh[0] >= self.ma_high[0] and self.dataclose[0] < self.ma_high[0]:
                if self.dataclose[0] > self.ma_low[0]:
                    self.log(f'SELL SHORT CREATE | Close: {self.dataclose[0]:.2f}')
                    self.order = self.sell()
        else: # Already in the market, manage position (check for Take Profit)
            if self.params.take_profit_active:
                current_pos_size = self.position.size # From broker
                if current_pos_size > 0:  # In a long position
                    if self.dataclose[0] >= self.ma_high[0]:
                        self.log(f'TAKE PROFIT (LONG) TRIGGER | Close: {self.dataclose[0]:.2f} >= MA High: {self.ma_high[0]:.2f}')
                        if self.stop_order: # Cancel existing stop loss
                            self.cancel(self.stop_order)
                            self.stop_order = None
                        self.order = self.sell(size=current_pos_size) # Place take profit order
                elif current_pos_size < 0:  # In a short position
                    if self.dataclose[0] <= self.ma_low[0]:
                        self.log(f'TAKE PROFIT (SHORT) TRIGGER | Close: {self.dataclose[0]:.2f} <= MA Low: {self.ma_low[0]:.2f}')
                        if self.stop_order: # Cancel existing stop loss
                            self.cancel(self.stop_order)
                            self.stop_order = None
                        self.order = self.buy(size=abs(current_pos_size)) # Place take profit order

    def stop(self):
        self.log(f'(MA Period {self.params.ma_period:2d}) Ending Value {self.broker.getvalue():.2f}')