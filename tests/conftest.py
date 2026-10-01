import pandas as pd
import psxdata
import pytest
from psxdata.exceptions import PSXConnectionError

SYMBOLS = ["OGDC", "PPL", "DOWN", "EMPTY", "LATER"]


def prices_frame(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 100,
            "is_anomaly": False,
        }
    )


SCREENER = pd.DataFrame(
    {
        "symbol": ["OGDC", "PPL"],
        "sector": ["OIL", "OIL"],
        "listed_in": ["KSE100", "KSE100"],
        "market_cap": [1e9, 2e9],
        "price": [200.0, 150.0],
        "pe_ratio": [5.1, 4.2],
        "dividend_yield": [8.0, None],
        "free_float": [0.3, 0.2],
        "volume_avg_30d": [1e6, 2e6],
        "change_1y_pct": [40.0, 30.0],
    }
)


@pytest.fixture
def fake_psx(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {"stocks": []}

    def stocks(symbol: str, start=None, end=None, cache=True):  # type: ignore[no-untyped-def]
        calls["stocks"].append(symbol)
        if symbol == "DOWN":
            raise PSXConnectionError("connection refused")
        if symbol == "EMPTY":
            return pd.DataFrame()
        return prices_frame()

    def indices(name: str, cache=True):  # type: ignore[no-untyped-def]
        base = {
            "symbol": ["OGDC", "PPL"],
            "current_index": [1.0, 2.0],
            "idx_weight": [10.0, 5.0],
            "idx_point": [100.0, 50.0],
            "market_cap_m": [1000.0, 500.0],
        }
        if name == "KSE100":
            return pd.DataFrame({**base, "freefloat_m": [300.0, 100.0]})
        return pd.DataFrame({**base, "shares_m": [12.5, 7.25]})

    debt = {
        f"table_{i}": pd.DataFrame(
            {
                "security_code": [f"C{i}"],
                "security_name": [f"Bond {i}"],
                "maturity_date": [pd.Timestamp("2027-02-08")],
                "coupon_rate": [0.1],
            }
        )
        for i in range(4)
    }
    eligible = {
        f"table_{i}": pd.DataFrame({"symbol": [f"S{i}"], "name": [f"Name {i}"]}) for i in range(9)
    }
    symbols = pd.DataFrame(
        {
            "symbol": SYMBOLS,
            "name": [f"{s} Ltd" for s in SYMBOLS],
            "sector_name": ["OIL"] * len(SYMBOLS),
            "is_etf": False,
            "is_debt": False,
            "is_gem": False,
        }
    )
    fundamentals = pd.DataFrame(
        {
            "symbol": ["OGDC", "PPL"],
            "year": [2025, 2025],
            "type": ["Annual", "Quarterly"],
            "period_ended": [pd.Timestamp("2025-06-30"), pd.Timestamp("2025-09-30")],
            "posting_date": [pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-20")],
            "posting_time": ["10:00", "11:00"],
            "document": ["a.pdf", "b.pdf"],
        }
    )
    sectors = pd.DataFrame(
        {
            "sector_code": ["0801"],
            "sector_name": ["OIL"],
            "advance": [3],
            "decline": [1],
            "unchanged": [0],
            "turnover": [1e6],
            "market_cap_b": [900.0],
        }
    )

    def quote(symbol: str, cache=True):  # type: ignore[no-untyped-def]
        return SCREENER[SCREENER["symbol"] == symbol.upper()].reset_index(drop=True)

    monkeypatch.setattr(psxdata, "stocks", stocks)
    monkeypatch.setattr(psxdata, "indices", indices)
    monkeypatch.setattr(psxdata, "screener", lambda cache=True: SCREENER.copy())
    monkeypatch.setattr(psxdata, "sectors", lambda cache=True: sectors.copy())
    monkeypatch.setattr(psxdata, "symbols", lambda cache=True: symbols.copy())
    monkeypatch.setattr(
        psxdata, "fundamentals", lambda symbol=None, cache=True: fundamentals.copy()
    )
    monkeypatch.setattr(
        psxdata, "debt_market", lambda cache=True: {k: v.copy() for k, v in debt.items()}
    )
    monkeypatch.setattr(
        psxdata, "eligible_scrips", lambda cache=True: {k: v.copy() for k, v in eligible.items()}
    )
    monkeypatch.setattr(psxdata, "quote", quote)
    return calls
