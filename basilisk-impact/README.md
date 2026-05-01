# Basilisk impact on Claude reasoning — this codebase

Same model. Same prompt. Same tools. Same git commit of this repo. Two configurations: with and without Basilisk in the workflow.

---

## Executive summary

Same `claude-opus-4-7` model, same prompt, same Read/Grep/Glob/Bash tools, same git commit of this repo — Claude run twice, once with Basilisk in context and once without.

**With Basilisk, Claude surfaced a concrete refactor lever in 76 seconds: 60+ method bodies are byte-identical duplicates across 34 strategy files, suggesting a `BaseStrategy` mixin extraction. Without Basilisk, given identical tools, Claude did not surface this finding.**

The cluster-duplication pattern is the kind of cross-file architectural debt a senior engineer typically surfaces in week 2 or 3 of onboarding. Here it appears as the opening of a first-response onboarding brief.

---

## The headline

In its first onboarding response, Claude **with Basilisk** produced this concrete architectural finding:

> *"9 exact-AST clusters cover 60 method instances across 34 strategies. 13 strategies share a byte-identical `notify_trade` body. 11 share an identical `log` method. 10 share a different `log` variant. 8 share an identical `stop`. 5 share a 83-node `notify_order`. That's heavy copy-paste boilerplate, not framework polymorphism. A senior should treat the strategies as a candidate for a `BaseStrategy` mixin extracting `log`, `notify_trade`, and `notify_order`."*

Claude **without Basilisk**, given the same prompt and the same Read/Grep/Glob/Bash tools against this codebase, did not surface this finding. The pattern is invisible from any single file — it requires AST-level clustering across all 34 strategies. LLMs do not run that clustering on their own; they rely on the calling workflow to provide it.

This is the kind of refactor lever a senior engineer might surface in week 2 or 3 of onboarding. **With Basilisk in context, it appeared in the first 76 seconds of Claude's first response.**

A side-by-side of the two responses is in [`responses/`](responses/). The full transcripts are unedited.

---

## What Claude saw with Basilisk that it didn't see without

The cluster duplication finding above is the headline. Other facts present in the With-Basilisk response and absent from Baseline:

| finding | basilisk source |
|---|---|
| 9 exact-AST clusters covering 60 method instances; specific cluster hashes and member counts | `pattern_clusters` |
| 178 event-handler methods + 12 plugin points across the repo | `intervention` |
| `trade_list_analyzer.py:5,10,24,38` — the four highest-importer plugin points (the contract the order-list tab depends on) | `top_by_importer` |
| 40 of 41 files are `LOAD_BEARING` (98.5% of LOC); only 1 test file (73 LOC) — refactoring this codebase has no safety net | `load_bearing` |
| Concrete `BaseStrategy` refactor recommendation absorbing 24+ duplicated methods | derived from `pattern_clusters` |

These are facts about *this codebase* that the LLM stated correctly because Basilisk had pre-computed the underlying analysis. The Baseline LLM, given codebase-reading tools, did not produce them — not because it lacked capability, but because surfacing them would require it to run AST clustering on 34 files, which it does not initiate without an explicit signal.

---

## Receipts: how Claude got there

| metric | Baseline | With Basilisk | what it means |
|---|---|---|---|
| Tool calls (Read/Grep/Glob/Bash) | 8 | **4** | Basilisk answered structural questions the baseline had to verify by reading files. **50% less codebase reading**. |
| Total tokens | 32,939 | 33,878 | Roughly equal. The Basilisk YAML adds ~1K input tokens; that overhead does not grow with codebase size. |
| Wall-clock duration | 75s | 76s | Equivalent. |
| `[code]`-only claims (cited from file reads, no other source) | 27 | **6** | **78% drop**. With Basilisk, Claude's structural claims come from the YAML or from cross-verified Basilisk + code, not from solo code reads. |
| `[basilisk]`-tagged claims | 0 | 19 | Facts only available because Basilisk pre-computed them. |
| Combined-source tags (e.g., `[basilisk + code]`) | 5 | 12 | Cross-verified claims more than doubled. |
| YAML-derived hard numbers in claims (counts, %, ratios) | 0 | 18 | Specific quantitative facts the baseline cannot match. |

**Both responses pass the standard 1-5 quality rubric at ceiling on all four dimensions** (specificity, grounding, actionability, calibration — see [`methodology.md`](methodology.md)). The 1-5 rubric is too coarse to differentiate at this codebase size. The decisive difference is *what the response contains*, not whether it passes a quality bar.

---

## Why the cluster-duplication insight matters commercially

You are buying Basilisk to **catch architectural debt earlier and act on it sooner**. On this 41-file codebase:

- The duplication is real (12+ exact-AST copies of `notify_trade`, etc. — verifiable by hand or by re-running the scan)
- Without Basilisk, an engineer onboarding to this codebase would likely take **2–3 weeks** to surface this pattern across 34 strategy files
- With Basilisk, it surfaces in **76 seconds, in the first response**, with a concrete refactor recommendation

On a larger Streamlit codebase (or any codebase with many siblings of similar shape), the same dynamic compounds: more clusters, more duplicated methods, more refactor levers, more weeks of senior-engineer time saved.

The receipts above are the credibility scaffolding showing *the result is real and reproducible*. The architectural insight itself is the product.

---

## Reproducibility

Everything required to rerun this comparison is in this repo.

1. Clone this repo
2. Install Basilisk
3. `basilisk code-scan .` (outputs a fresh `scan_id`)
4. `basilisk classify-intervention <scan_id> && basilisk classify-loadbearing <scan_id> && basilisk classify-patterns <scan_id>`
5. `basilisk export-facts <scan_id>` and `basilisk pack-coverage <scan_id>` (regenerates `.basilisk/`)
6. Run the [baseline prompt](prompts/baseline.md) against `claude-opus-4-7` — README + Read/Grep/Glob/Bash, no Basilisk context
7. Run the [with-Basilisk prompt](prompts/with-basilisk.md) against the same model + tools, with `.basilisk/structural-facts.yaml` and `.basilisk/pack-coverage.yaml` available

Same model + same prompt + same git commit will reproduce the receipts above modulo small token-counting variance.

---

## Files in this analysis

```
.basilisk/
├── structural-facts.yaml       # the YAML that With-Basilisk had in context
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

---

## Next-level questions a buyer typically asks

**"My codebase is bigger / different framework / different language. Will Basilisk find anything on it?"** — Yes for any Python/Java/Kotlin/TypeScript codebase. Run `basilisk pack-coverage <scan_id>` on a 5-minute scan of your repo; it returns a verdict (well-covered / partial / not-covered) plus the actual numbers (intervention surface, cluster count, load-bearing percentage). The cluster-level signal that drove the headline finding above works on any codebase regardless of framework support.

**"What if Basilisk doesn't yet support my framework?"** — The default analyzer pack ships with mainstream framework idioms (Django, FastAPI, Spring, Next.js, tRPC, plus the eight lines of backtrader support used here). Adding support for a new framework family is typically a 1-session change to a small pack file, reusable across every codebase in that niche.

**"How is this different from running a static-analysis linter?"** — Linters surface per-file rule violations. Basilisk surfaces *cross-file* structural patterns: which files import which others (fan-in/fan-out), which functions are byte-identical across the codebase (cluster signal), which classes are framework extension points, which files are load-bearing vs. test/fixture/vendor. The cluster-duplication finding above is not a lint rule — no linter would flag "13 strategies in this directory share an exact AST." It is a graph-level fact about the codebase.
