# With-Basilisk response

Verbatim output from `claude-opus-4-7` running the [with-Basilisk prompt](../prompts/with-basilisk.md). No edits.

---

# Senior-Engineer Onboarding: ST Streamlit Backtester

## 1. Architecture summary

This is a small Streamlit web app (41 Python files, 4,988 LOC) `[basilisk:3]` that runs financial trading backtests on top of the `backtrader` library. The user picks a strategy, ticker, and date range in the sidebar; data is fetched from Yahoo Finance (with a CSV fallback); a `backtrader.Cerebro` engine runs the strategy; results are rendered as five Streamlit tabs (price/volume, stats, order list, equity curve, library plot) `[code + readme:3]`.

High-level structure (single flat package, no nesting beyond `strategies/`) `[basilisk + code:3]`:

- **UI / orchestration** — `backtest_main.py` is the actual Streamlit entry (despite the README calling it `backtest_hub.py`) `[code + readme:3]`. It wires sidebar inputs through `load_finance_data` -> `run_strategy` -> three rendering helpers.
- **Config + plugin discovery** — `config.py` is the architectural hub: fan-in = 4, the highest in the repo `[basilisk:3]`. It defines the `StrategyDefinition` dataclass and the `load_strategies()` function that dynamically `importlib.import_module`s every `.py` file in `strategies/`, finds the first class subclassing `bt.Strategy`, and pairs it with a module-level `show_parameters()` callable (`config.py:23-35`) `[basilisk + code:3]`. This is the de facto plugin loader.
- **Data layer** — `finance_data_loader.py:18` `load_finance_data()` returns a `FinanceDataResult` dataclass; falls back to `MARKET_DATA_FOLDER` CSV when `yfinance` is empty `[code:3]`.
- **Engine wrapper** — `strategy_runner.py:6` `run_strategy()` builds a `Cerebro`, attaches 7 stock backtrader analyzers (Sharpe, AnnualReturn, Returns, DrawDown, TradeAnalyzer, SQN, Calmar) plus the custom `TradeListAnalyzer`, sets cash=$100k and 0.1% commission from `config.py:11-12` `[code:3]`.
- **Custom analyzer** — `trade_list_analyzer.py` is a `bt.Analyzer` subclass with `notify_trade`, `notify_order`, `get_analysis` — all four methods are flagged as plugin points with confidence=high `[basilisk:3]`. This is the only file outside `strategies/` with `notify_*` hooks.
- **Strategy library** — 34 strategy files under `strategies/` `[code:3]`, each conforming to a duck-typed contract: `(1)` a class subclassing `bt.Strategy`, `(2)` a module-level `show_parameters()` returning a dict of Streamlit widgets `[code + training:3]`. Examples: `EmaCrossStrategy.py:14`, `MACDStrategy.py:14`.
- **Page renderers** — `price_volume_page.py` (Plotly candlestick + volume) and `stats_report_page.py` (TradeAnalyzer markdown table) `[code:3]`.

**Pattern-cluster signal (this is the load-bearing finding):** Basilisk reports 9 exact-AST clusters covering 60 method instances `[basilisk:3]`. The biggest:
- 13 strategies share an identical `notify_trade` body (cluster `b2757f36`, avg 16 nodes) `[basilisk:3]`
- 11 strategies share an identical `log` body (cluster `ea69baa9`, avg 19 nodes) `[basilisk:3]`
- 10 more share another `log` variant (cluster `67bd96bd`) `[basilisk:3]`
- 8 strategies share an identical `stop` method `[basilisk:3]`
- 5 strategies share an identical `notify_order` (avg 83 nodes — substantial duplication) `[basilisk:3]`

That is heavy copy-paste boilerplate, not framework polymorphism. A senior should treat the strategies as a candidate for a `BaseStrategy` mixin extracting `log`, `notify_trade`, and `notify_order`.

**Load-bearing posture:** 40 of 41 files are LOAD_BEARING (98.5% of LOC); 1 file (73 LOC) is TEST `[basilisk:3]`. There is essentially no test suite — high risk for refactoring.

**Pack coverage verdict:** `well-covered` — 190 intervention points across 41 files (4.6/file density), default analyzer pack speaks this codebase `[basilisk:3]`. No third-party framework registered as `detected_frameworks` (backtrader and Streamlit are recognized via the generic event-handler / plugin-point shape) `[basilisk:3]`.

## 2. Important files / entry points / extension points

Read in this order:

