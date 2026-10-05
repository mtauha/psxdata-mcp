---
name: shariah-screen
title: Shariah-compliant screen
description: Find Shariah-compliant PSX stocks (KMI All-Share Islamic Index members) on their own or combined with a value, dividend, momentum or custom screen, with purification and recomposition caveats. Use when asked for halal, Islamic or Shariah-compliant PSX stocks.
argument: screen | optional | value, dividend, momentum, or your own conditions; empty for an overview
task: Run a Shariah-compliant PSX screen. Screen: {screen}
includes: screen
---
# Shariah-compliant screen

Restrict the stock screen to Shariah-compliant names, then run it. Follow the PSX playbook for
data traps and SQL patterns, and the stock screen for the screen itself.

## 1. Compliant universe

Build the playbook's `universe` view, then keep members of the **KMI All-Share Islamic Index**
(`KMIALLSHR`, about 300 stocks):

```sql
WHERE list_contains(string_split(listed_in, ','), 'KMIALLSHR')
```

If the user asks for something stricter, use `KMI30` (the 30 largest and most liquid compliant
names) or `MII30` instead, and say which index you used. `listed_in` uses the screener's
suffixed tickers, so the suffix-tolerant join from the playbook is required. Without it,
compliant names trading ex-dividend (`LUCKXD`) disappear.

To check membership against the source, call `load_index("KMIALLSHR")` and compare with
`index_constituents` on `symbol`. The counts should match.

## 2. Run the screen

- Screen given (`value`, `dividend`, `momentum` or conditions): run the stock screen exactly as
  described, on the compliant universe. Apply the same liquidity floor and red flags.
- Empty: give an overview instead. Show the number of compliant stocks (all and liquid), then a
  table by sector (count, median P/E, median yield, total traded value), and the 10 most
  liquid compliant names. End by offering the three presets.

## 3. Shariah caveats

- **Membership is a snapshot.** The KMI indices are recomposed periodically, using screening
  of each company's latest financial statements. A company can stop qualifying between
  reviews. If you can search the web, check the latest KMI recomposition or the published list
  of compliant stocks for each finalist, and flag any that changed.
- **The screening criteria**, for context: the core business must be permissible;
  interest-bearing debt below 37% of total assets; non-compliant investments below 33% of total
  assets; non-compliant income below 5% of revenue; illiquid assets at least 25% of total
  assets; and share price at least net liquid assets per share. If the user asks why a stock is
  or isn't compliant, explain with these, and don't recompute them: the data here has no balance
  sheets.
- **Dividend purification.** Compliant companies can still earn a small non-compliant income,
  and investors give away that share of dividends. For dividend screens, if you can search the
  web, find the latest published purification ratio for each finalist and cite it. Otherwise
  mention that purification may apply.
- **This is index membership, not a religious ruling.** Say so once, and suggest the user
  consult a qualified Shariah scholar or advisor for personal decisions.

## Output

Use the stock screen's output, with the title "Shariah-compliant <screen>", and add an
`Index` column (KMI30 / KMIALLSHR) and a short "Shariah notes" section covering the caveats
that apply.
