import backtrader as bt
import streamlit as st


def show_parameters():  
    return {
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25, min_value=0, step=1),
        'boll_period': st.number_input("Bollinger Bands Period", value=20, min_value=1, step=1),
        'boll_devfactor': st.number_input("Bollinger Bands Deviation Factor", value=2.0, min_value=0.0, step=0.1),
        'confirmation_bars': st.number_input("Confirmation Bars", value=3, min_value=1, step=1),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=2.0, min_value=0.0, max_value=100.0) / 100,
    }

class ADXTrendStrengthWithFilters(bt.Strategy):
    params = (
        ('adx_period', 14),
        ('adx_threshold', 25),
        ('boll_period', 20),          # Period for Bollinger Bands
        ('boll_devfactor', 2),        # Deviation factor for Bollinger Bands
        ('confirmation_bars', 3),     # Number of bars to confirm reversal signal
        ('trail_percent', 0.02),      # Trailing stop percentage (2% by default)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f"{dt.isoformat()} - {txt}")

    def __init__(self):
        self.dataclose = self.datas[0].close

        # Initialize ADX, PlusDI, and MinusDI
        self.adx = bt.indicators.ADX(self.datas[0], period=self.params.adx_period)
        self.plusdi = bt.indicators.PlusDI(self.datas[0], period=self.params.adx_period)
        self.minusdi = bt.indicators.MinusDI(self.datas[0], period=self.params.adx_period)
        
        # Bollinger Bands to measure market range
        self.boll = bt.indicators.BollingerBands(self.datas[0], 
                                                 period=self.params.boll_period, 
                                                 devfactor=self.params.boll_devfactor)
        
        # Counter to confirm reversal signals
        self.reversal_counter = 0

        # Track market and trailing orders
        self.order = None
        self.trail_order = None

    def notify_order(self, order):
        # Skip processing if order is submitted or accepted
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY EXECUTED at {order.executed.price:.2f}")
            elif order.issell():
                self.log(f"SELL EXECUTED at {order.executed.price:.2f}")
            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order Canceled/Margin/Rejected: {order.getstatusname()}")
            
        # Reset order reference if it was our order.
        if order == self.order:
            self.order = None
        if order == self.trail_order:
            self.trail_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"Trade Profit: GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}")

    def cancel_trail(self):
        if self.trail_order:
            self.log("Canceling active trailing stop order.")
            self.cancel(self.trail_order)
            self.trail_order = None

    def next(self):
        # Skip processing if an order is pending
        if self.order:
            return

        # If there is an open position, ensure trailing stop order is active.
        if self.position:
            if not self.trail_order:
                if self.position.size > 0:
                    self.log(f"Placing trailing stop order for long position at {self.dataclose[0]:.2f}")
                    self.trail_order = self.sell(
                        exectype=bt.Order.StopTrail,
                        trailpercent=self.params.trail_percent)
                elif self.position.size < 0:
                    self.log(f"Placing trailing stop order for short position at {self.dataclose[0]:.2f}")
                    self.trail_order = self.buy(
                        exectype=bt.Order.StopTrail,
                        trailpercent=self.params.trail_percent)
            # If in position, we also don't want to open a new trade.
            return

        # Ensure sufficient data is available
        if len(self) < max(self.params.adx_period, self.params.boll_period):
            return

        # Check if the market is trending strongly via ADX
        if self.adx[0] < self.params.adx_threshold:
            self.log(f"Low ADX ({self.adx[0]:.2f}). Market trending weakly. Skipping trade.")
            self.reversal_counter = 0  # Reset confirmation counter if market weakens
            return

        # Check for range-bound market using Bollinger Band width.
        boll_width = self.boll.top[0] - self.boll.bot[0]
        if boll_width < 0.01 * self.dataclose[0]:  # Example threshold: 1% of price
            self.log(f"Bollinger Bands narrow ({boll_width:.2f}). Market is range-bound. Skipping trade.")
            self.reversal_counter = 0
            return

        # Define directional signal
        long_signal = self.plusdi[0] > self.minusdi[0]
        short_signal = self.minusdi[0] > self.plusdi[0]

        # Confirm the directional signal persists for a number of bars
        if (long_signal and self.position.size <= 0) or (short_signal and self.position.size >= 0):
            self.reversal_counter += 1
        else:
            self.reversal_counter = 0

        # Check if confirmation condition is met
        if self.reversal_counter < self.params.confirmation_bars:
            return  # Wait for more confirmation

        # If a reversal condition is met, first cancel any existing trailing orders.
        self.cancel_trail()

        # Execute orders when confirmation condition is met
        if long_signal:
            if self.position and self.position.size < 0:
                self.log(f"Reversing to long at {self.dataclose[0]:.2f}")
                self.order = self.buy()  # Reverse position (buy closes short and opens long)
            elif not self.position:
                self.log(f"Going long at {self.dataclose[0]:.2f}")
                self.order = self.buy()
        elif short_signal:
            if self.position and self.position.size > 0:
                self.log(f"Reversing to short at {self.dataclose[0]:.2f}")
                self.order = self.sell()  # Reverse position (sell closes long and opens short)
            elif not self.position:
                self.log(f"Going short at {self.dataclose[0]:.2f}")
                self.order = self.sell()

    def stop(self):
        self.log(f"Ending Portfolio Value: {self.broker.getvalue():.2f}")

