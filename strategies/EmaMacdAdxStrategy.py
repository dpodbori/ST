import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'ema_fast_period': st.number_input("Fast EMA Period", value=12, min_value=1, step=1),
        'ema_slow_period': st.number_input("Slow EMA Period", value=26, min_value=1, step=1),
        'macd_fast_period': st.number_input("MACD Fast Period", value=12, min_value=1, step=1),
        'macd_slow_period': st.number_input("MACD Slow Period", value=26, min_value=1, step=1),
        'macd_signal_period': st.number_input("MACD Signal Period", value=9, min_value=1, step=1),
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=30.0, min_value=0.0, step=0.1),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=0.05, min_value=0.01, max_value=0.5, step=0.01), # 5% default
        'printlog': st.checkbox("Enable Logging", value=True)
    }

class EmaMacdAdxStrategy(bt.Strategy):
    """
    EMA Crossover Strategy with MACD and ADX Filters and Trailing Stop-Loss.
    - Long Entry: Fast EMA > Slow EMA AND MACD Line > Signal Line AND ADX > Threshold
    - Short Entry: Fast EMA < Slow EMA AND MACD Line < Signal Line AND ADX > Threshold
    - Exit:
        - Opposite EMA cross OR MACD cross reversal (Indicator Exit)
        - OR Price hits trailing stop level (Stop Exit)
    """
    params = (
        ('ema_fast_period', 12),
        ('ema_slow_period', 26),
        ('macd_fast_period', 12),
        ('macd_slow_period', 26),
        ('macd_signal_period', 9),
        ('adx_period', 14),
        ('adx_threshold', 30.0),
        ('trail_percent', 0.05), # Trailing stop percentage (e.g., 0.05 for 5%)
        ('printlog', True),      # Enable/Disable logging
    )

    def __init__(self):
        # Keep references to the closing prices
        self.dataclose = self.datas[0].close

        # Keep track of pending orders and buy price/commission
        self.order = None
        self.stop_order = None # To track the trailing stop order
        self.buyprice = None
        self.buycomm = None

        # --- Indicator Definitions ---
        self.ema_fast = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.params.ema_fast_period)
        self.ema_slow = bt.indicators.ExponentialMovingAverage(
            self.datas[0], period=self.params.ema_slow_period)
        self.macd = bt.indicators.MACDHisto(
            self.datas[0],
            period_me1=self.params.macd_fast_period,
            period_me2=self.params.macd_slow_period,
            period_signal=self.params.macd_signal_period)
        self.adx = bt.indicators.AverageDirectionalMovementIndex(
            self.datas[0], period=self.params.adx_period)

    def log(self, txt, dt=None, doprint=False):
        ''' Logging function for this strategy'''
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        ''' Handles order notifications '''
        # --- Handle Entry Order ---
        if order.status in [order.Submitted, order.Accepted]:
            # An order is active; return
            return

        # --- Handle Completed Order ---
        if order.status == order.Completed:
            if order.isbuy(): # --- Buy Order Completed ---
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm

                # Place Trailing Stop Sell Order
                if self.params.trail_percent:
                    self.log(f'>>> Placing SELL STOP TRAIL Order at {self.params.trail_percent * 100:.2f}%')
                    self.stop_order = self.sell(exectype=bt.Order.StopTrail,
                                                trailpercent=self.params.trail_percent)
                    # Log reference for debugging if needed
                    # self.log(f'>>> Sell StopTrail Ref: {self.stop_order.ref}')


            elif order.issell(): # --- Sell Order Completed ---
                # Check if it's an initial short sell or the closing sell of a long trade
                is_closing_order = self.buyprice is not None # Simple check if we logged a buy price for this trade cycle
                is_stop_trail_execution = order.ref == getattr(self.stop_order, 'ref', None) # Check if it matches our stop order ref

                if is_stop_trail_execution:
                     self.log(f'>>> SELL STOP TRAIL EXECUTED, Price: {order.executed.price:.2f}')
                     self.stop_order = None # Reset stop order tracker
                elif not is_closing_order: # Initial short sell order
                     self.log(
                         f'SELL SHORT EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                     )
                     # Place Trailing Stop Buy Order
                     if self.params.trail_percent:
                          self.log(f'>>> Placing BUY STOP TRAIL Order at {self.params.trail_percent * 100:.2f}%')
                          self.stop_order = self.buy(exectype=bt.Order.StopTrail,
                                                     trailpercent=self.params.trail_percent)
                          # self.log(f'>>> Buy StopTrail Ref: {self.stop_order.ref}')
                else: # Just a normal closing sell order (from indicator exit in next())
                    self.log(
                        f'SELL CLOSE EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                    )
                    self.buyprice = None # Reset buy price for next trade
                    self.buycomm = None

            # Reset main order tracker regardless of buy/sell if completed
            self.order = None


        # --- Handle Non-Completed Order (StopTrail specific logic) ---
        # Check if the order that failed/was cancelled was our trailing stop
        is_stop_trail_order = order.ref == getattr(self.stop_order, 'ref', None)

        if order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}, Ref: {order.ref}')
            # If the cancelled/rejected order was our tracked stop order, clear the tracker
            if is_stop_trail_order:
                self.log('>>> Trailing Stop Order Canceled/Margin/Rejected - Resetting tracker')
                self.stop_order = None
            # If the main entry/exit order failed, reset self.order
            elif self.order and order.ref == self.order.ref:
                 self.order = None


    def notify_trade(self, trade):
        ''' Handles trade notifications '''
        if not trade.isclosed:
            return # Ignore trades that are not yet closed

        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
        # Ensure stop order tracker is reset when a trade closes
        self.stop_order = None
        # Reset buy price info after trade closes
        self.buyprice = None
        self.buycomm = None


    def next(self):
        ''' Core strategy logic executed on each bar '''
        # Check if an order (entry or primary exit) is pending
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # --- Potential LONG Entry ---
            long_condition_1 = self.ema_fast[0] > self.ema_slow[0]
            long_condition_2 = self.macd.macd[0] > self.macd.signal[0]
            long_condition_3 = self.adx.adx[0] > self.params.adx_threshold

            if long_condition_1 and long_condition_2 and long_condition_3:
                self.log(f'BUY CREATE, Price: {self.dataclose[0]:.2f}')
                self.order = self.buy()
                # Stop order is placed in notify_order *after* this buy executes

            # --- Potential SHORT Entry ---
            else: # Only check short if not entering long
                short_condition_1 = self.ema_fast[0] < self.ema_slow[0]
                short_condition_2 = self.macd.macd[0] < self.macd.signal[0]
                short_condition_3 = self.adx.adx[0] > self.params.adx_threshold

                if short_condition_1 and short_condition_2 and short_condition_3:
                    self.log(f'SELL CREATE (Short), Price: {self.dataclose[0]:.2f}')
                    self.order = self.sell()
                    # Stop order is placed in notify_order *after* this sell executes

        else: # Already in the market, check for *indicator-based* exits
              # The trailing stop exit is handled by the broker simulation via the StopTrail order

            # --- Indicator-based EXIT for LONG position ---
            if self.position.size > 0:
                long_exit_condition_1 = self.ema_fast[0] < self.ema_slow[0]
                long_exit_condition_2 = self.macd.macd[0] < self.macd.signal[0]

                if long_exit_condition_1 or long_exit_condition_2:
                    self.log(f'INDICATOR EXIT - CLOSE LONG CREATE, Price: {self.dataclose[0]:.2f}')
                    # self.close() will automatically cancel the associated stop trail order
                    self.order = self.close()

            # --- Indicator-based EXIT for SHORT position ---
            elif self.position.size < 0:
                short_exit_condition_1 = self.ema_fast[0] > self.ema_slow[0]
                short_exit_condition_2 = self.macd.macd[0] > self.macd.signal[0]

                if short_exit_condition_1 or short_exit_condition_2:
                    self.log(f'INDICATOR EXIT - CLOSE SHORT CREATE, Price: {self.dataclose[0]:.2f}')
                    # self.close() will automatically cancel the associated stop trail order
                    self.order = self.close()

