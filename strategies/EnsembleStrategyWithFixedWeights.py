import math
import backtrader as bt
import backtrader.indicators as btind
import streamlit as st


def show_parameters():
    return {
        'sma_fast_p': st.number_input("SMA Fast Period", value=10, min_value=1, step=1),
        'sma_slow_p': st.number_input("SMA Slow Period", value=30, min_value=1, step=1),
        'rsi_p': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_level': st.number_input("RSI Level", value=50, min_value=0, max_value=100, step=1),
        'macd_fast': st.number_input("MACD Fast Period", value=12, min_value=1, step=1),
        'macd_slow': st.number_input("MACD Slow Period", value=26, min_value=1, step=1),
        'macd_signal': st.number_input("MACD Signal Period", value=9, min_value=1, step=1),
        'w_sma': st.number_input("Weight for SMA Model", value=0.4, min_value=0.0, max_value=1.0, step=0.01),
        'w_rsi': st.number_input("Weight for RSI Model", value=0.3, min_value=0.0, max_value=1.0, step=0.01),
        'w_macd': st.number_input("Weight for MACD Model", value=0.3, min_value=0.0, max_value=1.0, step=0.01),
        'consensus_threshold': st.number_input("Consensus Threshold", value=0.1, min_value=0.01, step=0.01),
        'stop_loss_perc': st.number_input("Stop Loss Percentage", value=4.0, min_value=0.01, max_value=100.0) / 100,
    }


