# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'key_ma_period': st.number_input("Key MA Period", value=50, min_value=1, step=1),
        'filter_ma_period': st.number_input("Filter MA Period", value=200, min_value=1, step=1),
        'ma_type': st.selectbox("MA Type", options=['SMA', 'EMA']),
        'order_percentage': st.number_input("Order Percentage", value=0.95, min_value=0.01, max_value=1.0, step=0.01),
        'stop_loss_pct': st.number_input("Stop Loss Percentage", value=0.03, min_value=0.01, max_value=0.5, step=0.01)
    }

# Define the MA Bounce Strategy
class MaBounceStrategy(bt.Strategy):
    params = (
        ('key_ma_period', 50),     # MA for bounce (e.g., 50 SMA)
        ('filter_ma_period', 200), # Longer MA for trend filter (e.g., 200 SMA)
        ('ma_type', 'SMA'),        # Type of MA ('SMA' or 'EMA')
        ('order_percentage', 0.95),
        ('stop_loss_pct', 0.03)    # Example: 3% stop loss below entry price
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.data_low = self.datas[0].low
        self.data_high = self.datas[0].high # Needed if implementing short side

        # Select MA type based on params
        ma_indicator = bt.indicators.SMA if self.params.ma_type == 'SMA' else bt.indicators.EMA

        # Initialize the key MA and filter MA
        self.key_ma = ma_indicator(self.data_close, period=self.params.key_ma_period)
        self.filter_ma = ma_indicator(self.data_close, period=self.params.filter_ma_period)

        # Order tracking and stop price
        self.order = None
        self.stop_price = None

    def log(self, txt, dt=None):
        ''' Logging function '''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]: return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')
                # Set stop loss price after buy order executes
                self.stop_price = order.executed.price * (1.0 - self.params.stop_loss_pct)
                self.log(f'Stop Loss set at {self.stop_price:.2f}')

            elif order.issell():
                 self.log(f'SELL EXECUTED (Exit/Stop), Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}')

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: Status {order.getstatusname()}')

        # Reset order tracking after completion/failure
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed: return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')
        # Reset stop price when trade is closed
        self.stop_price = None


    def next(self):
        # Check if indicators have enough data
        if len(self.data_close) < self.params.filter_ma_period:
            return

        # Check for open orders
        if self.order:
            return

        # --- Check Stop Loss ---
        if self.position and self.stop_price is not None:
            if self.data_close[0] < self.stop_price:
                self.log(f'STOP LOSS HIT: Close={self.data_close[0]:.2f}, Stop Price={self.stop_price:.2f}')
                self.order = self.close() # Close position
                return # Exit check for this bar

        # --- Entry Logic ---
        if not self.position:
            # 1. Confirm Uptrend State (Price > Filter MA, Key MA > Filter MA - optional but good)
            uptrend_confirmed = (self.data_close[0] > self.filter_ma[0] and
                                 self.key_ma[0] > self.filter_ma[0]) # Added Key > Filter condition
                                 # Optional: Check slope of key_ma > 0

            if uptrend_confirmed:
                # 2. Check for Pullback: Low price touched or went below the key MA in the previous bar
                touched_ma_prev_bar = self.data_low[-1] <= self.key_ma[-1]
                
                # 3. Check for Rejection/Entry Trigger: Price closes back ABOVE the key MA on the current bar
                closed_above_ma_curr_bar = self.data_close[0] > self.key_ma[0]

                if touched_ma_prev_bar and closed_above_ma_curr_bar:
                    self.log(f'BUY SIGNAL (MA Bounce): Close={self.data_close[0]:.2f}, Touched Key MA {self.params.key_ma_period}={self.key_ma[-1]:.2f} on previous bar, Closed above on current bar.')
                    cash = self.broker.get_cash()
                    size = (cash * self.params.order_percentage) / self.data_close[0]
                    self.log(f'Calculating Buy Size: Cash={cash:.2f}, Close={self.data_close[0]:.2f}, Percentage={self.params.order_percentage}, Size={size:.6f}')
                    self.order = self.buy(size=size)

        # --- Exit Logic (Alternative/Additional) ---
        # else: # Already in position
            # Example: Exit if price closes back below the key MA (could be used instead of % stop)
            # if self.data_close[0] < self.key_ma[0]:
            #     self.log(f'SELL SIGNAL (Exit - Close below Key MA): Close={self.data_close[0]:.2f}, Key MA={self.key_ma[0]:.2f}')
            #     self.order = self.close()
