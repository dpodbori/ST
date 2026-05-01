import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'adx_period': st.number_input("ADX Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25.0, min_value=0.0, step=0.1),
        'trail_percent': st.number_input("Trailing Stop Percentage", value=0.05, min_value=0.01, max_value=1.0, step=0.01),
    }

class HilbertTrendStrategy(bt.Strategy):
    params = dict(
        adx_period=14,
        adx_threshold=25,
        trail_percent=0.05,
    )

    def __init__(self):
        # 1) Hilbert Transform SineWave via Backtrader talib integration
        ht = bt.talib.HT_SINE(self.data.close)
        self.ht_sine     = ht.sine      # <-- grab the 'sine' output line
        self.ht_leadsine = ht.leadsine  # <-- grab the 'leadsine' output line
        self.sine_cross  = bt.indicators.CrossOver(
            self.ht_sine, self.ht_leadsine
        )

        # 2) Directional Movement Index (ADX, +DI, -DI)
        dmi = bt.indicators.DirectionalMovementIndex(
            period=self.p.adx_period
        )
        self.adx      = dmi.adx
        self.plus_di  = dmi.plusDI
        self.minus_di = dmi.minusDI

        # 3) Order tracking
        self.entry_order = None
        self.stop_order  = None

    def next(self):
        if self.entry_order or self.stop_order:
            return

        trending   = self.adx[0] > self.p.adx_threshold
        uptrend    = trending and (self.plus_di[0] > self.minus_di[0])
        downtrend  = trending and (self.minus_di[0] > self.plus_di[0])

        cross_up   = (self.sine_cross[0] ==  1)
        cross_down = (self.sine_cross[0] == -1)

        if not self.position:
            if uptrend and cross_up:
                self.entry_order = self.buy()
            elif downtrend and cross_down:
                self.entry_order = self.sell()

    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return

        if order.status == order.Completed:
            # entry filled → set up trailing stop on opposite side
            if order == self.entry_order:
                self.entry_order = None
                if order.isbuy():
                    self.stop_order = self.sell(
                        exectype=bt.Order.StopTrail,
                        trailpercent=self.p.trail_percent
                    )
                else:
                    self.stop_order = self.buy(
                        exectype=bt.Order.StopTrail,
                        trailpercent=self.p.trail_percent
                    )
            # stop filled → clear it
            elif order == self.stop_order:
                self.stop_order = None

        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            if order == self.entry_order:
                self.entry_order = None
            elif order == self.stop_order:
                self.stop_order = None

    def notify_trade(self, trade):
        pass  # no extra logging here
