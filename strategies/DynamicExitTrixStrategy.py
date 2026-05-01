import backtrader as bt
import numpy as np
import streamlit as st


def show_parameters():
    return {
        'trix_period': st.number_input("TRIX Period", value=15, min_value=1, step=1),
        'trix_signal': st.number_input("TRIX Signal Period", value=9, min_value=1, step=1),
        'sma_period': st.number_input("SMA Period", value=30, min_value=1, step=1),
        'sma_slope_lookback': st.number_input("SMA Slope Lookback", value=3, min_value=1, step=1),
        'confirmation_high_low_period': st.number_input("Confirmation High/Low Period", value=20, min_value=1, step=1),

        # Exit parameters
        'atr_period': st.number_input("ATR Period", value=14, min_value=1, step=1),
        'atr_stop_mult': st.number_input("ATR Stop Multiplier", value=5.0, min_value=0.0, step=0.1),
        'atr_target_mult': st.number_input("ATR Target Multiplier (0 to disable)", value=20.0, min_value=0.0, step=0.1),
        'time_stop_bars': st.number_input("Time Stop Bars (0 to disable)", value=90, min_value=0, step=1),

        # Other parameters
        'printlog': st.checkbox("Enable Logging", value=False)
    }
    
class DynamicExitTrixStrategy(bt.Strategy):
    """
    Enhanced TRIX Strategy with Dynamic Exits:
    - Entry: Same as EnhancedTrixStrategy (TRIX/Signal Cross + Confirmations)
    - Exit: Replaced with ATR Trailing Stop, optional ATR Profit Target, and optional Time Stop.
    """
    params = (
        # --- Entry Params (from EnhancedTrixStrategy) ---
        ('trix_period', 15),
        ('trix_signal', 9),
        ('sma_period', 30),
        ('sma_slope_lookback', 3),
        ('confirmation_high_low_period', 20),

        # --- Exit Params ---
        ('atr_period', 14),           # Lookback period for ATR
        ('atr_stop_mult', 5.0),       # ATR multiplier for initial/trailing stop
        ('atr_target_mult', 20.0),     # ATR multiplier for profit target (0 or None to disable)
        ('time_stop_bars', 90),       # Max bars to hold trade (0 or None to disable)

        # --- Other Params ---
        ('printlog', False),          # Enable logging for debugging
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

        # --- Entry Indicators (same as EnhancedTrixStrategy) ---
        self.sma_filter = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.params.sma_period)
        self.trix = bt.indicators.TRIX(self.datas[0], period=self.params.trix_period)
        self.trix_signal = bt.indicators.EMA(self.trix.trix, period=self.params.trix_signal)
        self.sma_slope = self.sma_filter - self.sma_filter(-self.params.sma_slope_lookback)
        self.highest_high = bt.indicators.Highest(self.datahigh, period=self.params.confirmation_high_low_period)
        self.lowest_low = bt.indicators.Lowest(self.datalow, period=self.params.confirmation_high_low_period)
        self.trix_signal_cross = bt.indicators.CrossOver(self.trix.trix, self.trix_signal)

        # --- Exit Indicator ---
        self.atr = bt.indicators.AverageTrueRange(self.datas[0], period=self.params.atr_period)

        # --- State Variables ---
        self.order = None
        self.trade_count = 0
        self.entry_bar = None
        self.entry_price = None
        self.initial_stop_price = None
        self.take_profit_price = None
        self.current_trail_stop = None
        self.atr_at_entry_signal = None # Store ATR value when signal occurs


    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            # --- Set Exit Prices on Entry Completion ---
            if order.isbuy() and self.position.size > 0 and self.entry_bar is None: # Check if it's the entry order completion
                self.entry_price = order.executed.price
                self.entry_comm = order.executed.comm
                self.entry_bar = len(self) # Bar number of execution

                if self.atr_at_entry_signal is not None and not np.isnan(self.atr_at_entry_signal):
                    stop_dist = self.params.atr_stop_mult * self.atr_at_entry_signal
                    self.initial_stop_price = self.entry_price - stop_dist
                    self.current_trail_stop = self.initial_stop_price # Initialize trail stop

                    if self.params.atr_target_mult and self.params.atr_target_mult > 0:
                        target_dist = self.params.atr_target_mult * self.atr_at_entry_signal
                        self.take_profit_price = self.entry_price + target_dist
                    else:
                         self.take_profit_price = None # Disable TP if mult is 0 or None

                    self.log(f'BUY EXECUTED @ {self.entry_price:.2f}, Initial Stop @ {self.initial_stop_price:.2f}, Trail @ {self.current_trail_stop:.2f}, Target @ {self.take_profit_price if self.take_profit_price else "N/A"}')
                else:
                    self.log(f'BUY EXECUTED @ {self.entry_price:.2f}, BUT ATR WAS NaN - CANNOT SET EXITS!')
                    # Consider closing position immediately or handle differently if ATR isn't ready
                    # self.close()
                    pass


            elif order.issell() and self.position.size < 0 and self.entry_bar is None: # Check if it's the entry order completion
                self.entry_price = order.executed.price
                self.entry_comm = order.executed.comm
                self.entry_bar = len(self) # Bar number of execution

                if self.atr_at_entry_signal is not None and not np.isnan(self.atr_at_entry_signal):
                    stop_dist = self.params.atr_stop_mult * self.atr_at_entry_signal
                    self.initial_stop_price = self.entry_price + stop_dist
                    self.current_trail_stop = self.initial_stop_price # Initialize trail stop

                    if self.params.atr_target_mult and self.params.atr_target_mult > 0:
                        target_dist = self.params.atr_target_mult * self.atr_at_entry_signal
                        self.take_profit_price = self.entry_price - target_dist
                    else:
                        self.take_profit_price = None # Disable TP

                    self.log(f'SELL EXECUTED @ {self.entry_price:.2f}, Initial Stop @ {self.initial_stop_price:.2f}, Trail @ {self.current_trail_stop:.2f}, Target @ {self.take_profit_price if self.take_profit_price else "N/A"}')
                else:
                    self.log(f'SELL EXECUTED @ {self.entry_price:.2f}, BUT ATR WAS NaN - CANNOT SET EXITS!')
                    # self.close()
                    pass

            # --- Reset state on trade closure ---
            elif not self.position: # If order completion resulted in flat position
                if order.isbuy() : self.log(f'BUY TO CLOSE EXECUTED @ {order.executed.price:.2f}')
                if order.issell() : self.log(f'SELL TO CLOSE EXECUTED @ {order.executed.price:.2f}')
                self.entry_bar = None
                self.entry_price = None
                self.initial_stop_price = None
                self.take_profit_price = None
                self.current_trail_stop = None
                self.atr_at_entry_signal = None


        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')

        self.order = None # Reset order tracking

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.trade_count += 1
        self.log(f'TRADE {self.trade_count} PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def next(self):
        # Check if an order is pending
        if self.order:
            return

        # Check if indicators are ready
        if np.isnan(self.sma_slope[0]) or \
           np.isnan(self.highest_high[-1]) or \
           np.isnan(self.lowest_low[-1]) or \
           np.isnan(self.trix_signal_cross[0]) or \
           np.isnan(self.atr[0]): # Added ATR check
            return

        # --- Exit Logic (Check before Entry Logic) ---
        if self.position:
            exit_reason = None
            current_atr = self.atr[0]

            # Make sure we have exit levels set (entry order completed successfully)
            if self.current_trail_stop is None:
                 self.log("Position exists but exit levels not set - skipping exit checks this bar.")
                 return

            if self.position.size > 0: # --- Long Position Exit Checks ---
                # 1. Profit Target
                if self.take_profit_price is not None and self.datahigh[0] >= self.take_profit_price:
                    exit_reason = f"Profit Target Hit >= {self.take_profit_price:.2f}"
                else:
                    # 2. ATR Trailing Stop Update & Check
                    potential_new_stop = self.dataclose[0] - self.params.atr_stop_mult * current_atr
                    self.current_trail_stop = max(self.current_trail_stop, potential_new_stop)
                    if self.dataclose[0] <= self.current_trail_stop:
                        exit_reason = f"Trailing Stop Hit <= {self.current_trail_stop:.2f}"
                    # 3. Time Stop (only if not stopped/targeted yet)
                    elif self.params.time_stop_bars and (len(self) - self.entry_bar >= self.params.time_stop_bars):
                         exit_reason = f"Time Stop Hit ({len(self) - self.entry_bar} >= {self.params.time_stop_bars} bars)"

            elif self.position.size < 0: # --- Short Position Exit Checks ---
                 # 1. Profit Target
                if self.take_profit_price is not None and self.datalow[0] <= self.take_profit_price:
                    exit_reason = f"Profit Target Hit <= {self.take_profit_price:.2f}"
                else:
                    # 2. ATR Trailing Stop Update & Check
                    potential_new_stop = self.dataclose[0] + self.params.atr_stop_mult * current_atr
                    self.current_trail_stop = min(self.current_trail_stop, potential_new_stop)
                    if self.dataclose[0] >= self.current_trail_stop:
                        exit_reason = f"Trailing Stop Hit >= {self.current_trail_stop:.2f}"
                     # 3. Time Stop (only if not stopped/targeted yet)
                    elif self.params.time_stop_bars and (len(self) - self.entry_bar >= self.params.time_stop_bars):
                         exit_reason = f"Time Stop Hit ({len(self) - self.entry_bar} >= {self.params.time_stop_bars} bars)"

            # --- Execute Exit ---
            if exit_reason:
                self.log(f"CLOSE {'LONG' if self.position.size > 0 else 'SHORT'} SIGNAL: {exit_reason}")
                self.order = self.close()


        # --- Entry Logic ---
        elif not self.position: # Only check entries if not already in a position
            # Long Entry Conditions (same as EnhancedTrixStrategy)
            long_signal_cross = self.trix_signal_cross[0] == 1.0
            long_trend_filter = self.dataclose[0] > self.sma_filter[0]
            long_sma_slope_confirm = self.sma_slope[0] > 0
            long_high_confirm = self.dataclose[0] > self.highest_high[-1]
            
            # Short Entry Conditions (same as EnhancedTrixStrategy)
            short_signal_cross = self.trix_signal_cross[0] == -1.0
            short_trend_filter = self.dataclose[0] < self.sma_filter[0]
            short_sma_slope_confirm = self.sma_slope[0] < 0
            short_low_confirm = self.dataclose[0] < self.lowest_low[-1]

            if long_signal_cross and long_trend_filter and long_sma_slope_confirm and long_high_confirm:
                self.log(f'LONG ENTRY SIGNAL: Conditions Met')
                self.atr_at_entry_signal = self.atr[0] # Store ATR for notify_order
                self.order = self.buy()

            elif short_signal_cross and short_trend_filter and short_sma_slope_confirm and short_low_confirm:
                self.log(f'SHORT ENTRY SIGNAL: Conditions Met')
                self.atr_at_entry_signal = self.atr[0] # Store ATR for notify_order
                self.order = self.sell()


