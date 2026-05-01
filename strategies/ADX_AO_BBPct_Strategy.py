import backtrader as bt
import streamlit as st


def show_parameters():    
    return {
        'stop_loss_pct': st.number_input("Stop Loss Percentage", value=2.0, min_value=0.0, max_value=100.0) / 100,
    }

class ADX_AO_BBPct_Strategy(bt.Strategy):
    params = (
        ('stop_loss_pct', 2.0),
    )

    def log(self, txt: str, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} {txt}')

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.entry_order = None
        self.stop_loss_order = None
        self.bar_executed = 0
        self.adx_indicator = bt.indicators.ADX(self.datas[0], period=14, movav=bt.indicators.SMMA)
        self.ao_indicator = bt.indicators.AwesomeOscillator(self.datas[0], fast=5, slow=34, movav=bt.indicators.SMA)
        self.bb_pct_indicator = bt.indicators.BollingerBandsPct(self.datas[0], period=20, devfactor=2.0, movav=bt.indicators.SMA)

    def notify_order(self, order):
        dt_str = self.datas[0].datetime.datetime(0).isoformat()
        if order.status in [order.Submitted, order.Accepted]:
            self.log(f'{dt_str} ORDER ACCEPTED/SUBMITTED: Status {order.getstatusname()}, Type {"Buy" if order.isbuy() else "Sell"}, Ref: {order.ref}')
            return
        if order.status == order.Completed:
            fill_price = order.executed.price
            fill_size = order.executed.size 
            comm = order.executed.comm
            if order.isbuy():
                self.log(f'{dt_str} BUY EXECUTED, Price: {fill_price:.2f}, Size: {fill_size:.6f}, Cost: {order.executed.value:.2f}, Comm: {comm:.2f}, Ref: {order.ref}')
            else:
                self.log(f'{dt_str} SELL EXECUTED, Price: {fill_price:.2f}, Size: {fill_size:.6f}, Cost: {order.executed.value:.2f}, Comm: {comm:.2f}, Ref: {order.ref}')
            self.bar_executed = len(self)
            if self.entry_order and order.ref == self.entry_order.ref:
                self.entry_order = None 
                if self.position:
                    if self.stop_loss_order and self.stop_loss_order.alive():
                        self.cancel(self.stop_loss_order)
                        self.log(f'{dt_str} Canceled existing stop loss order: {self.stop_loss_order.ref}')
                        self.stop_loss_order = None
                    if self.position.size > 0:
                        stop_price = fill_price * (1.0 - self.p.stop_loss_pct / 100.0)
                        self.stop_loss_order = self.sell(exectype=bt.Order.Stop, price=stop_price, size=self.position.size)
                        self.log(f'{dt_str} PLACED SELL STOP @ {stop_price:.2f} (Ref: {self.stop_loss_order.ref}) for size {self.position.size}')
                    elif self.position.size < 0:
                        stop_price = fill_price * (1.0 + self.p.stop_loss_pct / 100.0)
                        self.stop_loss_order = self.buy(exectype=bt.Order.Stop, price=stop_price, size=abs(self.position.size))
                        self.log(f'{dt_str} PLACED BUY STOP @ {stop_price:.2f} (Ref: {self.stop_loss_order.ref}) for size {abs(self.position.size)}')
                else: 
                    if self.stop_loss_order and self.stop_loss_order.alive():
                        self.cancel(self.stop_loss_order)
                        self.log(f'{dt_str} Position closed by strategy. CANCELLING PENDING STOP ORDER {self.stop_loss_order.ref}')
                        self.stop_loss_order = None
            elif self.stop_loss_order and order.ref == self.stop_loss_order.ref:
                log_prefix = "BUY" if order.isbuy() else "SELL"
                self.log(f'{dt_str} {log_prefix} STOP EXECUTED, Price: {fill_price:.2f}, Size: {fill_size:.6f}')
                self.stop_loss_order = None 
            if not self.position and self.stop_loss_order and self.stop_loss_order.alive():
                self.cancel(self.stop_loss_order)
                self.log(f'{dt_str} Position flat post-exec. CANCELLING ORPHANED STOP ORDER {self.stop_loss_order.ref}')
                self.stop_loss_order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected, order.Expired]:
            self.log(f'{dt_str} ORDER FAILED/CANCELLED/ETC: Status {order.getstatusname()}, Ref: {order.ref}')
            if self.entry_order and order.ref == self.entry_order.ref:
                self.entry_order = None
            elif self.stop_loss_order and order.ref == self.stop_loss_order.ref:
                self.log(f'{dt_str} Stop loss order {order.getstatusname()}. Position might be unprotected.')
                self.stop_loss_order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(
            f'OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}, Ref: {trade.ref}'
        )

    def next(self):
        if self.entry_order:
            return
        adx_val = self.adx_indicator.lines.adx[0]
        ao_val = self.ao_indicator.lines.ao[0] 
        pctb_val = self.bb_pct_indicator.lines.pctb[0]
        buy_signal = adx_val > 25 and ao_val > 0 and pctb_val < 0 
        sell_signal = adx_val < 10 and ao_val < 0 and pctb_val > 1
        if self.position.size == 0:
            if buy_signal:
                self.log(f'BUY SIGNAL (New Entry): ADX={adx_val:.2f}, AO={ao_val:.2f}, %B={pctb_val:.3f}')
                self.entry_order = self.buy()
            elif sell_signal:
                self.log(f'SELL SIGNAL (New Short Entry): ADX={adx_val:.2f}, AO={ao_val:.2f}, %B={pctb_val:.3f}')
                self.entry_order = self.sell()
        elif self.position.size > 0:
            if sell_signal:
                self.log(f'SELL SIGNAL (Exit Long/Reverse to Short): ADX={adx_val:.2f}, AO={ao_val:.2f}, %B={pctb_val:.3f}')
                self.entry_order = self.sell() 
        elif self.position.size < 0:
            if buy_signal:
                self.log(f'BUY SIGNAL (Exit Short/Reverse to Long): ADX={adx_val:.2f}, AO={ao_val:.2f}, %B={pctb_val:.3f}')
                self.entry_order = self.buy() 
    
    def stop(self):
        # Corrected call to self.log: removed the doprint argument
        self.log(f'(Strategy End) Final Portfolio Value: {self.broker.getvalue():.2f}')
