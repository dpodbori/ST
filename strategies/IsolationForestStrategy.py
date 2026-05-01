#!/usr/bin/env python3
"""
Backtesting script for an Isolation Forest-based trading strategy.

This script defines an Isolation Forest model for anomaly detection in financial data
and a Backtrader strategy that uses this model to generate trading signals.
It now uses yfinance to fetch Bitcoin data for the last 3 years.
"""

import logging
from datetime import datetime

import backtrader as bt
import numpy as np
import pandas as pd
from curl_cffi import requests
from sklearn.ensemble import IsolationForest

session = requests.Session(impersonate="chrome")
import streamlit as st


def show_parameters():
    return {
        'historical_data_path': st.text_input("Historical Data Path", value="data/btc_training_data.csv"),
        'contamination': st.number_input("Contamination Factor", value=0.01, min_value=0.001, max_value=0.1, step=0.001),
        'cooldown_period': st.number_input("Cooldown Period", value=7, min_value=1, step=1),
        'lookback_period_for_mean': st.number_input("Lookback Period for Mean", value=200, min_value=50, step=10)
    }

# --- Configuration Constants ---
CONTAMINATION_FACTOR: float = 0.01  # Adjusted for potentially more volatile crypto data
COOLDOWN_PERIOD: int = 7
INITIAL_CASH: float = 100000.0
# DEFAULT_HISTORICAL_DATA_FILE will be set dynamically
TRAINING_DATA_FILENAME: str = "data/btc_training_data.csv"
BACKTEST_DATA_FILENAME: str = "data/btc_backtest_data.csv" # Optional, if saving backtest data

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- Isolation Forest Model Class ---
class AnomalyDetectionModel:
    """
    A wrapper for the Isolation Forest model to detect anomalies in financial data.

    The model is trained on historical data and can then be used to predict
    if new data points are outliers.
    """

    def __init__(
        self,
        training_data: pd.DataFrame,
        contamination: float = CONTAMINATION_FACTOR,
        columns_to_use: list = None,
    ):
        """
        Initializes and trains the Isolation Forest model.

        Args:
            training_data (pd.DataFrame): DataFrame containing historical data for training.
                                         Expected columns: "Open", "High", "Low", "Close", "Volume".
            contamination (float): The expected proportion of outliers in the data set.
            columns_to_use (list, optional): Specific columns from training_data to use for model fitting.
                                             Defaults to ["Open", "High", "Low", "Close", "Volume"].
        """
        if columns_to_use is None:
            self.columns = ["Open", "High", "Low", "Close", "Volume"]
        else:
            self.columns = columns_to_use

        if not all(col in training_data.columns for col in self.columns):
            raise ValueError(
                f"Training data missing one or more required columns: {self.columns}. Available: {training_data.columns}"
            )

        model_input_data = training_data[self.columns].copy()

        if model_input_data.empty:
            raise ValueError("Training data for the model cannot be empty.")
        
        # Ensure data is numeric and handle potential NaNs
        for col in self.columns:
            model_input_data[col] = pd.to_numeric(model_input_data[col], errors='coerce')
        model_input_data.dropna(inplace=True) # Drop rows with NaNs after coercion

        if model_input_data.empty: # Check again after dropping NaNs
            raise ValueError("Training data became empty after handling non-numeric values or NaNs.")


        self.mean: pd.Series = model_input_data.mean()
        self.std: pd.Series = model_input_data.std()

        # Handle cases where std might be zero (e.g., constant column)
        self.std = self.std.replace(0, 1e-6) # Avoid division by zero

        normalized_data = (model_input_data - self.mean) / self.std

        self.iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42, # For reproducibility
        )
        self.iso_forest.fit(normalized_data)
        logger.info(f"Isolation Forest model trained successfully on {len(normalized_data)} samples.")
        self.training_mean_close = self.mean.get("Close", np.nan)


    def predict_outlier(self, data_point: pd.DataFrame) -> int:
        """
        Predicts if a new data point is an outlier.

        Args:
            data_point (pd.DataFrame): A single-row DataFrame with data for prediction.
                                       Must contain the same columns used for training.

        Returns:
            int: -1 if the point is an outlier, 1 if it's an inlier.
        """
        if not all(col in data_point.columns for col in self.columns):
            raise ValueError(
                f"Prediction data point missing one or more required columns: {self.columns}"
            )

        point_to_predict = data_point[self.columns].copy()
        # Ensure data is numeric for prediction
        for col in self.columns:
            point_to_predict[col] = pd.to_numeric(point_to_predict[col], errors='coerce')
        
        # If any value became NaN during coercion, we cannot normalize reliably with stored mean/std
        if point_to_predict.isnull().values.any():
            logger.warning(f"NaN value encountered in data_point for prediction: {data_point}. Returning as inlier.")
            return 1 # Treat as inlier if data is corrupted

        normalized_point = (point_to_predict - self.mean) / self.std
        return self.iso_forest.predict(normalized_point)[0]


