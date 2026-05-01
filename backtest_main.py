import config
import matplotlib

# disable backtrader chart showing
matplotlib.use('Agg')
import pandas as pd
import pytz
import loguru
import streamlit as st
from finance_data_loader import load_finance_data
from price_volume_page import price_volume_page
from stats_report_page import stats_report_page
from strategy_runner import run_strategy
import traceback

# Streamlit interface
st.set_page_config(layout="wide")
st.title("Models Backtesting")

# Sidebar for inputs
with st.sidebar:
    st.header("Models Controls")
    selected_strategy = st.sidebar.selectbox("Select Strategy", config.strategies, index=config.DEFAULT_STRATEGY, format_func=lambda s: s.name)
    
    # Inputs for the symbol, start and end dates
    symbol = st.text_input("Enter the symbol ", value=config.DEFAULT_TICKER)
    start_date = st.date_input("Start Date", value=pd.to_datetime(config.DEFAULT_INTERVAL[0]))
    end_date = st.date_input("End Date", value=pd.to_datetime(config.DEFAULT_INTERVAL[1]))

    # EMA controls
    st.header("Model Parameters")
    model_params = selected_strategy.show_parameters()
    
    # Button to perform backtesting
    backtest_clicked = st.button("Backtest")

if not backtest_clicked:
    st.markdown("**Please select a strategy and click the Backtest button to run the backtest.**")

if backtest_clicked:
    try:
        finance_data_response = load_finance_data(symbol, start_date=start_date, end_date=end_date)
        
        if finance_data_response.is_cached:
            st.markdown(f"**Data loaded from cache for {symbol} from {finance_data_response.date_from} to {finance_data_response.date_to}.**")
    except Exception as e: # Handle any exceptions during data loading
        print(f"Error loading data for {symbol}: {e}")
        st.error(f"Error loading data for {symbol}: {e}")
        finance_data_response = None
        
    if finance_data_response is None:
        st.error(f"Failed to load data for {symbol}.")
    else:    
        finance_data = finance_data_response.data
        [result, final_result, fig] = run_strategy(selected_strategy, finance_data, model_params)
        
        price_volume_tab, backtesting_stats_tab, list_of_trades_tab, tab4, library_plot_tab = st.tabs(["Price Volume Chart", "Backtesting Stats", "List of Orders", "Equity Curve", "Library Plot" ])
        
        with price_volume_tab:
            price_volume_page(symbol, finance_data)
            
        with backtesting_stats_tab:
            stats_report_page(result, final_result)
        
        with list_of_trades_tab:
            order_list = result.analyzers.trade_list.get_analysis()
            orders_df = pd.DataFrame(order_list)
            orders_df['date'] = pd.to_datetime(orders_df['date'], unit='s').dt.tz_localize('UTC').dt.tz_convert(pytz.timezone('America/New_York'))
            st.markdown("**List of Orders**")
            st.dataframe(orders_df)  # Set index to False and use full width
        
        with library_plot_tab:
            st.pyplot(fig)