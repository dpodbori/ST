import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'stop_loss_pct': st.number_input("Stop Loss Percentage", value=2.0, min_value=0.0, max_value=100.0) / 100,
    }

class ADX_ADXR_BBPct_Strategy(bt.Strategy):
    params = (
        ('stop_loss_pct', 2.0),  # Percentage for stop loss (e.g., 2.0 for 2%)
    )

    def log(self, txt: str, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} {txt}')

    def __init__(self):
        # Indicators
        self.adx = bt.indicators.ADX(self.datas[0], period=14, movav=bt.indicators.SMMA)
        self.adxr = bt.indicators.ADXR(self.datas[0], period=14, movav=bt.indicators.SMMA)
        self.bb_pct = bt.indicators.BollingerBandsPct(
            self.datas[0], period=20, devfactor=2.0, movav=bt.indicators.SMA)

        # Order trackers
        self.entry_order = None     # Tracks the main entry/exit order initiated by strategy logic
        self.stop_loss_order = None # Tracks the active stop loss order
        self.bar_executed = 0       # Bar of last trade execution

    def notify_order(self, order):
        dt_str = self.datas[0].datetime.datetime(0).isoformat()

        if order.status in [order.Submitted, order.Accepted]:
            # An order has been submitted/accepted - Nothing to do for now
            # self.log(f'{dt_str} Order {order.getstatusname()}: Ref {order.ref}')
            return

        # Check if an order has been completed
        if order.status == order.Completed:
            fill_price = order.executed.price
            fill_size = order.executed.size # Note: size is signed (positive for buy, negative for sell)
            comm = order.executed.comm

            if order.isbuy():
                self.log(f'{dt_str} BUY EXECUTED, Price: {fill_price:.2f}, Size: {fill_size:.2f}, Comm: {comm:.2f}')
            else:  # Sell
                self.log(f'{dt_str} SELL EXECUTED, Price: {fill_price:.2f}, Size: {fill_size:.2f}, Comm: {comm:.2f}')
            
            self.bar_executed = len(self)

            # Case 1: The completed order was our entry/exit order (self.entry_order)
            if self.entry_order and order.ref == self.entry_order.ref:
                self.entry_order = None # Reset main order tracker

                # If a position exists after this order, it was an entry or modification. Place/adjust stop loss.
                if self.position:
                    # Cancel any existing stop loss order before placing a new one
                    if self.stop_loss_order and self.stop_loss_order.alive():
                        self.cancel(self.stop_loss_order)
                        self.log(f'{dt_str} Canceled existing stop loss order: {self.stop_loss_order.ref}')
                        self.stop_loss_order = None
                        
                    if self.position.size > 0:  # We are Long
                        stop_price = fill_price * (1.0 - self.p.stop_loss_pct / 100.0)
                        self.stop_loss_order = self.sell(exectype=bt.Order.Stop, price=stop_price, size=self.position.size)
                        self.log(f'{dt_str} PLACED SELL STOP @ {stop_price:.2f} (Order ref: {self.stop_loss_order.ref}) for position size {self.position.size}')
                    elif self.position.size < 0:  # We are Short
                        stop_price = fill_price * (1.0 + self.p.stop_loss_pct / 100.0)
                        self.stop_loss_order = self.buy(exectype=bt.Order.Stop, price=stop_price, size=abs(self.position.size))
                        self.log(f'{dt_str} PLACED BUY STOP @ {stop_price:.2f} (Order ref: {self.stop_loss_order.ref}) for position size {abs(self.position.size)}')
                else: # Position is flat, meaning the entry_order was an exit order. Cancel any active SL.
                    if self.stop_loss_order and self.stop_loss_order.alive():
                        self.cancel(self.stop_loss_order)
                        self.log(f'{dt_str} Position closed by strategy. CANCELLING PENDING STOP ORDER {self.stop_loss_order.ref}')
                        self.stop_loss_order = None
            
            # Case 2: The completed order was our stop loss order
            elif self.stop_loss_order and order.ref == self.stop_loss_order.ref:
                if order.isbuy(): # Stop loss for a short position was hit
                    self.log(f'{dt_str} BUY STOP EXECUTED (Closed Short), Price: {fill_price:.2f}, Size: {fill_size:.2f}')
                else: # Stop loss for a long position was hit
                    self.log(f'{dt_str} SELL STOP EXECUTED (Closed Long), Price: {fill_price:.2f}, Size: {fill_size:.2f}')
                self.stop_loss_order = None # Reset stop loss order tracker
            
            # Safety check: If position is flat after any execution, ensure no orphaned SL order
            if not self.position and self.stop_loss_order and self.stop_loss_order.alive():
                self.cancel(self.stop_loss_order)
                self.log(f'{dt_str} Position is flat post-execution. CANCELLING ORPHANED STOP ORDER {self.stop_loss_order.ref}')
                self.stop_loss_order = None


        elif order.status in [order.Canceled, order.Margin, order.Rejected, order.Expired]:
            status_name = order.getstatusname()
            self.log(f'{dt_str} Order Failed/Cancelled/Margin/Expired: {status_name} - Ref: {order.ref}')

            if self.entry_order and order.ref == self.entry_order.ref:
                order_type = "Buy" if self.entry_order.isbuy() else "Sell"
                if self.entry_order.isclose(): order_type = "Close"
                self.log(f'{dt_str} Main strategy order ({order_type}) {status_name}.')
                self.entry_order = None  # Allow new strategy orders
            elif self.stop_loss_order and order.ref == self.stop_loss_order.ref:
                self.log(f'{dt_str} Stop loss order {status_name}. Position might be unprotected.')
                self.stop_loss_order = None
                if status_name == 'Margin' and self.position:
                    self.log(f'{dt_str} CRITICAL: Margin call on stop loss order while in position. Size: {self.position.size}. Consider manual exit or emergency close.')
                    # Optional: Force close position if SL margin call happens
                    # if not self.entry_order: self.entry_order = self.close()

    def next(self):
        # Check if an entry_order (buy/sell/close initiated by strategy) is pending
        if self.entry_order:
            return # Wait for the order to be processed

        adx = self.adx.adx[0]
        adxr = self.adxr.adxr[0] # ADXR not used in original logic for exit, only entry
        pctb = self.bb_pct.pctb[0]

        # Check if we are in the market
        if not self.position:
            # Not in the market, look for entry
            # LONG ENTRY: strong trend + oversold
            if adx > 25 and adxr > 20 and pctb < 0:
                self.log(f'BUY SIGNAL – ADX={adx:.1f}, ADXR={adxr:.1f}, %B={pctb:.2f}')
                self.entry_order = self.buy() # Sizer will determine size

            # SHORT ENTRY: strong trend + overbought
            elif adx > 25 and adxr > 20 and pctb > 1:
                self.log(f'SELL SIGNAL – ADX={adx:.1f}, ADXR={adxr:.1f}, %B={pctb:.2f}')
                self.entry_order = self.sell() # Sizer will determine size
        
        else: # In the market, look for strategy-based exit (not stop-loss)
            # LONG EXIT: trend fading or price up at upper band
            if self.position.size > 0: # If we are long
                if adx < 20 or pctb > 1:
                    self.log(f'EXIT LONG SIGNAL – ADX={adx:.1f}, %B={pctb:.2f}')
                    self.entry_order = self.close() # This will close the long position

            # SHORT EXIT: trend fading or price down at lower band
            elif self.position.size < 0: # If we are short
                if adx < 20 or pctb < 0:
                    self.log(f'EXIT SHORT SIGNAL – ADX={adx:.1f}, %B={pctb:.2f}')
                    self.entry_order = self.close() # This will close the short position

    def stop(self):
        self.log(f'(Strategy End) Final Portfolio Value: {self.broker.getvalue():.2f}')
