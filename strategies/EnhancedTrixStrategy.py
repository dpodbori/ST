import backtrader as bt

import numpy as np
import streamlit as st


def show_parameters():
    return {
        'trix_period': st.number_input("TRIX Period", value=15, min_value=1, step=1),
        'trix_signal': st.number_input("TRIX Signal Period", value=9, min_value=1, step=1),
        'sma_period': st.number_input("SMA Period", value=30, min_value=1, step=1),
        'sma_slope_lookback': st.number_input("SMA Slope Lookback", value=3, min_value=1, step=1),
        'printlog': st.checkbox("Enable Logging", value=False)
    }

class EnhancedTrixStrategy(bt.Strategy):
    """
    Enhanced TRIX Strategy incorporating:
    1. TRIX Signal Line Crossover for entries/exits.
    2. SMA Trend Filter (Price vs SMA).
    3. SMA Slope Confirmation.
    4. N-Period High/Low Breakout Confirmation.
    5. TRIX Slope Threshold Filter.
    """
    params = (
        # TRIX Params
        ('trix_period', 15),
        ('trix_signal', 9),
        # SMA Trend Filter Params
        ('sma_period', 30),
        # Confirmation Params
        ('sma_slope_lookback', 3),    # Lookback for SMA slope calculation
        # Other Params
        ('printlog', False),     # Enable logging for debugging
    )

    def log(self, txt, dt=None, doprint=False):
        ''' Logging function for this strategy'''
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')

    def __init__(self):
        # Keep references to data lines
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low

        # --- Indicator Definitions ---

        # 1. SMA Trend Filter
        self.sma_filter = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.sma_period)

        # 2. TRIX and its Signal Line
        self.trix = bt.indicators.TRIX(
            self.datas[0], period=self.params.trix_period)
        self.trix_signal = bt.indicators.EMA(
            self.trix.trix, period=self.params.trix_signal) # Signal is EMA of TRIX line

        # 3. SMA Slope
        # Simple slope: Current SMA value - SMA value N periods ago
        self.sma_slope = self.sma_filter - self.sma_filter(-self.params.sma_slope_lookback)


        # --- Crossover Signals ---
        self.trix_signal_cross = bt.indicators.CrossOver(self.trix.trix, self.trix_signal)
        self.price_sma_cross = bt.indicators.CrossOver(self.dataclose, self.sma_filter) # For exits

        # --- State Variables ---
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.trade_count = 0

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.trade_count += 1
        self.log(f'TRADE {self.trade_count} PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def next(self):
        # Log current indicator values if needed for debugging
        # self.log(f'Close={self.dataclose[0]:.2f}, TRIX={self.trix.trix[0]:.4f}, Signal={self.trix_signal[0]:.4f}, SMA={self.sma_filter[0]:.2f}, SMA_Slope={self.sma_slope[0]:.4f}, TRIX_Slope={self.trix_slope[0]:.4f}, High={self.highest_high[-1]:.2f}, Low={self.lowest_low[-1]:.2f}')

        # Check if an order is pending
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # --- Potential Entry ---

            # Check for NaN values in indicators (can happen early in the backtest)
            if np.isnan(self.sma_slope[0]):
                return # Skip bar if indicators not ready


            # Long Entry Conditions
            long_signal_cross = self.trix_signal_cross[0] == 1.0
            long_trend_filter = self.dataclose[0] > self.sma_filter[0]
            long_sma_slope_confirm = self.sma_slope[0] > 0
            
            # Short Entry Conditions
            short_signal_cross = self.trix_signal_cross[0] == -1.0
            short_trend_filter = self.dataclose[0] < self.sma_filter[0]
            short_sma_slope_confirm = self.sma_slope[0] < 0

            if long_signal_cross and long_trend_filter and long_sma_slope_confirm:
                self.log(f'LONG ENTRY SIGNAL: TRIX/Sig Cross(1), Price>SMA, SMA Slope>0, Price>N-High')
                self.order = self.buy()

            elif short_signal_cross and short_trend_filter and short_sma_slope_confirm:
                self.log(f'SHORT ENTRY SIGNAL: TRIX/Sig Cross(-1), Price<SMA, SMA Slope<0, Price<N-Low')
                self.order = self.sell()

        else:
            # --- Potential Exit ---
            # Exit based on TRIX/Signal cross OR Price/SMA cross

            # Check for NaN in crossover indicators before using them for exits
            if np.isnan(self.trix_signal_cross[0]) or np.isnan(self.price_sma_cross[0]):
                return

            # Exit Long: TRIX crosses below Signal OR Price crosses below SMA
            if self.position.size > 0: # If long
                exit_signal = self.trix_signal_cross[0] == -1.0 or self.price_sma_cross[0] == -1.0
                if exit_signal:
                    exit_reason = ""
                    if self.trix_signal_cross[0] == -1.0: exit_reason += "TRIX Cross Below Signal "
                    if self.price_sma_cross[0] == -1.0: exit_reason += "Price Cross Below SMA "
                    self.log(f'LONG EXIT SIGNAL: {exit_reason}')
                    self.order = self.close()

            # Exit Short: TRIX crosses above Signal OR Price crosses above SMA
            elif self.position.size < 0: # If short
                 exit_signal = self.trix_signal_cross[0] == 1.0 or self.price_sma_cross[0] == 1.0
                 if exit_signal:
                    exit_reason = ""
                    if self.trix_signal_cross[0] == 1.0: exit_reason += "TRIX Cross Above Signal "
                    if self.price_sma_cross[0] == 1.0: exit_reason += "Price Cross Above SMA "
                    self.log(f'SHORT EXIT SIGNAL: {exit_reason}')
                    self.order = self.close()

