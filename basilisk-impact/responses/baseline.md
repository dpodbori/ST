# Baseline response

Verbatim output from `claude-opus-4-7` running the [baseline prompt](../prompts/baseline.md). No edits.

---

# Streamlit Backtest Hub — Onboarding Brief

## 1. Architecture Summary

This is a small **Streamlit single-page app** that backtests stock-trading strategies against historical OHLCV data using the `backtrader` engine `[code:3]`. The full app lives in ~9 top-level Python files plus a `strategies/` directory containing 34 strategy implementations `[code:3]` (verified via directory listing).

**High-level flow** (entry: `backtest_main.py`):
1. `config.py` runs at import time, scans `strategies/*.py`, dynamically imports each module, finds the first `bt.Strategy` subclass, and registers it as a `StrategyDefinition` `[code:3]` (`config.py:23-37`).
2. The Streamlit sidebar lets the user pick a strategy, ticker, date range, and per-strategy parameters via that strategy's `show_parameters()` function `[code:3]` (`backtest_main.py:23-32`).
3. On Backtest click, `finance_data_loader.load_finance_data()` fetches OHLCV from Yahoo Finance via `yfinance`, falling back to `MARKET_DATA_FOLDER/<ticker>.csv` if Yahoo returns nothing `[code:3]` (`finance_data_loader.py:18-53`).
4. `strategy_runner.run_strategy()` builds a `bt.Cerebro` engine, registers the strategy + 7 built-in analyzers + the custom `TradeListAnalyzer`, runs the simulation, and returns `(result, final_value, fig)` `[code:3]` (`strategy_runner.py:6-44`).
5. Five Streamlit tabs render outputs: candlestick (`price_volume_page.py`), stats table (`stats_report_page.py`), order list, equity curve placeholder, and the Matplotlib figure from `cerebro.plot()` `[code:3]` (`backtest_main.py:57-73`).

**Module boundaries:**
- **Config / strategy registry** — `config.py` (single source of CLI args, defaults, dynamic strategy discovery) `[code:3]`.
- **Data layer** — `finance_data_loader.py` (Yahoo + CSV fallback, returns `FinanceDataResult` dataclass) `[code:3]`.
- **Engine wrapper** — `strategy_runner.py` (thin Cerebro setup) `[code:3]`.
- **Custom analyzer** — `trade_list_analyzer.py` (a `bt.Analyzer` subclass that records each completed/partial order for the orders table) `[code:3]` (`trade_list_analyzer.py:4-39`).
- **UI pages** — `backtest_main.py` (controller + tabs), `price_volume_page.py` (Plotly candle/volume), `stats_report_page.py` (Markdown table from `TradeAnalyzer`) `[code:3]`.
- **Strategies** — `strategies/*.py`, each a self-contained module exposing `show_parameters()` + one `bt.Strategy` subclass `[code:3]` (pattern verified in `MACDStrategy.py:5-21` and `EmaCrossStrategy.py:6-19`; 34/34 modules export `show_parameters`).

**Note on README drift:** README says `streamlit run ".\ST\backtest_hub.py"` but no such file exists — the real entry is `backtest_main.py` `[code + readme:3]`. The CLI override example in the README does point at `backtest_main.py` correctly `[readme:3]`.

## 2. Key Files / Entry Points / Extension Points

Read in this order on day 1:

1. **`backtest_main.py`** (73 lines) — top-level Streamlit controller; shows the entire user journey end-to-end `[code:3]`.
2. **`config.py`** (61 lines) — strategy auto-discovery (`load_strategies()` at `config.py:23`) and CLI argparse (`parse_args()` at `config.py:41`). Note: `parse_args()` is invoked at import time, which is unusual for a Streamlit app `[code:3]`.
3. **`strategy_runner.py`** (44 lines) — the Cerebro wiring. The list of analyzers at `strategy_runner.py:25-32` defines what stats are available downstream `[code:3]`.
4. **`strategies/MACDStrategy.py`** and **`strategies/EmaCrossStrategy.py`** — canonical examples of the strategy convention: module-level `show_parameters()` returning a dict that is splatted into the strategy's `params` tuple `[code:3]` (`MACDStrategy.py:5-21`, `EmaCrossStrategy.py:6-19`).
5. **`trade_list_analyzer.py`** — the only custom backtrader extension; demonstrates the `notify_trade` / `notify_order` hooks `[code + training:3]`.
6. **`finance_data_loader.py`** — the Yahoo→CSV fallback path is the most likely source of demo-time failures (no internet, rate limits) `[code:2]`.
7. **`stats_report_page.py`** — couples tightly to backtrader's `TradeAnalyzer` schema (`trades_analysis.won.pnl.max`, etc.); changes here require knowing backtrader internals `[code + training:3]`.

