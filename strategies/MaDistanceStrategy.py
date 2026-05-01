# Import necessary libraries
import backtrader as bt
import streamlit as st


def show_parameters():    
    return {
        'ma_period': st.number_input("MA Period", value=20, min_value=1, step=1),
        'ma_type': st.selectbox("MA Type", options=['EMA', 'SMA']),
    }

# Define the MA Distance Logging Strategy
class MaDistanceStrategy(bt.Strategy):
    params = (
        ('ma_period', 20),     # Period for the central EMA
        ('ma_type', 'EMA'),    # Type of MA
    )

    def __init__(self):
        self.data_close = self.datas[0].close

        # Select MA type based on params
        ma_indicator = bt.indicators.EMA if self.params.ma_type == 'EMA' else bt.indicators.SMA
        self.ma = ma_indicator(self.data_close, period=self.params.ma_period)

        # To store the distance calculation
        self.ma_distance_pct = None

    def log(self, txt, dt=None):
        ''' Logging function '''
        dt = dt or self.datas[0].datetime.date(0)
        # Only print logs if distance is calculated
        if self.ma_distance_pct is not None:
             print(f'{dt.isoformat()} - {txt}')

    # We don't need notify_order or notify_trade as we aren't placing orders

    def next(self):
        # Check if MA has enough data
        if len(self.data_close) < self.params.ma_period:
            return

        # Calculate percentage distance
        try:
             # Ensure MA is not zero to avoid division error
             if self.ma[0] != 0:
                  self.ma_distance_pct = ((self.data_close[0] - self.ma[0]) / self.ma[0]) * 100
                  self.log(f'Close={self.data_close[0]:.2f}, MA({self.params.ma_period})={self.ma[0]:.2f}, Distance={self.ma_distance_pct:.2f}%')
             else:
                  self.ma_distance_pct = None # Cannot calculate if MA is zero
        except Exception as e:
             # Catch any potential calculation errors
             # print(f"Error calculating distance: {e}") # Uncomment for debugging
             self.ma_distance_pct = None


        # --- NO Automated Trading Logic ---
        # This section is where a trader would visually inspect the plot
        # or apply statistical analysis to the self.ma_distance_pct value
        # to identify potential extreme levels based on historical data.
        #
        # Example manual thought process:
        # if self.ma_distance_pct is not None:
        #     if self.ma_distance_pct > 6.0: # Hypothetical extreme threshold found via analysis
        #         # Look for bearish candlestick pattern for short entry confirmation
        #         self.log("Price reached extreme distance ABOVE MA - Potential Short Setup")
        #     elif self.ma_distance_pct < -5.0: # Hypothetical extreme threshold
        #         # Look for bullish candlestick pattern for long entry confirmation
        #         self.log("Price reached extreme distance BELOW MA - Potential Long Setup")

