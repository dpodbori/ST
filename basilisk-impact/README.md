# Basilisk impact on Claude reasoning — this codebase

Head-to-head comparison of Claude's reasoning quality on **this specific app**, with and without Basilisk in the workflow. Same model, same prompt, same tools — only the starting context differs.

---

## What we ran

| field | value |
|---|---|
| Codebase | This repo (ST — Streamlit + backtrader financial backtester) |
| Size | 41 Python files, 4,988 LOC |
| Documentation | 325-byte README; no `AGENTS.md`, `CLAUDE.md`, or architectural notes |
| Task | Senior-engineer onboarding brief: architecture summary + key files / extension points + week-1 plan |
| Model | `claude-opus-4-7` (Claude Opus 4.7) |
| Tools available (both modes) | Read, Grep, Glob, Bash |
| Date | 2026-05-01 |

## The two configurations

| config | starting context | tools |
|---|---|---|
| **Baseline** | This codebase + README only | Read, Grep, Glob, Bash |
| **With Basilisk** | This codebase + README + `.basilisk/structural-facts.yaml` + `.basilisk/pack-coverage.yaml` | Read, Grep, Glob, Bash |

Single variable changed: the Basilisk YAML in the starting context. The YAML files are committed in this repo at [`.basilisk/`](../.basilisk/).

---

## Receipts: efficiency

| metric | Baseline | With Basilisk | delta |
|---|---|---|---|
| Total tokens (input + output) | 32,939 | 33,878 | +2.9% |
| Tool calls (Read/Grep/Glob/Bash) | 8 | 4 | **−50%** |
| Wall-clock duration | 75s | 76s | +1% |

Tokens roughly equal. Tool calls — the LLM's "go read the codebase" steps — were halved with Basilisk in the workflow. On larger codebases this gap widens.

## Receipts: quality (rubric, 1-5 each)

Four dimensions, identical rubric applied to both responses.

| dimension | Baseline | With Basilisk |
|---|---|---|
| Specificity | 5 | 5 |
| Grounding | 5 | 5 |
| Actionability | 5 | 5 |
| Calibration | 5 | 5 |

Both responses pass the quality bar at ceiling. The 1-5 rubric is too coarse to differentiate at this codebase size; the differences appear in the counts below. The rubric we used is documented in [`methodology.md`](methodology.md).

## Receipts: anchors and source attribution

Both modes were instructed to cite a source for every substantive claim. Counts:

| metric | Baseline | With Basilisk |
|---|---|---|
| File:line anchors (e.g., `config.py:23`) | 27 | 24 |
| Code-fenced symbol anchors | 29 | 22 |
| `[basilisk]`-tagged claims (Basilisk-derived facts) | 0* | 19 |
| Combined-source tags (e.g., `[basilisk + code]`) | 5 | 12 |
| `[code]`-only tags (single-source code claims) | 27 | 6 |
| YAML-derived hard numbers in claims (counts, %) | 0 | 18 |

*Baseline cannot use `[basilisk]` tags by construction.

The shift: with Basilisk, the LLM cites code-only claims **78% less often** (27 → 6). Most claims that were "I read the code" become "Basilisk's structural map says, and I cross-checked the code." Eighteen specific YAML-derived numbers (cluster sizes, fan-in counts, intervention surface counts) appear in claims that the baseline cannot match.

---

## Findings present in "With Basilisk" but absent from baseline

These are facts about *this codebase* that appeared in the With-Basilisk response and not in the Baseline response. The baseline LLM had read access to the same code but did not surface these in 8 tool calls.

