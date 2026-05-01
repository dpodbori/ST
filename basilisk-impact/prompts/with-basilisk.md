# With-Basilisk prompt

This is the exact prompt given to `claude-opus-4-7` for the **With Basilisk** configuration.

Same model and same toolset (Read, Grep, Glob, Bash) as the baseline. The only difference: the model is told two YAML files exist in `.basilisk/` and instructed to read them first.

---

You are a senior engineer being onboarded onto a small Streamlit financial backtesting codebase (in your current working directory).

Starting context:

```
# README.md
# run application:

1. `pip install pandas numpy matplotlib streamlit hurst ta-lib`
2. `streamlit run ".\ST\backtest_hub.py"`

## Override config parameters through cli:

3. `streamlit run ".\ST\backtest_main.py" -- --ticker NVDA --interval 2021-01-01 2025-01-01 --strategy MACDStrategy --market_data_folder "..\marketdata"`
```

You also have access to deterministic structural facts produced by the Basilisk toolkit:

- `.basilisk/structural-facts.yaml` — codebase stats, pattern clusters (exact AST twins), load-bearing breakdown, top files by fan-in, intervention surface (route handlers, event handlers, plugin points)
- `.basilisk/pack-coverage.yaml` — verdict on whether the default analyzer pack speaks this codebase's framework

**Read both YAML files first.** Then use Read/Grep/Glob to inspect source files as needed.

## Task

In a single substantive response, produce:

1. **Architecture summary** — what the codebase does, the high-level structure, key module boundaries.
2. **Important files / entry points / extension points** — what to read first and why.
3. **Week-1 onboarding plan** — a concrete numbered list of what a new engineer should do in their first week.

## Source attribution rules (mandatory)

Every substantive claim must be tagged with its source:

- `[basilisk]` — claim is from the Basilisk YAML files
- `[readme]` — claim is from the README content
- `[code]` — claim is from inspecting source code
- `[training]` — claim is from your training data (Streamlit/backtrader/ta-lib lore)
- `[git]` — from git log / git blame
- Combined: `[basilisk + code]`, `[code + readme]`, etc. **Use combined form when applicable** — claims grounded in both Basilisk AND code-verification are stronger.

Add a confidence 1-3. Example: "13 strategies share an exact-AST `notify_trade` method `[basilisk + code:3]`."

When you cite code, **include precise anchors** — file paths AND line numbers. Basilisk artifacts give you these directly; use them.

## Source priority

Prefer this order: `[basilisk]` first → `[basilisk+code]` for facts also verifiable today → `[code]` alone only when Basilisk is silent → `[readme]` for intent → `[training]` for explicit framework lore. Citing `[code]` alone for a fact already in the YAML is non-compliant — use `[basilisk + code]`.

## Output format

Return ONE substantive response (markdown, ~600-1500 words). End your response with these stats on a separate line:

```
STATS: tool_calls=N file_line_anchors=N symbol_anchors=N basilisk_tags=N readme_tags=N code_tags=N training_tags=N combined_tags=N hard_numbers=N hedges=N
```

Be thorough but realistic. Act like a senior engineer with limited time.
