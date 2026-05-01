# run application:

1. `pip install pandas numpy matplotlib streamlit hurst ta-lib`
2. `streamlit run ".\ST\backtest_hub.py"`

## Override config parameters through cli:

3. `streamlit run ".\ST\backtest_main.py" -- --ticker NVDA --interval 2021-01-01 2025-01-01 --strategy MACDStrategy --market_data_folder "..\marketdata"`