| finding | basilisk source |
|---|---|
| 13 strategies share a byte-identical `notify_trade` body (cluster `b2757f36`) | `pattern_clusters` |
| 11 strategies share an identical `log` body (cluster `ea69baa9`) | `pattern_clusters` |
| 10 strategies share a second `log` variant (cluster `67bd96bd`) | `pattern_clusters` |
| 8 strategies share an identical `stop` method (cluster `a0bd…`) | `pattern_clusters` |
| 5 strategies share an identical 83-node `notify_order` (cluster `4dc6…`) | `pattern_clusters` |
| 178 event-handler methods + 12 plugin points across the repo | `intervention` |
| `trade_list_analyzer.py:5,10,24,38` — the four highest-importer plugin points | `top_by_importer` |
| 40 of 41 files are `LOAD_BEARING` (98.5% of LOC); 1 test file (73 LOC) | `load_bearing` |
| Concrete refactor recommendation: extract a `BaseStrategy` mixin to absorb ~24+ duplicated methods | derived from `pattern_clusters` |

The cluster-level architectural insight — "13 of your strategies share byte-identical boilerplate methods, here's the refactor lever" — is the kind of finding a senior engineer might surface in week 2 or 3 of onboarding. Mode B' surfaced it in the first 76 seconds.

---

## Side-by-side response excerpts

A direct comparison of how each mode opens its architecture summary on the same prompt.

**Baseline (Mode A) — opening of architecture summary:**

> This is a small **Streamlit single-page app** that backtests stock-trading strategies against historical OHLCV data using the `backtrader` engine `[code:3]`. The full app lives in ~9 top-level Python files plus a `strategies/` directory containing 34 strategy implementations `[code:3]` (verified via directory listing).

**With Basilisk (Mode B') — opening of architecture summary:**

> This is a small Streamlit web app (41 Python files, 4,988 LOC) `[basilisk:3]` that runs financial trading backtests on top of the `backtrader` library. […] **Pattern-cluster signal (this is the load-bearing finding):** Basilisk reports 9 exact-AST clusters covering 60 method instances `[basilisk:3]`. The biggest:
> - 13 strategies share an identical `notify_trade` body (cluster `b2757f36`, avg 16 nodes) `[basilisk:3]`
> - 11 strategies share an identical `log` body (cluster `ea69baa9`, avg 19 nodes) `[basilisk:3]`
> - …
>
> That is heavy copy-paste boilerplate, not framework polymorphism. A senior should treat the strategies as a candidate for a `BaseStrategy` mixin extracting `log`, `notify_trade`, and `notify_order`.

Full responses: [`responses/baseline.md`](responses/baseline.md) — [`responses/with-basilisk.md`](responses/with-basilisk.md).

---

## Reproducibility

Everything required to rerun this comparison is in this repo.

1. Clone this repo
2. Install Basilisk (`pip install basilisk-toolkit` — or build from source)
3. Re-scan: `basilisk code-scan .` → outputs a fresh `scan_id`
4. Classify: `basilisk classify-intervention <scan_id> && basilisk classify-loadbearing <scan_id> && basilisk classify-patterns <scan_id>`
5. Regenerate artifacts: `basilisk export-facts <scan_id>` and `basilisk pack-coverage <scan_id>` → writes to `.basilisk/`
6. Run the [baseline prompt](prompts/baseline.md) against `claude-opus-4-7` with no Basilisk context, equipped with Read/Grep/Glob/Bash tools
7. Run the [with-Basilisk prompt](prompts/with-basilisk.md) against the same model/tools, with `.basilisk/structural-facts.yaml` and `.basilisk/pack-coverage.yaml` available

Same model + same prompt + same git commit will reproduce the receipts above modulo small token-counting variance.

---

## Files in this analysis

```
.basilisk/
├── structural-facts.yaml       # the YAML that Mode B' had in context
├── pack-coverage.yaml          # the pre-flight verdict on framework support
└── audit.yaml                   # README/doc-drift audit (0 findings on this repo)

basilisk-impact/
├── README.md                   # this file — the headline writeup
├── methodology.md              # rubric details, scoring caveats
├── prompts/
│   ├── baseline.md             # exact prompt used for Baseline
│   └── with-basilisk.md        # exact prompt used for With Basilisk
└── responses/
    ├── baseline.md             # full Baseline response (verbatim)
    └── with-basilisk.md        # full With-Basilisk response (verbatim)
```
