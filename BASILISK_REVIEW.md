# Basilisk review — suspected issues in ST

## What this is

We ran this codebase through **Basilisk**, our toolkit that builds a deterministic structural map of
a project — module dependencies, class/type hierarchies, the call graph, and change history — and
hands that map to an LLM so the model's analysis stays grounded in the actual code rather than its
general priors. An LLM then reviewed ST using that map, **cold**: with no prior knowledge of the code
and nothing told to it about what, or whether, to look for.

## What this is *not* — please read first

These are **suspected** issues, at the confidence levels noted — not verified defects. We make **no
claim about why** any of them is the way it is: we can't tell whether a given item is a genuine bug,
a scar from a real codebase's evolution, or something intentional. We simply looked, with fresh eyes,
and these are the places that gave a careful, structurally-grounded reviewer pause. If an item is
intentional or already known, ignore it; if any are news, we're glad the review surfaced them.

**Provenance.** Reviewed 2026-06-17 (UTC) against commit `6185549`
(`618554960262735211d8c44db86f5feefd020c74`) of `github.com/dpodbori/ST`, using Basilisk + an LLM
(`claude-sonnet-4-6`). Line numbers are **as of that commit**; this is a point-in-time review and the
code may have evolved since — re-check the references against the current source before acting.

---

## High confidence

**1. Stop-loss is ~100× too tight when run from the UI** — `strategies/ADX_ADXR_BBPct_Strategy.py:65,69`
(and the near-identical `strategies/ADX_AO_BBPct_Strategy.py:50,54`).
The Streamlit input already converts the percentage to a fraction (`value=2.0 … / 100` → `0.02`), but
the strategy divides by 100 *again* (`self.p.stop_loss_pct / 100.0`). The effective stop ends up ~0.02%
from entry and would be hit by ordinary noise. (Run headless with the class default `2.0` it happens to
work — the two execution paths disagree.)

**2. Short-entry trend condition looks inverted** — `strategies/ADX_AO_BBPct_Strategy.py:91-92`.
The long entry requires a strong trend (`adx_val > 25`); the short entry requires a near-flat market
(`adx_val < 10`). The sibling `ADX_ADXR_BBPct_Strategy.py` uses `> 25` for both directions. As written,
shorts would essentially never fire.

**3. Possible look-ahead bias in the ML training labels** — `strategies/DecisionTree_EMA_Crossover_MLStrategy.py:49-50`.
`X_train = X[:-1]` paired with `y_train = y[1:]` shifts each training label one bar ahead of its
features (the in-line comment even says "shifted by one"), so the model is fit against the price move
that comes *after* the one it should be predicting.

**4. Closed-trade records store the entry price as the exit price** — `trade_list_analyzer.py:15-16`.
Both `entry_price` and `exit_price` are set to `trade.price` (the entry). The exit should be
`trade.priceexit`; as is, every closed trade shows identical entry/exit and any P&L derived from the
list is wrong.

**5. A strategy uses an attribute it never defines** — `strategies/MACDStrategy.py:39`.
`next()` reads `self.data_close[0]`, but `__init__` only assigns `self.data.close` (line 26) —
`self.data_close` is never set, so this raises `AttributeError` on the first bar. Every other reference
in the file uses `self.data.close`.

**6. A mean-reversion filter may admit the regime it's meant to skip** — `strategies/rsi_mean_reversion_filtered.py:82-85`.
The guard that skips trading uses `trend_confirmed AND volatile_enough`, so it can still enter in a
strong-but-quiet trend — arguably the opposite of the stated intent — and the same early `return` sits
ahead of the position-exit logic.

## Medium confidence / worth a look

**7. Entry filter may be backwards** — `strategies/HilbertRsiStrategy.py:~158`.
The entry filter appears to permit trades only in quiet, trendless conditions, which may invert the
intended confirmation. Our two review passes disagreed on this one, so it may well be deliberate.

**8. UI default differs from the strategy's own default** — `strategies/MACDStrategy.py:11` vs `:20`.
The take-profit shown in the UI defaults to 5% while the strategy's class default is 10% (and the
line-11 comment reads "10%"). The same strategy behaves differently depending on how it's launched.

---

## How we found them

Most of these are *logic* issues — look-ahead bias, an inverted condition, a too-tight stop — which a
structural map can't see directly; those came from careful reading. What the map contributed was
**orientation**: because it enumerates the whole strategy family, several catches were *sibling
comparisons* — the one short-entry condition that disagrees with its own long entry and with its
sibling strategy (#2), the stop-loss pattern shared by a twin strategy (#1), the one strategy that
references an attribute the rest of the family's pattern sets (#5). The map told the reviewer where the
outliers were; reading confirmed why.

We're happy to go deeper on any single item, or to look at areas we didn't call out.
