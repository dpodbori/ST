import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        'bb_period': st.number_input("Bollinger Bands Period", value=20, min_value=1, step=1),
        'bb_devfactor': st.number_input("Bollinger Bands Deviation Factor", value=2.0, min_value=0.0, step=0.1),
        'rsi_period': st.number_input("RSI Period", value=14, min_value=1, step=1),
        'rsi_oversold': st.number_input("RSI Oversold Level", value=30, min_value=0, max_value=100, step=1),
        'rsi_overbought': st.number_input("RSI Overbought Level", value=70, min_value=0, max_value=100, step=1),
        'sl_atr_period': st.number_input("ATR Stop Loss Period", value=14, min_value=1, step=1),
        'sl_atr_mult': st.number_input("ATR Stop Loss Multiplier", value=2.0, min_value=0.0, step=0.1),
    }

class BollingerRSIReversion(bt.Strategy):
    """
    Mean Reversion Strategy using Bollinger Bands and RSI.
    Enters long when price touches/crosses below lower BB and RSI is oversold.
    Enters short when price touches/crosses above upper BB and RSI is overbought.
    Exits when price crosses back over the middle BB.
    Uses an ATR-based stop loss.
    """
    params = (
        ('bb_period', 20),
        ('bb_devfactor', 2.0),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('sl_atr_period', 14),
        ('sl_atr_mult', 2.0),
    )

    def __init__(self):
        self.bbands = bt.indicators.BollingerBands(
            period=self.p.bb_period, devfactor=self.p.bb_devfactor
        )
        self.rsi = bt.indicators.RelativeStrengthIndex(
            period=self.p.rsi_period
        )
        self.atr = bt.indicators.AverageTrueRange(
            period=self.p.sl_atr_period
        )
        self.bb_upper = self.bbands.lines.top
        self.bb_middle = self.bbands.lines.mid
        self.bb_lower = self.bbands.lines.bot
        self.entry_order = None
        self.sl_order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{self.__class__.__name__} - {dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            if order == self.entry_order:
                entry_price = order.executed.price
                entry_size = order.executed.size
                atr_value = self.atr[0]
                if order.isbuy():
                    self.log(f'Long entry executed at {entry_price:.2f}, Size: {entry_size}')
                    stop_price = self.data.low[0] - max(atr_value, 0.00001) * self.p.sl_atr_mult
                    self.sl_order = self.sell(exectype=bt.Order.Stop, price=stop_price, size=entry_size)
                    self.log(f'Placed stop loss for long at {stop_price:.2f}')
                elif order.issell():
                    self.log(f'Short entry executed at {entry_price:.2f}, Size: {entry_size}')
                    stop_price = self.data.high[0] + max(atr_value, 0.00001) * self.p.sl_atr_mult
                    self.sl_order = self.buy(exectype=bt.Order.Stop, price=stop_price, size=abs(entry_size))
                    self.log(f'Placed stop loss for short at {stop_price:.2f}')
                self.entry_order = None
            elif order == self.sl_order:
                self.log(f'Stop loss executed at {order.executed.price:.2f}')
                self.sl_order = None
        elif order.status in [order.Canceled, order.Rejected, order.Margin]:
            self.log(f'Order {order.getstatusname()} - Ref: {order.ref}')
            if order == self.entry_order: self.entry_order = None
            elif order == self.sl_order: self.sl_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        direction = 'UNKNOWN'
        if trade.history and len(trade.history) > 0:
            try:
                first_event = trade.history[0].event
                if hasattr(first_event, 'size'):
                    direction = 'LONG' if first_event.size > 0 else 'SHORT'
            except Exception:
                pass
        self.log(f'TRADE CLOSED - Direction: {direction}, Net PnL: {trade.pnlcomm:.2f}')

    def next(self):
        if self.entry_order or self.sl_order:
            return
        close = self.data.close[0]
        rsi_val = self.rsi[0]
        if not self.position:
            if close < self.bb_lower[0] and rsi_val < self.p.rsi_oversold:
                self.log(f'Long signal at {close:.2f}, RSI: {rsi_val:.2f}')
                self.entry_order = self.buy()
            elif close > self.bb_upper[0] and rsi_val > self.p.rsi_overbought:
                self.log(f'Short signal at {close:.2f}, RSI: {rsi_val:.2f}')
                self.entry_order = self.sell()
        else:
            if self.position.size > 0 and close > self.bb_middle[0]:
                self.log(f'Long exit signal (Mean Reversion) at {close:.2f}')
                self.close()
            elif self.position.size < 0 and close < self.bb_middle[0]:
                self.log(f'Short exit signal (Mean Reversion) at {close:.2f}')
                self.close()

    def stop(self):
        self.log(f'Ending Value: {self.broker.getvalue():.2f}')
