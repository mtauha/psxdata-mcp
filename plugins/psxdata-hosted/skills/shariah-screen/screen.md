# Stock screen

Shortlist PSX stocks that match a preset or the user's own conditions. Follow the PSX playbook
for data traps and SQL patterns.

## 1. Pick the screen

- `value`, `dividend` or `momentum` → use the preset below.
- Anything else → a custom screen (section 4).
- Empty → ask the user to choose a preset or describe their conditions, then continue.

The user may combine a preset with extra conditions ("dividend, cement only", "value in
KMI30"). Apply both.

## 2. Build the universe

Call `load_screener()` and `load_symbols()`, then create the playbook's `universe` view
(the suffix-tolerant join with sector medians). Every query below reads from it.

**Liquidity floor:** keep `traded_pkr_m >= 10` (PKR 10 million a day, about 200 stocks)
unless the user sets another. Illiquid names otherwise flood every screen.

## 3. Presets

**Value.** `pe < 0.75 * sector_pe` in sectors with `n_pe >= 3`, ranked by `pe / sector_pe`.
P/E levels differ a lot between sectors (banks trade far below tech), so compare against the
sector, not one cut-off.

**Dividend.** `dy >= 8` and `pe IS NOT NULL` (profitable, so the payout is more likely to
last), ranked by `dy`. If you can search the web, use the current SBP policy rate as the cut-off
instead of 8 and say so: a yield above the risk-free rate is the useful comparison.

**Momentum.**
- Hosted (`load_mart` exists): load `fact_cross_sectional_rankings` for the latest few days.
  Keep the latest `date` with `momentum_63d_quintile = 1` and `relative_strength_63d_quintile
  = 1`, ranked by `relative_strength_63d`. This covers KSE-100 names only; say so.
- Local: take the top 25 liquid names by `chg_1y`, then call `load_prices` for their `base_symbol`s from about
  4 months ago. Keep names whose 3-month return is also positive, ranked by 3-month return.
  Run the playbook's corporate-action check on the finalists: a bonus or split drop can hide a
  winner, and a missed one can fake a loser.

## 4. Custom screens

1. Map each condition to a column: P/E → `pe`, yield → `dy`, sector → `sector` (match
   case-insensitively with ILIKE, then list the sector names that matched: `%BANK%` also
   catches investment banks), index → `list_contains(string_split(listed_in, ','), '<INDEX>')`,
   Shariah-compliant → index `KMIALLSHR`, 1-year return → `chg_1y`, liquidity → `traded_pkr_m`,
   price → `price`.
2. Before running, state your reading in one line, e.g.
   "Reading this as: sector ILIKE '%BANK%', pe < 6, traded ≥ PKR 10m/day".
3. If a condition isn't in the data (ROE, debt/equity, EPS growth, margins), say so. Screen on
   what exists, and for at most 10 finalists check the missing metric on the web if you can,
   citing each figure.
4. For conditions on price history (drawdown, volatility, moving averages), screen on the
   snapshot first, then load prices for at most 50 finalists. Hosted: use
   `fact_technical_indicators` for KSE-100 names.

## 5. Red flags

Add a `flags` column to every result row:
- `P/E<3`: often a one-off gain or stale earnings; check before trusting.
- `1Y<-50%`: possible distress, or an unadjusted bonus or split.
- `yield>15%`: probably a special dividend or a price collapse.
- `no P/E`: loss-making or missing data.
- `NC`: the ticker carries the non-compliant suffix (`status` contains `NC`).
- `ex-div` / `ex-bonus`: `status` is `XD` / `XB`; the price just dropped by the payout, so
  yield and 1Y return are distorted.

If you can search the web, check recent news for the top 5 names, and add a flag for anything
material (losses, regulatory action, default, delisting notice), citing the source.

## Output

```
**<Screen name>**: <N> of <universe size> liquid stocks match · screener as of <time>
Criteria: <one line>

| # | Symbol | Name | Sector | Price | P/E | Sector P/E | Yield % | 1Y % | Traded PKR m/day | Flags |

**What stands out:** 2–3 bullets (sector clustering, the strongest names, common flags).
**Caveats:** liquidity floor used, data gaps, unadjusted returns.
Data: PSX via psxdata. Not investment advice.
```

Show at most 15 rows; if more match, say how many and offer to narrow down. If nothing
matches, say which condition removed the most names and suggest loosening it.
