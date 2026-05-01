import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'kama_period': st.number_input("KAMA Period", value=20, min_value=1, step=1),
        'fast_ema': st.number_input("Fast EMA (KAMA Internal)", value=2, min_value=1, step=1),  # Only relevant if using custom KAMA
        'slow_ema': st.number_input("Slow EMA (KAMA Internal)", value=30, min_value=1, step=1),  # Only relevant if using custom KAMA
        'vol_period': st.number_input("Volatility Period", value=20, min_value=1, step=1),
        'vol_mult': st.number_input("Volatility Multiplier", value=2.0, min_value=0.0, step=0.1),
        'trade_mode': st.selectbox("Trade Mode", ['pullback', 'breakout']),
        'trail_perc': st.number_input("Trailing Stop Percentage", value=0.05, min_value=0.0, max_value=1.0)  # e.g., 0.05 = 5%
    }

class AdaptiveMAVolatilityStrategy(bt.Strategy):
    """
    Strategy using KAMA with volatility bands and a trailing stop-loss.
    Trades pullbacks or breakouts, exits on KAMA cross OR trailing stop.
    """
    params = (
        ('kama_period', 20),
        ('fast_ema', 2),      # Only relevant if using custom KAMA
        ('slow_ema', 30),     # Only relevant if using custom KAMA
        ('vol_period', 20),
        ('vol_mult', 2.0),
        ('trade_mode', 'pullback'), # 'pullback' or 'breakout'
        ('trail_perc', 0.05), # Trailing stop percentage (e.g., 0.05 = 5%)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.kama = bt.indicators.KAMA(period=self.p.kama_period) # Uses internal fast/slow
        self.kama_stddev = bt.indicators.StandardDeviation(self.kama, period=self.p.vol_period)
        self.upper_band = self.kama + self.p.vol_mult * self.kama_stddev
        self.lower_band = self.kama - self.p.vol_mult * self.kama_stddev
        self.kama_cross = bt.indicators.CrossOver(self.dataclose, self.kama)

        # Order tracking
        self.order = None         # For entry or KAMA-based exit orders
        self.order_trail = None   # For the trailing stop order
        self.buyprice = None
        self.buycomm = None

        if self.p.trade_mode not in ['pullback', 'breakout']:
            raise ValueError("trade_mode parameter must be 'pullback' or 'breakout'")
        if self.p.trail_perc is not None and self.p.trail_perc <= 0:
            raise ValueError("trail_perc must be positive or None")

        self.log(f"Strategy Initialized: KAMA(Period={self.p.kama_period}), "
                 f"VolBands(StdDev({self.p.vol_period}), Mult={self.p.vol_mult}), "
                 f"TradeMode={self.p.trade_mode}, TrailPerc={self.p.trail_perc}")
        self.log(f"Note: Standard bt.indicators.KAMA uses internal fast/slow periods (typically 2 and 30).")


    def notify_order(self, order):
        # --- Order Status ---
        if order.status == order.Submitted:
            self.log(f'ORDER SUBMITTED: Ref:{order.ref}, Type:{order.ordtypename()}, Size:{order.size}, Price:{order.price}')
            return
        if order.status == order.Accepted:
             self.log(f'ORDER ACCEPTED: Ref:{order.ref}, Type:{order.ordtypename()}')
             return

        # --- Order Completion/Rejection ---
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            otype = order.ordtypename()
            # Get execution details safely, providing defaults for non-completed orders
            price = order.executed.price if order.status == order.Completed else None
            # Use executed size if available, otherwise submitted size (submitted size might be more informative for rejected orders)
            size = order.executed.size if order.status == order.Completed and order.executed.size is not None else order.size
            comm = order.executed.comm if order.status == order.Completed else 0.0
            pnl = order.executed.pnl if order.status == order.Completed and order.executed.pnl else 0.0 # Defaults to 0.0

            # Prepare formatted strings to handle None values gracefully for logging
            exec_price_str = f"{price:.2f}" if price is not None else "N/A"
            # Handle order.price which might be 0 or None for Market orders/some brokers
            req_price_val = order.price if order.price is not None and order.price != 0.0 else None
            req_price_str = f"{req_price_val:.2f}" if req_price_val is not None else "Market/None"
            comm_str = f"{comm:.2f}" # Safe as it defaults to 0.0
            pnl_str = f"{pnl:.2f}"   # Safe as it defaults to 0.0

            # --- CORRECTED LOG LINE ---
            # Uses the pre-formatted safe strings (exec_price_str, req_price_str, etc.)
            self.log(f'ORDER COMPLETE/CANCEL/REJECT: Ref:{order.ref}, Type:{otype}, Status:{order.getstatusname()}, '
                     f'Size:{size}, ExecPrice:{exec_price_str} (Req:{req_price_str}), Comm:{comm_str}, Pnl:{pnl_str}')

            # --- Order Tracking Logic --- (Rest of the function is the same)
            is_entry = order.ref == getattr(self.order, 'ref', None)
            is_trail = order.ref == getattr(self.order_trail, 'ref', None)

            if is_entry:
                if order.status == order.Completed:
                    # --- ENTRY COMPLETED ---
                    if order.isbuy():
                        self.log(f'BUY EXECUTED @ {price:.2f}, Size: {size}') # Use 'price' here as it's confirmed not None
                        self.buyprice = price
                        self.buycomm = comm
                        if self.p.trail_perc:
                            stop_price = price * (1.0 - self.p.trail_perc)
                            self.log(f'PLACING TRAILING SELL ORDER: Trail %: {self.p.trail_perc * 100:.2f}, Initial Stop: {stop_price:.2f}')
                            self.order_trail = self.sell(exectype=bt.Order.StopTrail, trailpercent=self.p.trail_perc)
                            self.order_trail.addinfo(name="TrailStopSell")
                    elif order.issell():
                        self.log(f'SELL EXECUTED @ {price:.2f}, Size: {size}') # Use 'price' here as it's confirmed not None
                        self.buyprice = price
                        self.buycomm = comm
                        if self.p.trail_perc:
                             stop_price = price * (1.0 + self.p.trail_perc)
                             self.log(f'PLACING TRAILING BUY ORDER: Trail %: {self.p.trail_perc * 100:.2f}, Initial Stop: {stop_price:.2f}')
                             self.order_trail = self.buy(exectype=bt.Order.StopTrail, trailpercent=self.p.trail_perc)
                             self.order_trail.addinfo(name="TrailStopBuy")

                # --- KAMA-EXIT COMPLETED ---
                if not self.position and self.order_trail is not None:
                     # Check status just to be sure the order causing flatness was completed, not rejected.
                     if order.status == order.Completed:
                          self.log(f'KAMA EXIT EXECUTED. CANCELLING PENDING TRAIL ORDER Ref: {self.order_trail.ref}')
                          self.cancel(self.order_trail)
                          self.order_trail = None

                # Reset main order tracker only if the main order event finished (completed, canceled, rejected)
                if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
                    self.order = None

            elif is_trail:
                 # --- TRAILING STOP EVENT (EXECUTED, CANCELED, REJECTED) ---
                 if order.status == order.Completed:
                      # Use 'price' here as it's confirmed not None
                      self.log(f'TRAILING STOP EXECUTED @ {price:.2f}, Size: {size}, Pnl: {pnl:.2f}')
                 else:
                      self.log(f'TRAILING STOP CANCELED/REJECTED Status: {order.getstatusname()}')

                 # Reset trail order tracker regardless of completion status
                 self.order_trail = None

            else:
                 # Order completion notification for an unknown order ref? Should not happen often.
                 # Could be an manually cancelled order if broker had such API interaction?
                 self.log(f"WARN: notify_order received for unrecognized order Ref: {order.ref}, Status: {order.getstatusname()}")

        # --- End notify_order -----


    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')

    def next(self):
        # Check if any order is pending
        if self.order or self.order_trail:
            # self.log(f"Skipping next(): Pending order exists. self.order: {self.order}, self.order_trail: {self.order_trail}")
            return

        # --- Entry Logic ---
        if not self.position:
            entry_signal = False
            # ** Pullback Mode **
            if self.p.trade_mode == 'pullback':
                if self.kama_cross[0] > 0: # Buy Signal
                    self.log(f'PULLBACK BUY SIGNAL: Close {self.dataclose[0]:.2f} > KAMA {self.kama[0]:.2f}')
                    self.order = self.buy()
                    entry_signal = True
                elif self.kama_cross[0] < 0: # Sell Signal (optional shorting)
                    self.log(f'PULLBACK SELL SIGNAL: Close {self.dataclose[0]:.2f} < KAMA {self.kama[0]:.2f}')
                    self.order = self.sell()
                    entry_signal = True

            # ** Breakout Mode **
            elif self.p.trade_mode == 'breakout':
                if self.dataclose[0] > self.upper_band[0] and self.dataclose[-1] <= self.upper_band[-1]: # Buy Signal
                     self.log(f'BREAKOUT BUY SIGNAL: Close {self.dataclose[0]:.2f} > Upper Band {self.upper_band[0]:.2f}')
                     self.order = self.buy()
                     entry_signal = True
                elif self.dataclose[0] < self.lower_band[0] and self.dataclose[-1] >= self.lower_band[-1]: # Sell Signal (optional shorting)
                     self.log(f'BREAKOUT SELL SIGNAL: Close {self.dataclose[0]:.2f} < Lower Band {self.lower_band[0]:.2f}')
                     self.order = self.sell()
                     entry_signal = True

            # If an entry order was placed, stop processing for this bar
            if entry_signal:
                return

        # --- KAMA-Based Exit Logic ---
        # Only consider KAMA exit if we are in a position AND no trailing stop order is currently active
        # Note: We place the KAMA exit even if a trail order exists, letting the broker handle which executes first.
        # The cancellation logic is handled in notify_order.
        else: # Already in the market
            # Exit Long: Price crosses below KAMA
            if self.position.size > 0 and self.kama_cross[0] < 0:
                 self.log(f'KAMA CLOSE LONG SIGNAL: Close {self.dataclose[0]:.2f} < KAMA {self.kama[0]:.2f}')
                 self.order = self.close() # Close position via KAMA cross

            # Exit Short: Price crosses above KAMA
            elif self.position.size < 0 and self.kama_cross[0] > 0:
                 self.log(f'KAMA CLOSE SHORT SIGNAL: Close {self.dataclose[0]:.2f} > KAMA {self.kama[0]:.2f}')
                 self.order = self.close() # Close position via KAMA cross

    def stop(self):
        trail_info = f"TrailPerc={self.p.trail_perc}" if self.p.trail_perc else "NoTrail"
        self.log(f'(KAMA Period {self.p.kama_period}, {trail_info}) Ending Value {self.broker.getvalue():.2f}')