1. `config.py` — fan-in=4 `[basilisk:3]`; understand `StrategyDefinition` and `load_strategies()` first, because everything else assumes the discovery contract.
2. `backtest_main.py` — the Streamlit entry; 73 lines, the entire UI flow `[code:3]`. Note: README's `backtest_hub.py` is stale `[readme + code:3]`.
3. `strategy_runner.py` — analyzer wiring and Cerebro setup `[code:3]`.
4. `trade_list_analyzer.py:5,10,24,38` — the four highest-importer plugin points in the repo `[basilisk:3]`; this is the contract the order-list tab depends on.
5. One canonical strategy, e.g. `strategies/EmaCrossStrategy.py` `[basilisk + code:3]` — to internalize the `show_parameters` + `bt.Strategy` duck-typed pair.
6. `finance_data_loader.py`, `price_volume_page.py`, `stats_report_page.py` — small, peripheral; skim last `[code:3]`.

**Extension points (where new code goes):**
- New strategy = drop a file into `strategies/`; auto-discovered on next reload `[basilisk + code:3]`.
- Strategy hooks Basilisk lists as `plugin_point`/`event_handler`: `__init__`, `next`, `notify_order`, `notify_trade`, `log`, `stop` `[basilisk:3]`. 178 event handlers + 12 plugin points across the repo `[basilisk:3]`.
- New analyzer = subclass `bt.Analyzer`, register in `strategy_runner.py:25-32` `[code + training:3]`.
- New tab/page = add to the `st.tabs(...)` call in `backtest_main.py:57` `[code:3]`.

## 3. Week-1 onboarding plan

1. **Day 1 morning — environment.** Install per README: `pip install pandas numpy matplotlib streamlit hurst ta-lib` plus the missing-from-README ones I observed in code (`backtrader`, `yfinance`, `loguru`, `plotly`, `pytz`) `[readme + code:3]`. `ta-lib` requires native libs on macOS (`brew install ta-lib`) `[training:2]`.
2. **Day 1 afternoon — first run.** Run `streamlit run ST/backtest_main.py` (note: not `backtest_hub.py` — README is stale) `[readme + code:3]`. Backtest AMZN with `EmaCrossStrategy` to verify the five tabs render.
3. **Day 2 — read the spine.** `config.py` -> `backtest_main.py` -> `strategy_runner.py` -> `trade_list_analyzer.py`. Diagram the call sequence sidebar -> `load_finance_data` -> `run_strategy` -> tabs.
4. **Day 3 — strategy contract.** Open `EmaCrossStrategy.py` and `MACDStrategy.py` side-by-side; confirm the `show_parameters()` + `bt.Strategy` duck-typed pair `[code:3]`. Write a "Hello Strategy" file that just buys on day 1, sells on day 100, drop it in `strategies/`, confirm auto-discovery.
5. **Day 4 morning — measure the duplication.** Use Basilisk's `pattern_clusters` data: 13×`notify_trade`, 11+10×`log`, 8×`stop` are byte-AST identical `[basilisk:3]`. Spot-check 2-3 cluster members manually (e.g. `EmaCrossStrategy.py:59` vs `DemaCrossStrategy.py:51`) to confirm before proposing a refactor.
6. **Day 4 afternoon — propose `BaseStrategy`.** Draft a mixin extracting `log` and the boilerplate `notify_trade` body. Do NOT merge yet; 98.5% of the codebase is LOAD_BEARING with effectively no tests (1 file / 73 LOC) `[basilisk:3]`.
7. **Day 5 morning — testing safety net.** Before any refactor, add a smoke test that runs each of the 34 strategies on a fixed cached CSV and snapshots `final_result` and `len(orders_df)`. The CSV fallback path (`finance_data_loader.py:33-45`) makes this deterministic `[code:3]`.
8. **Day 5 afternoon — known issues to file.** (a) README references `backtest_hub.py` which doesn't exist `[readme + code:3]`; (b) `finance_data_loader.py:38-42` uses `is_cached=True` only on fallback, and the rename `{"Date":"index"}` looks suspicious — verify with a CSV `[code:2]`; (c) `MACDStrategy.py:60` calls `self.log` but the class doesn't define it — likely a latent bug if `entry_price` ever stays `None` (it's set in `next` before `log` is called, so probably OK in happy path) `[code:2]`; (d) duplicate strategy boilerplate per cluster data above `[basilisk:3]`.
9. **End of week — pair review.** Walk a teammate through `config.py:23-35` (the discovery contract), `strategy_runner.py:25-32` (analyzer registry), and `trade_list_analyzer.py:5-38` (the only custom analyzer); these are the three points where adding capabilities is cheap.

What I would not do in week 1: touch the strategies' shared boilerplate without tests; change the `Cerebro` analyzer set (it feeds `stats_report_page.py`'s rigid TradeAnalyzer expectations `[code:3]`); rely on the Yahoo path in CI (rate limits / network) `[training:2]`.

```
STATS: tool_calls=4 file_line_anchors=24 symbol_anchors=22 basilisk_tags=19 readme_tags=0 code_tags=6 training_tags=3 combined_tags=12 hard_numbers=18 hedges=3
```
