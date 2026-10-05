---
name: market-wrap
title: Market wrap
description: Daily or weekly summary of the Pakistan Stock Exchange — KSE-100 move and the stocks driving it, breadth, sector performance, top movers, turnover and the news behind it. Use when asked how the PSX or KSE-100 did today or this week, or for a market summary.
argument: period | optional | today (default) or week
task: Write a PSX market wrap. Period: {period}
---
# Market wrap

Summarise the PSX session (`today`, the default) or the last 5 trading days (`week`). Follow
the PSX playbook for data traps and SQL patterns.

## Daily wrap

1. **Load.** Call `load_screener()`, `load_symbols()`, `load_sectors()` and
   `load_index("KSE100")`, and build the playbook's `universe` view. Quote the screener load
   time; if PSX is still trading, call it an intraday wrap.
2. **Index move.** `index_constituents.idx_point` is each constituent's contribution to the
   day's KSE-100 move in points. `sum(idx_point)` is the index's point change. Show the 5 biggest
   positive and the 5 biggest negative contributors (symbol, points, % change, joining
   `screener` on `symbol`). Hosted: take the index level and % change from `fact_index_ohlcv`,
   but only if its latest date is today (see the playbook's freshness rule).
3. **Breadth.** Advancers, decliners and unchanged across the market (`sectors` totals), and
   within KSE-100 (the sign of `idx_point`). Note how lopsided the day was.
4. **Sectors.** Per sector: advancers vs. decliners, the median `change_pct` of liquid names
   (`traded_pkr_m >= 10`), and turnover. List the 3 best and 3 worst sectors by median change,
   among sectors with at least 3 liquid names.
5. **Movers.** Top 5 gainers and losers by `change_pct` among liquid names, and the 5 most
   traded by value. Mark `XD` / `XB` names: their drop is the dividend or bonus, not selling.
6. **Context (web, if available).** Search for today's PSX market report (Business Recorder,
   Dawn, brokerage notes) for the 2–3 drivers: policy and SBP news, results, IMF or budget news,
   oil and PKR moves, foreign flows. Cite each with source and date. If the web reason
   conflicts with the data (e.g. "banks led" but banks fell), trust the data and say so.

## Weekly wrap

Same structure over the last 5 trading days:

- **Hosted:** load `fact_technical_indicators` for the latest date. Use `trailing_return_5d`
  per stock, and weight it by `index_constituents.idx_weight` to estimate the KSE-100's weekly
  move:

  ```sql
  SELECT 100 * sum(i.idx_weight * t.trailing_return_5d) / sum(i.idx_weight) AS kse100_5d_pct,
         sum(i.idx_weight) FILTER (t.symbol IS NOT NULL) AS weight_covered
  FROM index_constituents i
  LEFT JOIN t ON t.symbol = regexp_replace(i.symbol, '(XD|XB|XR|XA|NC)+$', '')
  WHERE i.index_name = 'KSE100'
  ```

  (`t` = the latest day's `fact_technical_indicators` rows.) Report the weight covered; the
  warehouse does not hold every constituent. Use `fact_index_ohlcv` instead if it is current.
  Sector breadth by day comes from `fact_sector_daily`. Mention any `ma_crossover_event`
  (golden or death cross) of the week.
- **Local:** load prices for the 50 largest KSE-100 constituents by `idx_weight` (about 90% of
  the index), starting 3 weeks back. Compute each stock's 5-trading-day return and the
  weight-weighted estimate as above, and say it is an estimate from 50 stocks.
- Run the playbook's corporate-action check on the top and bottom movers before naming them.
- Web: the week's 3–4 main drivers and the coming week's scheduled events (SBP policy
  meeting, CPI release, results due), with sources.

## Output

```
## PSX <daily|weekly> wrap · <date or date range> (<as-of time>)

**KSE-100: <±points> (<±%>)** · breadth <adv>/<dec> · turnover PKR <x> bn

**Story of the <day|week>:** 2–3 sentences on what drove it, with sources.

| Index movers (+) | pts | % |    | Index movers (−) | pts | % |

| Sector | Adv/Dec | Median % | Turnover |   (best 3, worst 3)

| Top gainers | % |   | Top losers | % |   | Most traded | PKR m |

**Next:** scheduled events (weekly wrap, or the daily wrap when known).
**Caveats:** snapshot time, estimates, stale marts, XD/XB effects.
Data: PSX via psxdata. Not investment advice.
```
