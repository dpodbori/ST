import warnings

import backtrader as bt
import numpy as np
import streamlit as st


def show_parameters():
    return {
        'bull_state': st.number_input("Bull State Index", value=0, min_value=0, step=1),
        'bear_state': st.number_input("Bear State Index", value=1, min_value=0, step=1),
        'sma_short': st.number_input("Short SMA Period", value=30, min_value=1, step=1),
        'sma_long': st.number_input("Long SMA Period", value=90, min_value=1, step=1),
        'printlog': st.checkbox("Print Log", value=True),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=0.10, min_value=0.01, max_value=1.0, step=0.01),
    }

# Suppress warnings
warnings.filterwarnings("ignore")

# --- 1) DATAFEED ---
class HMMData(bt.feeds.PandasData):
    lines = ('hmm_state',)
    params = dict(
        datetime=None, open='Open', high='High', low='Low',
        close='Close', volume='Volume', openinterest=None,
        hmm_state='HMM_State',
    )
    plotinfo = dict(subplot=True)
    plotlines = dict(
        hmm_state=dict(_name='Regime', linestyle='--')
    )

# --- 2) STRATEGY ---
class HMMTrendRegimeStrategy(bt.Strategy):
    params = dict(
        bull_state=None,    # HMM bull state index
        bear_state=None,    # HMM bear state index
        sma_short=30,
        sma_long=90,
        printlog=True,
        trail_percent=0.10, # 10% trailing stop
    )

    def __init__(self):
        if self.p.bull_state is None or self.p.bear_state is None:
            raise ValueError("Must pass both bull_state and bear_state")
        self.price = self.data.close
        self.state = self.data.hmm_state
        self.sma_s = bt.indicators.SMA(self.data, period=self.p.sma_short)
        self.sma_l = bt.indicators.SMA(self.data, period=self.p.sma_long)
        self.order = None

    def log(self, txt, dt=None):
        if self.p.printlog:
            dt = dt or self.data.datetime.date(0)
            print(f"{dt.isoformat()} | {txt}")

    def next(self):
        # Require at least 2 bars for prev state
        if len(self) < 2:
            return

        # Warmup guard
        if (np.isnan(self.sma_s[0]) or np.isnan(self.sma_l[0]) or
            np.isnan(self.state[0]) or np.isnan(self.state[-1])):
            return

        state      = int(self.state[0])
        prev_state = int(self.state[-1])
        s, l       = self.sma_s[0], self.sma_l[0]
        pos        = self.position.size
        in_long    = pos > 0
        in_short   = pos < 0

        self.log(f"SMA_S={s:.2f} SMA_L={l:.2f} HMM={state}(prev={prev_state}) Pos={pos}")

        # Wait for pending order
        if self.order:
            return

        # --- EXIT LOGIC ---
        if in_long:
            if s <= l or state != self.p.bull_state:
                reason = "SMA down/equal" if s <= l else "Regime flip out of bull"
                self.log(f"CLOSE LONG ({reason}) @ {self.price[0]:.2f}")
                self.order = self.close()

        elif in_short:
            if s >= l or state != self.p.bear_state:
                reason = "SMA up/equal" if s >= l else "Regime flip out of bear"
                self.log(f"CLOSE SHORT ({reason}) @ {self.price[0]:.2f}")
                self.order = self.close()

        # --- ENTRY LOGIC ---
        else:  # flat
            # Compute both long & short signals up front
            go_long = (
                (s > l) and
                (state == self.p.bull_state) and
                (prev_state == self.p.bull_state)
            )
            go_short = (
                (s < l) and
                (state == self.p.bear_state) and
                (prev_state == self.p.bear_state)
            )

            if go_long:
                self.log(f"BUY CREATE (bull & sma up & persistent) @ {self.price[0]:.2f}")
                self.order = self.buy()

            elif go_short:
                self.log(f"SELL SHORT CREATE (bear & sma down & persistent) @ {self.price[0]:.2f}")
                self.order = self.sell()

    def notify_order(self, order):
        # Only act on final statuses
        if order.status in (order.Submitted, order.Accepted):
            return

        dt = self.data.datetime.date(0)
        if order.status == order.Completed:
            # Entry vs Close determined by order.isbuy()/issell() & current position
            if order.isbuy():
                if self.position.size > 0:
                    # Long entry
                    px, sz, cm = order.executed.price, order.executed.size, order.executed.comm
                    self.log(f"LONG EXECUTED Size={sz} Price={px:.2f} Comm={cm:.2f}")
                    # Attach a trailing stop on the long
                    if self.p.trail_percent > 0:
                        self.log(f" -> ATTACH SELL StopTrail {self.p.trail_percent*100:.1f}%")
                        self.sell(exectype=bt.Order.StopTrail,
                                  trailpercent=self.p.trail_percent)
                else:
                    # Closing short
                    px, sz, cm = order.executed.price, order.executed.size, order.executed.comm
                    self.log(f"BUY CLOSE SHORT Size={sz} Price={px:.2f} Comm={cm:.2f}")

            elif order.issell():
                if self.position.size < 0:
                    # Short entry
                    px, sz, cm = order.executed.price, order.executed.size, order.executed.comm
                    self.log(f"SHORT EXECUTED Size={sz} Price={px:.2f} Comm={cm:.2f}")
                    # Attach a trailing stop on the short
                    if self.p.trail_percent > 0:
                        self.log(f" -> ATTACH BUY StopTrail {self.p.trail_percent*100:.1f}%")
                        self.buy(exectype=bt.Order.StopTrail,
                                 trailpercent=self.p.trail_percent)
                else:
                    # Closing long
                    px, sz, cm = order.executed.price, order.executed.size, order.executed.comm
                    self.log(f"SELL CLOSE LONG Size={sz} Price={px:.2f} Comm={cm:.2f}")

        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            self.log(f"Order {order.getstatusname()} Ref={order.ref}")

        # Clear the pending order flag
        if self.order and self.order.ref == order.ref:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f"TRADE CLOSED P/L Net={trade.pnlcomm:.2f}")

    def stop(self):
        self.log(f"FINAL PORTFOLIO VALUE {self.broker.getvalue():.2f}")