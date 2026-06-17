# Basilisk review — simple version

## What we did

We ran your code through our tool, **Basilisk**. It makes a map of the code:
which files use which, which classes are related, and how things connect.
Then an AI read your code using that map. The AI started **cold** — it did not
know the code before, and nobody told it what to look for.

## Please read this first

These are **maybe-problems**, not proven bugs. We do **not** know why each one
is there. Maybe it is a real bug. Maybe it is old code. Maybe it is on purpose.
We just looked with fresh eyes and these places made us stop and think.

If you already know about one, or it is on purpose — just ignore it.
If any are new to you — good, then the review helped.

**When:** we looked on 2026-06-17. The code was at commit `6185549`. The line
numbers are from that commit. The code may have changed since — please check
the lines against your current code before you do anything.

---

## Most sure

**1. The stop-loss is about 100× too small when you run from the app.**
Files: `strategies/ADX_ADXR_BBPct_Strategy.py` lines 65, 69
(same problem in `strategies/ADX_AO_BBPct_Strategy.py` lines 50, 54).
The app already turns "2%" into `0.02`. But the strategy divides by 100 **again**.
So the stop becomes about `0.02%` — tiny. Normal price movement will hit it at
once. (If you run it without the app, the default value happens to work — so the
two ways of running it do not agree.)

**2. Short trades will almost never happen.**
File: `strategies/ADX_AO_BBPct_Strategy.py` lines 91–92.
To **buy** (long), it needs a strong trend (`adx > 25`).
To **sell** (short), it needs an almost flat market (`adx < 10`).
The sister strategy uses `> 25` for both. So shorts will almost never start.
Maybe the short rule is backwards.

**3. The machine-learning model may "see the future".**
File: `strategies/DecisionTree_EMA_Crossover_MLStrategy.py` lines 49–50.
The training data moves the answer one step ahead of the inputs
(`X_train = X[:-1]`, `y_train = y[1:]`). So the model learns from the price move
that comes **after** the one it should predict. This makes results look too good.

**4. Closed trades save the wrong exit price.**
File: `trade_list_analyzer.py` lines 15–16.
Both `entry_price` and `exit_price` are set to `trade.price` (the entry price).
The exit should be `trade.priceexit`. So every trade shows the same entry and
exit, and any profit/loss from this list is wrong.

**5. One strategy uses a variable that does not exist.**
File: `strategies/MACDStrategy.py` line 39.
`next()` reads `self.data_close`, but it is never created — the code makes
`self.data.close` instead. So this will **crash** on the first bar
(`AttributeError`). Everywhere else in the file uses `self.data.close`.

**6. A filter may allow exactly what it wants to block.**
File: `strategies/rsi_mean_reversion_filtered.py` lines 82–85.
The "skip trading" rule uses `trend_confirmed AND volatile_enough`. So it can
still trade in a strong but calm trend — maybe the opposite of the goal. Also,
this early `return` is before the code that closes a position.

## Less sure — please look

**7. The entry filter may be reversed.**
File: `strategies/HilbertRsiStrategy.py` around line 158.
The filter seems to allow trades only in calm, no-trend times. This may be
backwards. Our two passes did not agree here — so maybe it is on purpose.

**8. The app default is different from the strategy default.**
File: `strategies/MACDStrategy.py` line 11 vs line 20.
The take-profit in the app is `5%`, but the strategy's own default is `10%`
(and the comment says "10%"). So the strategy works differently depending on
how you start it.

---

## How we found them

Most of these are **logic** problems — a reversed rule, a too-small stop,
seeing the future. A map of the code cannot see these directly; we found them by
**reading**. But the map helped a lot: it put **all the strategies side by side**,
so we could compare them. Many problems are "this one is different from its
brothers":
- the short rule that disagrees with its own long rule and with its sister (#2),
- the stop pattern shared with a twin (#1),
- the strategy that uses a variable the others set (#5).

The map told us **where** to look. Reading told us **why**.

We are happy to look deeper at any one item, or at parts we did not mention.
