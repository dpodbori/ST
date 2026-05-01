import config
import streamlit as st

def stats_report_page(result, final_result):
    # Prepare stats for display
    stats = []
    initial_cash = config.INITIAL_CASH
    strat = result  

    stats.append(("Starting Portfolio Value", f"{initial_cash:.2f}"))
    stats.append(("Final Portfolio Value", f"{final_result:.2f}"))
    stats.append(("Total Return (%)", f"{(final_result - initial_cash) / initial_cash * 100:.2f}%"))

    # --- TradeAnalyzer ---
    trades_analysis = strat.analyzers.trades.get_analysis()

    if trades_analysis.total.total > 0:
        stats.append(("**Trade Analysis**", ""))
        stats.append(("Total Trades", trades_analysis.total.total))
        stats.append(("Total Open Trades", trades_analysis.total.open))
        stats.append(("Total Closed Trades", trades_analysis.total.closed))

        stats.append(("**PNL**", ""))
        stats.append(("Net PNL", f"{trades_analysis.pnl.net.total:.2f}"))
        stats.append(("Gross PNL", f"{trades_analysis.pnl.gross.total:.2f}"))
        stats.append(("Average PNL per trade", f"{trades_analysis.pnl.net.average:.2f}"))

        stats.append(("**Winning Trades**", ""))
        stats.append(("Count", trades_analysis.won.total))
        if trades_analysis.won.total > 0:
            stats.append(("Max Win", f"{trades_analysis.won.pnl.max:.2f}"))
            stats.append(("Avg Win", f"{trades_analysis.won.pnl.average:.2f}"))
            stats.append(("Total Win PNL", f"{trades_analysis.won.pnl.total:.2f}"))

        stats.append(("**Losing Trades**", ""))
        stats.append(("Count", trades_analysis.lost.total))
        if trades_analysis.lost.total > 0:
            stats.append(("Max Loss", f"{trades_analysis.lost.pnl.max:.2f}"))
            stats.append(("Avg Loss", f"{trades_analysis.lost.pnl.average:.2f}"))
            stats.append(("Total Loss PNL", f"{trades_analysis.lost.pnl.total:.2f}"))

        # Other stats
        stats.append(("Win Rate (% of closed)", f"{(trades_analysis.won.total / trades_analysis.total.closed * 100) if trades_analysis.total.closed > 0 else 0:.2f}%"))
        if trades_analysis.lost.pnl.total != 0:
            profit_factor = abs(trades_analysis.won.pnl.total / trades_analysis.lost.pnl.total)
            stats.append(("Profit Factor", f"{profit_factor:.2f}"))
        else:
            stats.append(("Profit Factor", "N/A (no losing trades)"))

        stats.append(("Max Consecutive Wins", trades_analysis.streak.won.longest))
        stats.append(("Max Consecutive Losses", trades_analysis.streak.lost.longest))
        stats.append(("Average Trade Length (bars)", f"{trades_analysis.len.average:.2f}"))
    else:
        stats.append(("No trades executed.", ""))

    # Display as table with group headers
    st.markdown("**Backtesting Stats**")
    table_md = "| Metric | Value |\n|---|---|\n"
    for metric, value in stats:
        if metric.startswith("**") and metric.endswith("**"):
        # Group header row
            table_md += f"| <b>{metric.strip('**')}</b> |  |\n"
        else:
            table_md += f"| {metric} | {value} |\n"
    st.markdown(table_md, unsafe_allow_html=True)