# --- Trading Strategy Class using Isolation Forest ---
class IsolationForestStrategy(bt.Strategy):
    """
    Trading strategy that uses an Isolation Forest model to identify anomalies
    and generate buy/sell signals.
    """

    params = (
        ("historical_data_path", TRAINING_DATA_FILENAME), # Default, will be overridden
        ("contamination", CONTAMINATION_FACTOR),
        ("cooldown_period", COOLDOWN_PERIOD),
        ("lookback_period_for_mean", 200) # Lookback for dynamic mean comparison
    )

    def __init__(self):
        """Initializes the strategy, data lines, and the anomaly detection model."""
        self.data_open: bt.line.Line = self.datas[0].open
        self.data_high: bt.line.Line = self.datas[0].high
        self.data_low: bt.line.Line = self.datas[0].low
        self.data_close: bt.line.Line = self.datas[0].close
        self.data_volume: bt.line.Line = self.datas[0].volume
        self.data_datetime: bt.line.Line = self.datas[0].datetime

        try:
            historical_data = pd.read_csv(self.p.historical_data_path, index_col='Date', parse_dates=True)
        except FileNotFoundError:
            logger.error(f"Historical data file not found: {self.p.historical_data_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            raise

        self.model = AnomalyDetectionModel(
            training_data=historical_data,
            contamination=self.p.contamination
        )
        self.training_mean_close = self.model.training_mean_close
        if pd.isna(self.training_mean_close):
            logger.warning("'Close' column not found in model's training mean. Signal logic might be affected.")


        self.cooldown_counter: int = 0
        self.order: bt.Order = None

        self.dynamic_mean_close = bt.indicators.SimpleMovingAverage(
            self.datas[0].close, period=self.p.lookback_period_for_mean
        )


    def log(self, txt: str, dt: datetime = None, level: int = logging.INFO):
        """Logs a message with the current date of the simulation."""
        dt_val = dt or self.data_datetime.datetime(0) # Get datetime object
        log_func = logger.info if level == logging.INFO else logger.warning
        log_func(f"{dt_val.isoformat()} - {txt}")

    def notify_order(self, order: bt.Order):
        """Handles order notifications."""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
            elif order.issell():
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}"
                )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order Canceled/Margin/Rejected: Status {order.Status[order.status]}", level=logging.WARNING)

        self.order = None

    def notify_trade(self, trade: bt.Trade):
        """Handles trade notifications."""
        if not trade.isclosed:
            return
        self.log(f"OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}")


    def next(self):
        """Defines the logic for each bar."""
        # Ensure enough data for indicators
        if len(self.data_close) < self.p.lookback_period_for_mean :
            return

        current_bar_data = pd.DataFrame(
            {
                "Open": [self.data_open[0]],
                "High": [self.data_high[0]],
                "Low": [self.data_low[0]],
                "Close": [self.data_close[0]],
                "Volume": [self.data_volume[0]],
            }
        )

        if self.order:
            return

        is_outlier = self.model.predict_outlier(current_bar_data) == -1

        comparison_mean_close = self.dynamic_mean_close[0]
        if pd.isna(comparison_mean_close) or comparison_mean_close == 0:
            comparison_mean_close = self.training_mean_close
            if pd.isna(comparison_mean_close):
                 # self.log("Mean for comparison is not available. Skipping trade logic.", level=logging.WARNING)
                 return


        if is_outlier:
            current_close = self.data_close[0]
            if not self.position:
                if current_close < comparison_mean_close and self.cooldown_counter == 0:
                    self.log(f"BUY SIGNAL - Outlier detected below mean. Price: {current_close:.2f}, Mean: {comparison_mean_close:.2f}")
                    self.order = self.buy(size=0.1) # Example: Buy 0.1 BTC
                    self.cooldown_counter = self.p.cooldown_period
            elif self.position.size > 0 :
                 if current_close > comparison_mean_close:
                    self.log(f"SELL SIGNAL (Exit Long) - Outlier detected above mean. Price: {current_close:.2f}, Mean: {comparison_mean_close:.2f}")
                    self.order = self.sell(size=self.position.size)

        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1