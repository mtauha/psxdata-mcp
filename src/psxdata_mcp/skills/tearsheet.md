---
name: tearsheet
title: Stock tearsheet
description: One-page report on a single PSX stock — price performance, risk, valuation against sector peers, recent filings and news. Use when asked to analyse, review or summarise one PSX-listed company.
argument: symbol | required | PSX ticker, e.g. OGDC
task: Build a tearsheet for {symbol}.
---
# Stock tearsheet

Produce a one-page tearsheet for one PSX stock. Follow the PSX playbook for data traps and SQL
patterns.

## Steps

1. **Snapshot.** Call `quote(symbol)`. If the symbol is unknown, stop and suggest close matches
   from `load_symbols()`.
2. **Peers.** Call `load_screener()` and `load_symbols()` so the stock can be compared with its
   sector.
3. **Prices.** Call `load_prices([symbol], start=<about 13 months ago>)`.
   - If `load_mart` exists (hosted server) and the stock is a KSE-100 name, also load for the
     same window: `fact_index_ohlcv` (benchmark), `fact_technical_indicators`,
     `fact_ticker_relationships` and `fact_valuation_daily`, filtered to the symbol.
4. **Corporate actions.** Run the playbook's gap check over the window. Confirm flagged dates
   on the web if you can and adjust, or keep raw prices and add a caveat.
5. **Performance and risk.** In SQL: last close and its date; returns over 1M, 3M, 6M, YTD
   and 1Y; 52-week high and low and the distance from each; max drawdown over 1Y; annualised
   volatility; average daily traded value (close × volume) over 30 days in PKR millions.
   - Hosted: add relative return vs. KSE-100 over the same horizons, plus beta and correlation
     from `fact_ticker_relationships`. Cross-check your numbers against
     `fact_technical_indicators`.
   - Local: compare 1Y return with the median `change_1y_pct` of sector peers instead.
6. **Valuation.** From `screener`: P/E and dividend yield vs. sector medians (zeros as NULL,
   outliers dropped), and the stock's rank within the sector. Hosted: add where today's P/E
   sits in its own one-year range from `fact_valuation_daily`.
7. **Filings.** Call `load_fundamentals([symbol])` and list the latest 4 reports (type, period,
   posting date, link).
8. **Context (web, if available).** Find dividends declared in the last 12 months, any
   corporate actions, and the 2–3 most important news items from the last 90 days. Add one
   macro line (SBP policy rate vs. the dividend yield). Cite each item with source and date.

## Output

```
## <SYMBOL> — <Company name>  ·  <sector>
<price> PKR (<day change>%) · as of <date> · index memberships: <listed_in>

**Bottom line:** 2–3 sentences: trend, valuation vs. sector, the one thing to watch.

| Performance | 1M | 3M | 6M | YTD | 1Y |
| <SYMBOL>    |    |    |    |     |    |
| KSE-100 / sector median | … |

| Risk | 52w high / low | From high | Max drawdown 1Y | Volatility (ann.) | Beta | Avg traded value 30d |

| Valuation | <SYMBOL> | Sector median | Rank in sector |
| P/E | … |
| Dividend yield | … |

**Recent filings:** bullet list with links.
**News and corporate actions:** bullets, each with source and date.
**Caveats:** unadjusted prices or adjustments made, missing data, snapshot times.
Data: PSX via psxdata. Not investment advice.
```

Leave out rows you couldn't compute rather than filling them with guesses, and say why.
