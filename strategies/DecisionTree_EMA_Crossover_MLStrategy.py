import backtrader as bt
import numpy as np
from sklearn.tree import DecisionTreeClassifier
import streamlit as st


def show_parameters():
    return {
        "lookback_period": st.number_input("Lookback Period", value=24, min_value=1, step=1),
    }

class DecisionTree_EMA_Crossover_MLStrategy(bt.Strategy):
    params = (
        ("lookback_period", 24),
    )

    def __init__(self):
        self.data_close = self.datas[0].close
        self.window = self.params.lookback_period
        self.model = DecisionTreeClassifier(random_state=42)
        
        # Indicators
        self.emas = bt.indicators.ExponentialMovingAverage(self.data_close, period=50)
        self.emal = bt.indicators.ExponentialMovingAverage(self.data_close, period=200)
        self.rsi = bt.indicators.RelativeStrengthIndex(self.data_close, period=14)
        self.macd = bt.indicators.MACDHisto(self.data_close,
                                            period_me1=12,
                                            period_me2=26,
                                            period_signal=9)
        self.order = None  # To track pending orders

    def next(self):
        # Only process if we have enough data for the lookback period
        if len(self) > self.window:
            # Generate features from the lookback window
            emas_values = np.array(self.emas.get(size=self.window))
            emal_values = np.array(self.emal.get(size=self.window))
            rsi_values = np.array(self.rsi.get(size=self.window))
            macd_values = np.array(self.macd.macd.get(size=self.window))
            signal_values = np.array(self.macd.signal.get(size=self.window))
            
            # Stack features into X
            X = np.column_stack((emas_values, emal_values, rsi_values, macd_values, signal_values))
            # Create target: 1 if price went up, 0 otherwise (using price diff over the window+1)
            prices = np.array(self.data_close.get(size=self.window + 1))
            y = np.where(np.diff(prices) > 0, 1, 0)
            
            # Prepare training data: use all but the last row for training
            X_train = X[:-1]
            y_train = y[1:]  # Align target with features (shifted by one)
            X_test = X[-1]
            
            # Train the decision tree on the latest lookback window
            self.model.fit(X_train, y_train)
            # Predict the next move using the most recent features
            prediction = self.model.predict(X_test.reshape(1, -1))
            
            # Check if there is no open position
            if not self.position:
                cash = self.broker.get_cash()
                asset_price = self.data_close[0]
                position_size = cash / asset_price * 0.99  # Adjust position sizing
                
                # Long entry: if prediction is 1 and the short EMA is above the long EMA
                if prediction[0] == 1 and self.emas[0] > self.emal[0]:
                    self.buy(size=position_size)
                    self.log(f"Buy order placed at price: {asset_price:.2f}")
            else:
                # Exit condition: if short EMA falls below long EMA
                if self.emas[0] < self.emal[0]:
                    self.close()
                    self.log(f"Position closed at price: {self.data_close[0]:.2f}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        # Order completed
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f"Buy executed: {order.executed.price:.2f}")
            elif order.issell():
                self.log(f"Sell executed: {order.executed.price:.2f}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order canceled/margin/rejected")
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")