class EnsembleStrategyWithFixedWeights(bt.Strategy):
    """
    Implements an ensemble trading strategy combining signals from multiple
    sub-models using pre-defined, fixed weights (passed as parameters).

    The dynamic calculation of weights based on recent performance is assumed
    to be done externally and periodically updated in the parameters.
    """
    params = (
        # --- Sub-Model Parameters ---
        ('sma_fast_p', 10),
        ('sma_slow_p', 30),
        ('rsi_p', 14),
        ('rsi_level', 50), # RSI level for trend signal
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),

        # --- Ensemble Parameters ---
        # Weights for each sub-model (MUST sum ideally to 1.0 or be normalized later)
        ('w_sma', 0.4),
        ('w_rsi', 0.3),
        ('w_macd', 0.3),
        ('consensus_threshold', 0.1), # Minimum weighted vote sum to trigger action

        # --- Risk Management ---
        ('stop_loss_perc', 0.04),  # Stop loss percentage (e.g., 0.04 = 4%)

        # --- Control ---
        ('printlog', True),
    )

    def log(self, txt, dt=None, doprint=False):
        ''' Logging function'''
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} - {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close

        # --- Initialize Indicators for Sub-Models ---
        # 1. SMA Crossover
        self.sma_fast = btind.SimpleMovingAverage(self.dataclose, period=self.p.sma_fast_p)
        self.sma_slow = btind.SimpleMovingAverage(self.dataclose, period=self.p.sma_slow_p)

        # 2. RSI Trend
        self.rsi = btind.RSI(self.dataclose, period=self.p.rsi_p)

        # 3. MACD Trend
        self.macd = btind.MACD(self.dataclose,
                               period_me1=self.p.macd_fast,
                               period_me2=self.p.macd_slow,
                               period_signal=self.p.macd_signal)
        # We only need macd line and signal line for crossover logic
        self.macd_line = self.macd.macd
        self.macd_signal_line = self.macd.signal

        # --- Store Weights ---
        # Ensure weights are non-negative
        self.weights = {
            'sma': max(0, self.p.w_sma),
            'rsi': max(0, self.p.w_rsi),
            'macd': max(0, self.p.w_macd)
        }
        # Optional: Normalize weights if they don't sum to 1 (or handle scaling later)
        total_weight = sum(self.weights.values())
        if total_weight > 0 and not math.isclose(total_weight, 1.0):
             self.log(f"Warning: Weights do not sum to 1. Normalizing. Original: {self.weights}")
             self.weights = {k: v / total_weight for k, v in self.weights.items()}
             self.log(f"Normalized Weights: {self.weights}")


        # --- Order Tracking ---
        self.order = None
        self.stop_order = None

    # --- Sub-Model Signal Functions ---
    def _get_sma_signal(self):
        if self.sma_fast[0] > self.sma_slow[0]: return 1
        elif self.sma_fast[0] < self.sma_slow[0]: return -1
        else: return 0

    def _get_rsi_signal(self):
        if self.rsi[0] > self.p.rsi_level: return 1
        elif self.rsi[0] < self.p.rsi_level: return -1
        else: return 0

    def _get_macd_signal(self):
        # Check if lines are calculated (NaN check)
        if not math.isnan(self.macd_line[0]) and not math.isnan(self.macd_signal_line[0]):
            if self.macd_line[0] > self.macd_signal_line[0]: return 1
            elif self.macd_line[0] < self.macd_signal_line[0]: return -1
            else: return 0
        else:
             return 0 # Not ready

    def notify_order(self, order):
        otype = order.ordtypename()
        ostatus = order.getstatusname()

        if order.status in [order.Submitted, order.Accepted]:
            price_str = f"{order.price:.2f}" if order.price is not None and order.price != 0.0 else "Market/None"
            self.log(f'ORDER {otype} {ostatus}: Ref:{order.ref}, Size:{order.size}, Price:{price_str}')
            return

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            price = order.executed.price if order.status == order.Completed else None
            size = order.executed.size if order.status == order.Completed else order.size
            comm = order.executed.comm if order.status == order.Completed else 0.0
            pnl = order.executed.pnl if order.status == order.Completed else 0.0

            exec_price_str = f"{price:.2f}" if price is not None else "N/A"
            comm_str = f"{comm:.2f}"
            pnl_str = f"{pnl:.2f}"

            self.log(f'ORDER COMPLETE/CANCEL/REJECT: Ref:{order.ref}, Type:{otype}, Status:{ostatus}, '
                     f'Size:{size}, ExecPrice:{exec_price_str}, Comm:{comm_str}, Pnl:{pnl_str}')

            is_entry_exit_order = self.order and order.ref == self.order.ref
            is_stop_order = self.stop_order and order.ref == self.stop_order.ref

            if is_entry_exit_order:
                if order.status == order.Completed:
                    if self.position and size != 0: # Entry completed
                        stop_price = 0.0
                        if order.isbuy():
                            stop_price = price * (1.0 - self.p.stop_loss_perc)
                            self.log(f'BUY EXECUTED @ {price:.2f}. Placing STOP SELL @ {stop_price:.2f}')
                            self.stop_order = self.sell(exectype=bt.Order.Stop, price=stop_price, size=order.executed.size) # Match size
                            self.stop_order.addinfo(name="StopLossSell")
                        elif order.issell():
                            stop_price = price * (1.0 + self.p.stop_loss_perc)
                            self.log(f'SELL EXECUTED @ {price:.2f}. Placing STOP BUY @ {stop_price:.2f}')
                            self.stop_order = self.buy(exectype=bt.Order.Stop, price=stop_price, size=order.executed.size) # Match size
                            self.stop_order.addinfo(name="StopLossBuy")
                    elif not self.position and self.stop_order: # Close completed
                        self.log(f'CLOSE EXECUTED (Ref: {order.ref}). Cancelling pending STOP ORDER Ref: {self.stop_order.ref}')
                        self.cancel(self.stop_order)
                        self.stop_order = None
                elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                     if self.stop_order:
                         self.log(f"Entry/Close order {ostatus} (Ref: {order.ref}). Cancelling related Stop Order Ref: {self.stop_order.ref}")
                         self.cancel(self.stop_order)
                         self.stop_order = None
                self.order = None

            elif is_stop_order:
                if order.status == order.Completed:
                    self.log(f'STOP LOSS EXECUTED @ {price:.2f} (Ref: {order.ref})')
                else:
                    self.log(f'Stop loss order {ostatus}. Ref: {order.ref}')
                self.stop_order = None

        elif order.status == order.Expired:
            self.log(f'ORDER EXPIRED: Ref: {order.ref}, Type: {otype}')
            if self.order and order.ref == self.order.ref: self.order = None
            elif self.stop_order and order.ref == self.stop_order.ref: self.stop_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}')

    def next(self):
        # Check if an order is pending
        if self.order:
            return

        # --- Calculate Weighted Consensus Signal ---
        sma_signal = self._get_sma_signal()
        rsi_signal = self._get_rsi_signal()
        macd_signal = self._get_macd_signal()

        weighted_vote_sum = (
            sma_signal * self.weights['sma'] +
            rsi_signal * self.weights['rsi'] +
            macd_signal * self.weights['macd']
        )
        # self.log(f"Signals: SMA={sma_signal}, RSI={rsi_signal}, MACD={macd_signal} | Weighted Sum: {weighted_vote_sum:.2f}") # Debug log

        final_signal = 0
        if weighted_vote_sum > self.p.consensus_threshold:
            final_signal = 1
        elif weighted_vote_sum < -self.p.consensus_threshold:
            final_signal = -1

        # --- Trading Logic ---
        if not self.position: # If not in the market
            if final_signal == 1:
                self.log(f'CONSENSUS LONG SIGNAL (Vote: {weighted_vote_sum:.2f}). Placing BUY Order.')
                if self.stop_order: self.cancel(self.stop_order) # Safety cancel
                self.order = self.buy()
            elif final_signal == -1:
                self.log(f'CONSENSUS SHORT SIGNAL (Vote: {weighted_vote_sum:.2f}). Placing SELL Order.')
                if self.stop_order: self.cancel(self.stop_order) # Safety cancel
                self.order = self.sell()

        else: # If in the market
            current_signal = 1 if self.position.size > 0 else -1
            
            # Exit if consensus signal flips or turns neutral
            if final_signal != current_signal:
                self.log(f'CONSENSUS EXIT SIGNAL (Vote: {weighted_vote_sum:.2f}, Final Signal: {final_signal}). Closing Position.')
                if self.stop_order: # Cancel pending stop loss before closing
                     self.log(f'Cancelling Stop Order Ref: {self.stop_order.ref} before closing.')
                     self.cancel(self.stop_order)
                     self.stop_order = None
                self.order = self.close() # Place market close order

    def stop(self):
         # Log final parameters used, including weights
         weight_str = ', '.join([f"w_{k}={v:.2f}" for k, v in self.weights.items()])
         self.log(f'(Ensemble Params: {weight_str}, Threshold={self.p.consensus_threshold}, '
                  f'Stop Loss={self.p.stop_loss_perc*100:.1f}%) Ending Value {self.broker.getvalue():.2f}', doprint=True)

