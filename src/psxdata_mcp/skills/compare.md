---
name: compare
title: Compare stocks
description: Side-by-side comparison of 2–10 PSX stocks over a period — returns, risk, correlation, valuation and a rebased price path, optionally against the KSE-100. Use when asked to compare PSX stocks, pick between them, or see how they moved together.
argument: symbols | required | 2–10 PSX tickers, comma-separated, e.g. OGDC, PPL, MARI
argument: period | optional | look-back such as 3M, 6M, 1Y (default), 3Y or YTD
task: Compare these PSX stocks: {symbols}. Period: {period}
---
# Compare stocks

Compare 2–10 PSX stocks over one period. Follow the PSX playbook for data traps and SQL
patterns.

## Steps

1. **Inputs.** Split `symbols` on commas or spaces and uppercase them. Fewer than 2 → ask for
   more. More than 10 → ask the user to trim, or offer the `screen` skill. Period defaults to 1Y.
2. **Snapshot.** Call `load_screener()` and `load_symbols()` and build the playbook's `universe`
   view. Report any ticker that isn't found and continue with the rest. Note any `NC`, `XD` or
   `XB` status.
3. **Prices.** Call `load_prices(<base symbols>, start=<period start minus 2 weeks>)`.
   - Hosted (`load_mart` exists): also load `fact_index_ohlcv` for the period, and
     `fact_ticker_relationships` for the KSE-100 names.
   - Local: there is no index series. Say the comparison is between the stocks only.
4. **Corporate actions.** Run the playbook's gap check for every symbol. Adjust confirmed
   actions in a view before computing anything.
5. **Common window.** Compare over dates where every stock traded, so that one late listing or
   a suspension doesn't skew the numbers:

   ```sql
   CREATE OR REPLACE VIEW cmp AS
   WITH p AS (
     SELECT symbol, date, close FROM prices
     WHERE symbol IN (...) AND NOT is_anomaly AND date >= <period start>
   ), common AS (
     SELECT date FROM p GROUP BY date HAVING count(DISTINCT symbol) = <n>
   )
   SELECT symbol, date, close,
          ln(close / lag(close) OVER (PARTITION BY symbol ORDER BY date)) AS lr
   FROM p JOIN common USING (date)
   ```

   Hosted: `UNION ALL` the KSE-100 from `fact_index_ohlcv` as symbol `'KSE100'` so it shows up
   in every table below. If the common window is much shorter than the period, say why (which
   stock is missing data).
6. **Metrics per stock.** Total return, annualised volatility, max drawdown, and return per
   unit of volatility. Use the playbook patterns, grouped by `symbol` over `cmp`. Hosted: add
   beta vs. KSE-100 from `fact_ticker_relationships`.
7. **Correlation.** Pairwise correlation of daily log returns:

   ```sql
   SELECT a.symbol, b.symbol AS other, round(corr(a.lr, b.lr), 2) AS corr
   FROM cmp a JOIN cmp b ON a.date = b.date AND a.symbol < b.symbol
   GROUP BY ALL ORDER BY corr DESC
   ```

8. **Price path.** Month-end levels rebased to 100 at the start, one column per stock:

   ```sql
   WITH b AS (
     SELECT symbol, date,
            100 * close / first_value(close) OVER (PARTITION BY symbol ORDER BY date) AS idx
     FROM cmp
   )
   PIVOT (SELECT symbol, date_trunc('month', date)::DATE AS month,
                 round(arg_max(idx, date), 1) AS idx FROM b GROUP BY ALL)
   ON symbol USING first(idx) ORDER BY month
   ```

   Use weekly points for 3M or less. If you can draw charts, plot this table as lines.
9. **Valuation.** From `universe`: price, P/E vs. sector median, dividend yield, 30-day traded
   value, and sector.
10. **Context (web, if available).** For each stock, the one news item or corporate action that
    best explains its move in the period, with source and date. When the stocks share a sector,
    add one line on the sector driver (oil prices, interest rates, cement demand and so on).

## Output

```
## <SYM1> vs <SYM2> vs … · <period> (<first date> → <last date>, <n> common trading days)

**Bottom line:** 2–3 sentences: who led, at what risk, how closely they moved, which looks
cheaper.

| Symbol | Return % | Volatility % | Max drawdown % | Return/vol | Beta | P/E | Sector P/E | Yield % | Traded PKR m/day |

**Correlation:** the pairs table, or a matrix if 4 or fewer stocks.
**Price path (rebased to 100):** the month-end table, or a chart.
**What explains the gap:** one bullet per stock, citing sources.
**Caveats:** adjustments made, missing data, the common-window effect.
Data: PSX via psxdata. Not investment advice.
```
