# psxdata-mcp

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants Pakistan Stock
Exchange data. It runs locally in Docker: the assistant loads PSX data (prices, screener,
index constituents, sectors, filings, debt market, margin-eligible scrips) into a private
in-memory DuckDB and answers your questions with SQL. It's built on
[psxdata](https://github.com/psxdata/psxdata).

**Requires:** [Docker](https://docs.docker.com/get-docker/).

## Install

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_psxdata-0098FF?logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=psxdata&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22-i%22%2C%22--rm%22%2C%22-v%22%2C%22psxdata-cache%3A%2Fhome%2Fapp%2F.psxdata%22%2C%22mtauha%2Fpsxdata-mcp%3Alatest%22%5D%7D)

**Claude Code** (plugin, recommended):

```bash
claude plugin marketplace add psxdata/psxdata-mcp
claude plugin install psxdata@psxdata-mcp
```

**Claude Code** (server only):

```bash
claude mcp add --transport stdio --scope user psxdata -- docker run -i --rm -v psxdata-cache:/home/app/.psxdata mtauha/psxdata-mcp:latest
```

**Cursor:** open this link:
`cursor://anysphere.cursor-deeplink/mcp/install?name=psxdata&config=eyJjb21tYW5kIjoiZG9ja2VyIiwiYXJncyI6WyJydW4iLCItaSIsIi0tcm0iLCItdiIsInBzeGRhdGEtY2FjaGU6L2hvbWUvYXBwLy5wc3hkYXRhIiwibXRhdWhhL3BzeGRhdGEtbWNwOmxhdGVzdCJdfQ==`

**Claude Desktop / any other client:** add to its MCP config (Claude Desktop:
`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "psxdata": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "psxdata-cache:/home/app/.psxdata", "mtauha/psxdata-mcp:latest"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `load_prices(symbols, start?, end?)` | Daily OHLCV for up to 50 symbols → `prices` |
| `load_screener()` | All ~729 symbols with price, P/E, dividend yield, market cap → `screener` |
| `load_index(name)` | Constituents and weights of KSE100, KSE30, KMI30, … → `index_constituents` |
| `load_sectors()` | 37-sector summary → `sectors` |
| `load_fundamentals(symbols?)` | Filed financial reports list → `fundamentals` |
| `load_symbols()` | All listed symbols with name and sector → `symbols` |
| `load_debt_market()` | TFCs, Sukuks, government securities → `debt_market` |
| `load_eligible_scrips()` | Margin-eligible scrips by market → `eligible_scrips` |
| `query(sql)` | DuckDB SQL over loaded tables (≤200 rows, 30 s, no file/network access) |
| `list_tables()` | What's loaded, row counts, load time |
| `quote(symbol)` | Latest snapshot for one symbol |

Ask things like *"How has OGDC done against KSE-100 constituents this year?"* or *"Which cement
stocks have a P/E under 6?"*

## Good to know

- Prices are PKR and **not adjusted** for splits, bonus issues or dividends.
- Historical data is cached in the `psxdata-cache` Docker volume, so each symbol is downloaded
  once. Live data (screener, sectors, quotes) refreshes every 15 minutes.
- Loaded tables live in memory and reset when the assistant session ends.
- Data is scraped from the public PSX website; it isn't an official feed.

## Development

```bash
uv sync
uv run pytest                    # unit + server tests
uv run pytest -m live            # hits real PSX
docker build -t psxdata-mcp:dev . && uv run pytest -m container
npx @modelcontextprotocol/inspector docker run -i --rm psxdata-mcp:dev
```

## License

MIT
