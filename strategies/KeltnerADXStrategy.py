import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'kc_ema_period': st.number_input("Keltner Channels EMA Period", value=20, min_value=1, step=1),
        'kc_atr_period': st.number_input("Keltner Channels ATR Period", value=10, min_value=1, step=1),
        'kc_atr_mult': st.number_input("Keltner Channels ATR Multiplier", value=2.0, min_value=0.1, step=0.1),
        'dmi_period': st.number_input("DMI Period", value=14, min_value=1, step=1),
        'adx_threshold': st.number_input("ADX Threshold", value=25, min_value=0, step=1),
        'sl_atr_period': st.number_input("Stop Loss ATR Period", value=14, min_value=1, step=1),
        'sl_atr_mult': st.number_input("Stop Loss ATR Multiplier", value=3.0, min_value=0.1, step=0.1),
    }

class KeltnerChannels(bt.Indicator):
    """
    Keltner Channels based on EMA and ATR.
    """
    lines = ('upper', 'middle', 'lower')
    params = (('ema_period', 20), ('atr_period', 10), ('atr_mult', 2.0),)

    def __init__(self):
        self.l.middle = bt.indicators.ExponentialMovingAverage(
            self.data.close, period=self.p.ema_period)
        atr = bt.indicators.AverageTrueRange(self.data, period=self.p.atr_period)
        self.l.upper = self.l.middle + self.p.atr_mult * atr
        self.l.lower = self.l.middle - self.p.atr_mult * atr

class KeltnerADXStrategy(bt.Strategy):
    """
    Improved Keltner + ADX Strategy with Dynamic Trailing Stops.
    """
    params = (
        ('kc_ema_period', 20),
        ('kc_atr_period', 10),
        ('kc_atr_mult', 2.0),
        ('dmi_period', 14),
        ('adx_threshold', 25),
        ('sl_atr_period', 14),
        ('sl_atr_mult', 3.0),
    )

    def __init__(self):
        self.keltner = KeltnerChannels(
            self.data,
            ema_period=self.p.kc_ema_period,
            atr_period=self.p.kc_atr_period,
            atr_mult=self.p.kc_atr_mult
        )
        self.dmi = bt.indicators.DirectionalMovementIndex(
            self.data, period=self.p.dmi_period
        )
        self.atr = bt.indicators.AverageTrueRange(
            self.data, period=self.p.sl_atr_period
        )
        self.entry_order = None
        self.sl_order = None
        self.current_stop_price = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order == self.entry_order:
                if order.isbuy():
                    self.log(f'Long entry executed at {order.executed.price:.2f}')
                    initial_stop = self.data.close[0] - self.p.sl_atr_mult * self.atr[0]
                    self.current_stop_price = initial_stop
                    self.sl_order = self.sell(
                        exectype=bt.Order.Stop,
                        price=self.current_stop_price,
                        size=order.executed.size
                    )
                    self.log(f'Initial stop loss for long at {self.current_stop_price:.2f}')
                elif order.issell():
                    self.log(f'Short entry executed at {order.executed.price:.2f}')
                    initial_stop = self.data.close[0] + self.p.sl_atr_mult * self.atr[0]
                    self.current_stop_price = initial_stop
                    self.sl_order = self.buy(
                        exectype=bt.Order.Stop,
                        price=self.current_stop_price,
                        size=abs(order.executed.size)
                    )
                    self.log(f'Initial stop loss for short at {self.current_stop_price:.2f}')
                self.entry_order = None
            else:
                if order.exectype == bt.Order.Stop:
                    self.log('Stop order executed – trade closed')
                    self.sl_order = None
                    self.current_stop_price = None
        elif order.status in [order.Canceled, order.Rejected, order.Margin]:
            self.log(f'Order {order.getstatusname()}')
            if order == self.entry_order:
                self.entry_order = None
            elif order == self.sl_order:
                self.sl_order = None

    def next(self):
        if self.entry_order or (self.sl_order and self.sl_order.alive()):
            return
        if not self.position:
            if (self.data.close[0] > self.keltner.l.upper[0] and
                self.dmi.adx[0] > self.p.adx_threshold and
                self.dmi.plusDI[0] > self.dmi.minusDI[0]):
                self.log(f'Long entry signal at {self.data.close[0]:.2f}')
                self.entry_order = self.buy()
            elif (self.data.close[0] < self.keltner.l.lower[0] and
                  self.dmi.adx[0] > self.p.adx_threshold and
                  self.dmi.minusDI[0] > self.dmi.plusDI[0]):
                self.log(f'Short entry signal at {self.data.close[0]:.2f}')
                self.entry_order = self.sell()
        else:
            if self.position.size > 0:
                candidate_stop = self.data.close[0] - self.p.sl_atr_mult * self.atr[0]
                if self.current_stop_price is None or candidate_stop > self.current_stop_price:
                    self.current_stop_price = candidate_stop
                    self.log(f'Updating long trailing stop to {self.current_stop_price:.2f}')
                    if self.sl_order and self.sl_order.alive():
                        self.cancel(self.sl_order)
                    self.sl_order = self.sell(
                        exectype=bt.Order.Stop,
                        price=self.current_stop_price,
                        size=self.position.size
                    )
                if self.data.close[0] < self.keltner.l.lower[0]:
                    self.log(f'Long exit signal (channel cross) at {self.data.close[0]:.2f}')
                    self.close()
            elif self.position.size < 0:
                candidate_stop = self.data.close[0] + self.p.sl_atr_mult * self.atr[0]
                if self.current_stop_price is None or candidate_stop < self.current_stop_price:
                    self.current_stop_price = candidate_stop
                    self.log(f'Updating short trailing stop to {self.current_stop_price:.2f}')
                    if self.sl_order and self.sl_order.alive():
                        self.cancel(self.sl_order)
                    self.sl_order = self.buy(
                        exectype=bt.Order.Stop,
                        price=self.current_stop_price,
                        size=abs(self.position.size)
                    )
                if self.data.close[0] > self.keltner.l.upper[0]:
                    self.log(f'Short exit signal (channel cross) at {self.data.close[0]:.2f}')
                    self.close()

    def stop(self):
        self.log(f'Final Portfolio Value: {self.broker.getvalue():.2f}')
