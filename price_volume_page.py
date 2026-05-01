import plotly.graph_objs as go
import streamlit as st
from plotly.subplots import make_subplots


def price_volume_page(symbol, finance_data):
    # RSI and Volume: create figure with subplots (smaller row heights)
    price_volume_fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.8, 0.2]  # Reduced heights
    )
    
    # 1. Candlestick Chart
    price_volume_fig.add_trace(go.Candlestick(x=finance_data.index,
                open=finance_data['Open'],
                high=finance_data['High'],
                low=finance_data['Low'],
                close=finance_data['Close'], name='Candlestick'), row=1, col=1)# 4. Volume Plot (if available)
    if 'Volume' in finance_data.columns:
        price_volume_fig.add_trace(go.Bar(x=finance_data.index, y=finance_data['Volume'], name='Volume',
                        marker_color='gray'), row=2, col=1)
    else:
        price_volume_fig.add_trace(go.Scatter(x=finance_data.index, y=[0]*len(finance_data), name='No Volume Data',
                            line=dict(color='gray')), row=2, col=1)

    # Update layout (smaller height)
    price_volume_fig.update_layout(
        title=f'{symbol} Price, Volume',
        height=500,  
        hovermode='x unified',
        showlegend=True,
        xaxis_rangeslider_visible=False,
    )

    # Update y-axes titles
    price_volume_fig.update_yaxes(title_text="Price", row=1, col=1)
    price_volume_fig.update_yaxes(title_text="Volume" if 'Volume' in finance_data.columns else "", row=2, col=1)
    st.plotly_chart(price_volume_fig)