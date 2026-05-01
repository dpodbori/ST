import os
from dataclasses import dataclass
from typing import Optional

import config
import pandas as pd
import yfinance as yf


@dataclass
class FinanceDataResult:
    data: pd.DataFrame
    date_from: pd.Timestamp
    date_to: pd.Timestamp
    is_cached: bool


def load_finance_data(ticker, start_date, end_date):
    print(f'Fetching {ticker} from {start_date} to {end_date}…')
    is_cached = False
    df = (
        yf.download(
            ticker,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=False
        )
        .droplevel(axis=1, level=1)
    )
    df.index = pd.to_datetime(df.index)
    # If Yahoo returns no data, try loading from local file
    if df.empty:
        if config.MARKET_DATA_FOLDER is None:
            print("MARKET_DATA_FOLDER is not set. Please set it in cli argument --market_data_folder.")
            return None
        file_path = os.path.join(config.MARKET_DATA_FOLDER, f"{ticker}.csv")
        if os.path.exists(file_path):
            print(f"Yahoo Finance returned no data. Loading from {file_path}")
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            df = df.rename(columns={"Date": "index"})
            is_cached = True
        else:
            print(f"No local file found for {ticker} in {config.MARKET_DATA_FOLDER}")
            return None
    else:
        # If data is multi-index, flatten it
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(axis=1, level=1)
    df.index = pd.to_datetime(df.index)
    date_from = df.index.min() if not df.empty else None
    date_to = df.index.max() if not df.empty else None
    return FinanceDataResult(df, date_from, date_to, is_cached)