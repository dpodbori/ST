# Methodology

Supporting detail for the head-to-head comparison in [`README.md`](README.md).

## Quality rubric (4 dimensions, 1-5 each)

| dimension | what 5 means | what 3 means | what 1 means |
|---|---|---|---|
| **Specificity** | Most claims include precise anchors (file:line ranges, exact symbol paths, fan-in counts, named framework constructs) | Mix of specific and general claims | Generic; could apply to any project of this kind |
| **Grounding** | Every substantive claim cites a precise, verifiable source (file:line, README section, scan-derived count with origin) | Mix of grounded and asserted; sources mentioned but not precise | Cannot tell evidence from inference |
| **Actionability** | A senior engineer could act on this directly without further research | Useful starting point but needs additional scoping | Vague; doesn't enable concrete next steps |
| **Calibration** | Explicitly distinguishes verified from inferred; flags uncertainty | Some hedging but inconsistent | All claims asserted at the same confidence level |

The rubric is intentionally rigorous on what 5 means at the high end — particularly Specificity, which requires *precise* anchors (file:line, exact paths, counts), not just "names a thing."

## Source attribution requirement

Both modes were instructed to tag every substantive claim with its source:

- `[readme]` — claim is from the README content
- `[code]` — claim is from inspecting source code via Read/Grep
- `[training]` — claim is from the model's training data (framework knowledge)
- `[git]` — claim is from `git log` / `git blame`
- `[basilisk]` — *(With Basilisk only)* claim is from the structural-facts YAML
- Combined tags (e.g., `[basilisk + code]`, `[code + readme]`) — claim is supported by multiple sources

Each tag includes a confidence number 1-3.

## Objective counts (descriptive, not aggregated into a score)

The counts reported in [`README.md`](README.md) are extracted from each response by tag-matching and citation-pattern matching. They are descriptive — we don't roll them up into a quality number. They show what each mode actually produced, side-by-side.

## Efficiency metrics

- `total_tokens` — input + output tokens summed across the conversation, as reported by the model API
- `tool_calls` — count of Read/Grep/Glob/Bash invocations made by the model during the run
- `duration` — wall-clock time from prompt submission to final response

## Pack support note (technical)

Basilisk's default analyzer pack covers mainstream framework idioms (Python's Django/FastAPI/Flask/Graphene/Celery; Java's Spring/JPA; TypeScript's Next.js/tRPC). For analyses involving backtrader, eight lines of pack code recognize backtrader's four base classes (`bt.Strategy`, `bt.Analyzer`, `bt.Indicator`, `bt.Observer`). The pack addition itself is a one-time, ~10-minute change; once added, every Streamlit + backtrader codebase scanned afterward inherits the support.

## Scoring caveats

- **Single run per cell (N=1).** Both responses are single samples. Variance unmeasured. For hypothesis-grade evidence we'd run N=3+ per cell.
- **Self-scoring.** The same author who designed this comparison applied the rubric to both responses. Independent scoring would strengthen the methodology. Disclosed for transparency.
- **Same model, same temperature, same effort setting** for both runs. The only deliberate variable is the starting context.

## Why this rubric, why these counts

The rubric measures *quality on a comprehension task*. The objective counts measure *evidence density and source-attribution discipline*. Together they answer:

1. Are both responses good enough to act on? *(rubric)*
2. Where does the additional evidence in the With-Basilisk response come from, and is it verifiable? *(counts)*
3. How much does the LLM trust Basilisk for structural facts vs. re-deriving them by reading code? *(source-tag mix)*

The 1-5 rubric ceiling tie at this codebase size is itself informative: it tells you that on a small, doc-poor codebase, Mode A — the baseline — produces an actionable response. Basilisk's value-add at this scale is **efficiency + irreducible structural insight**, not "fixing a broken response."
