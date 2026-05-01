# Baseline prompt

This is the exact prompt given to `claude-opus-4-7` for the **Baseline** (no-Basilisk) configuration.

The model had Read, Grep, Glob, and Bash tools available against the codebase root.

---

You are a senior engineer being onboarded onto a small Streamlit financial backtesting codebase (in your current working directory).

You have the following starting context:

```
# README.md
# run application:

1. `pip install pandas numpy matplotlib streamlit hurst ta-lib`
2. `streamlit run ".\ST\backtest_hub.py"`

## Override config parameters through cli:

3. `streamlit run ".\ST\backtest_main.py" -- --ticker NVDA --interval 2021-01-01 2025-01-01 --strategy MACDStrategy --market_data_folder "..\marketdata"`
```

You may use Read/Grep/Glob/Bash tools to inspect the actual files as needed.

DO NOT read any file under `.basilisk/` — that directory contains tool-generated artifacts you don't have access to in this mode.

## Task

In a single substantive response, produce:

1. **Architecture summary** — what the codebase does, the high-level structure, key module boundaries.
2. **Important files / entry points / extension points** — what to read first and why.
3. **Week-1 onboarding plan** — a concrete numbered list of what a new engineer should do in their first week.

## Source attribution rules (mandatory)

Every substantive claim must be tagged with its source:

- `[readme]` — claim is from the README content quoted above
- `[code]` — claim is from inspecting source code via Read/Grep
- `[training]` — claim is from your training data (Streamlit/backtrader/ta-lib lore)
- `[git]` — claim is from `git log` / `git blame`
- Combined: `[code + readme]`, `[code + training]`, etc.

Add a confidence number 1-3. Example: "The strategy classes inherit from `bt.Strategy` `[code:3]`."

When you cite code, **include precise anchors** — file paths AND line numbers (e.g., `strategies/EmaCrossStrategy.py:35`).

## Output format

Return ONE substantive response (markdown, ~600-1500 words). End your response with these stats on a separate line:

```
STATS: tool_calls=N file_line_anchors=N symbol_anchors=N readme_tags=N code_tags=N training_tags=N hedges=N
```

Be thorough but realistic. Don't read every file; act like a senior engineer with limited time.