**The extension point** is unambiguous: drop a new file into `strategies/` that defines (a) a module-level `show_parameters()` returning a dict and (b) one class deriving from `bt.Strategy`. `config.load_strategies()` will pick it up on next app launch `[code:3]` (`config.py:25-34`).

## 3. Week-1 Onboarding Plan

1. **Day 1 AM — Environment.** Install deps (`pip install pandas numpy matplotlib streamlit hurst ta-lib` plus `backtrader`, `yfinance`, `plotly`, `loguru`, `pytz` — all imported but not in the README's pip line) `[readme + code:3]`. Note `ta-lib` requires a native library install on macOS/Linux `[training:2]`. Launch via `streamlit run backtest_main.py` (not `backtest_hub.py` as README says) `[code:3]`.

2. **Day 1 PM — Walk one happy path.** Open the app, run `EmaCrossStrategy` on `AMZN` over the default `2020-01-01`–`2025-05-17` window `[code:3]` (`config.py:8-10`). Click through all 5 tabs and confirm orders/stats render.

3. **Day 2 — Read the controller end-to-end.** Step through `backtest_main.py:1-73` with a debugger; observe the `result`, `final_result`, `fig` triple returned by `run_strategy` `[code:3]`.

4. **Day 2-3 — Trace one strategy execution.** Pick `MACDStrategy`. Read `MACDStrategy.py:35-58` (the `next()` method) and tie each entry/exit branch to backtrader's bar-by-bar evaluation model `[code + training:3]`. Skim 3-4 more strategies (e.g. `BollingerRSIReversion_Strategy.py`, `HMMTrendRegimeStrategy.py`, `IsolationForestStrategy.py`) to gauge variety — the codebase mixes simple TA-driven strategies with ML-based ones (Isolation Forest, HMM, Decision Tree) `[code:3]`.

5. **Day 3 — Understand analyzers.** Map each analyzer registered in `strategy_runner.py:25-32` (`SharpeRatio`, `AnnualReturn`, `Returns`, `DrawDown`, `TradeAnalyzer`, `SQN`, `Calmar`, `TradeListAnalyzer`) to where it is consumed in `stats_report_page.py:15-52`. Note that several analyzers are registered but never displayed (e.g. `sharpe`, `calmar`, `sqn` are computed but not rendered) — that's a likely first ticket `[code:3]`.

6. **Day 4 — Write a new strategy.** Add `strategies/SmaCrossStrategy.py` following the `EmaCrossStrategy.py` template `[code:3]`. Verify it appears in the sidebar dropdown without code changes elsewhere — this validates the auto-discovery contract.

7. **Day 4 — Fix the README drift.** Either rename `backtest_main.py` to `backtest_hub.py` or correct the README. Add the missing deps (`backtrader`, `yfinance`, `plotly`, `loguru`, `pytz`) to the install line `[code + readme:3]`.

8. **Day 5 AM — Audit data layer fragility.** `finance_data_loader.py:21-30` calls `.droplevel(axis=1, level=1)` unconditionally, then again conditionally at line 49 — the second branch is dead given the early call. Test with an empty Yahoo response and the CSV fallback to confirm `[code:2]`.

9. **Day 5 AM — Audit the Streamlit + argparse interaction.** `config.parse_args()` runs at import; this can collide with Streamlit's own arg handling (the `--` separator in the README is a workaround) `[code + training:2]`. Document the gotcha or move CLI parsing behind `if __name__ == "__main__"`.

10. **Day 5 PM — Pick a starter ticket.** Suggested options: (a) wire the unused `sharpe`/`calmar`/`sqn` analyzers into `stats_report_page.py`; (b) populate the empty "Equity Curve" tab (`backtest_main.py:57` declares `tab4` but never fills it) `[code:3]`; (c) cache `yf.download` results to disk so reruns don't hit Yahoo every time. Each is a self-contained, ~half-day change that exercises a different module boundary.

```
STATS: tool_calls=8 file_line_anchors=27 symbol_anchors=29 readme_tags=5 code_tags=27 training_tags=5 hedges=1
```
