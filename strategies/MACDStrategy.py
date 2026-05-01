import backtrader as bt
import streamlit as st


def show_parameters():
    return {
        "macd_fast": st.number_input("MACD Fast Period", value=12, min_value=1),
        "macd_slow": st.number_input("MACD Slow Period", value=26, min_value=1),
        "macd_signal": st.number_input("MACD Signal Period", value=9, min_value=1),
        "stop_loss": st.number_input("Stop Loss (%)", value=5.0, min_value=0.0, max_value=100.0) / 100,       # 5% stop loss
        "take_profit": st.number_input("Take Profit (%)", value=5.0, min_value=0.0, max_value=100.0) / 100,   # 10% take profit
    }

class MACDStrategy(bt.Strategy):
    params = (
        ("macd_fast", 12),
        ("macd_slow", 26),
        ("macd_signal", 9),
        ("stop_loss", 0.05),       # 5% stop loss
        ("take_profit", 0.1),      # 10% take profit
    )

    def __init__(self):
        # Initialize the MACD indicator
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.macd_fast,
            period_me2=self.params.macd_slow,
            period_signal=self.params.macd_signal,
        )
        # Manually compute the MACD histogram as the difference between MACD and its signal line
        self.macd_hist = self.macd.macd - self.macd.signal
        self.entry_price = None

    def next(self):
        # Check if we are in the market
        if not self.position:
            cash = self.broker.get_cash()
            asset_price = self.data_close[0]
            position_size = cash / asset_price * 0.99  # Adjust position sizing
            # Entry condition: MACD histogram crosses from negative to positive
            if self.macd_hist[0] > 0 and self.macd_hist[-1] <= 0:
                self.buy(size=position_size)
                self.entry_price = self.data.close[0]
                self.log(f"Buy at {self.data.close[0]:.2f}")
        else:
            # Exit condition 1: MACD histogram crosses from positive to negative
            if self.macd_hist[0] < 0 and self.macd_hist[-1] >= 0:
                self.close()
                self.log(f"Sell at {self.data.close[0]:.2f} (MACD histogram crossover)")
            # Exit condition 2: Stop-loss hit
            elif self.data.close[0] <= self.entry_price * (1 - self.params.stop_loss):
                self.close()
                self.log(f"Stop Loss Sell at {self.data.close[0]:.2f}")
            # Exit condition 3: Take-profit reached
            elif self.data.close[0] >= self.entry_price * (1 + self.params.take_profit):
                self.close()
                self.log(f"Take Profit Sell at {self.data.close[0]:.2f}")
                
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")