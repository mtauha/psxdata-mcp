"""Fetch PSX datasets through the psxdata SDK and normalize them into flat DataFrames."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd
import psxdata
from psxdata.exceptions import PSXDataError, PSXRateLimitError, PSXUnavailableError

INDEX_COLUMNS: tuple[str, ...] = (
    "index_name",
    "symbol",
    "current_index",
    "idx_weight",
    "idx_point",
    "market_cap_m",
    "freefloat_m",
    "shares_m",
)

# Order of the <h2> headings on /eligible-scrips, matching the SDK's table_0..table_8.
ELIGIBLE_CATEGORIES: tuple[str, ...] = (
    "Regular Deliverable Equity Market",
    "Future Deliverable Contract Market",
    "Initial Public Offering Market",
    "Cash Settled Future Contract Market",
    "Stock Index Future Contract Market",
    "Bills and Bond Market",
    "Negotiated Deal Market",
    "Odd Lot Market",
    "Square-Up (Buy-In) Market",
)

# Order of the 4 tables on /debt-market, matching the SDK's table_0..table_3.
DEBT_CATEGORIES: tuple[str, ...] = (
    "GoP Ijarah Sukuk",
    "Public Debt Securities",
    "Privately Debt Securities",
    "Government Debt Securities",
)


@dataclass
class LoadResult:
    df: pd.DataFrame
    failures: dict[str, str] = field(default_factory=dict)


def snake(name: object) -> str:
    text = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()
    return text or "col"


def _as_date(value: object) -> object:
    # pd.NaT is an instance of datetime, so missing values must be checked first.
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return None if pd.isna(value) else value  # type: ignore[call-overload]


def _is_datetime_column(col: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(col):
        return True
    if col.dtype != object:
        return False
    values = col.dropna()
    return not values.empty and all(isinstance(v, dt.datetime) for v in values)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [snake(c) for c in out.columns]
    for name in out.columns:
        if _is_datetime_column(out[name]):
            out[name] = pd.Series([_as_date(v) for v in out[name]], index=out.index, dtype=object)
    return out


def _reason(exc: PSXDataError) -> str:
    if isinstance(exc, PSXUnavailableError):
        return "PSX unreachable"
    if isinstance(exc, PSXRateLimitError):
        return "rate-limited by PSX"
    return f"{type(exc).__name__}: {exc}"


def known_symbols() -> frozenset[str]:
    df = psxdata.symbols()
    if "symbol" not in df.columns:
        return frozenset()
    return frozenset(df["symbol"].astype(str).str.upper())


def load_prices(symbols: list[str], start: dt.date | None, end: dt.date | None) -> LoadResult:
    frames: list[pd.DataFrame] = []
    failures: dict[str, str] = {}
    for i, sym in enumerate(symbols):
        try:
            df = psxdata.stocks(sym, start=start, end=end)
        except PSXDataError as exc:
            failures[sym] = _reason(exc)
            if isinstance(exc, PSXUnavailableError):
                for rest in symbols[i + 1 :]:
                    failures[rest] = "skipped — PSX unreachable"
                break
            continue
        if df.empty:
            failures[sym] = "no data in range"
            continue
        df = normalize(df)
        df.insert(0, "symbol", sym)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return LoadResult(out, failures)


def load_screener() -> pd.DataFrame:
    return normalize(psxdata.screener())


def load_sectors() -> pd.DataFrame:
    return normalize(psxdata.sectors())


def load_symbols() -> pd.DataFrame:
    return normalize(psxdata.symbols())


# PSX appends status suffixes to a ticker while they apply: XD ex-dividend, XB ex-bonus,
# XR ex-rights, XA ex-all, NC non-compliant with listing rules. The screener lists LUCKXD, not LUCK.
STATUS_SUFFIX = re.compile(r"(XD|XB|XR|XA|NC)+$")


def load_quote(symbol: str) -> pd.DataFrame:
    sym = symbol.upper()
    df = normalize(psxdata.quote(sym))
    if not df.empty:
        return df
    screener = load_screener()
    if "symbol" not in screener.columns:
        return df
    base = screener["symbol"].astype(str).str.replace(STATUS_SUFFIX, "", regex=True)
    hit = screener[base == sym]
    return hit.reset_index(drop=True) if len(hit) == 1 else df


def load_index(name: str) -> pd.DataFrame:
    df = normalize(psxdata.indices(name))
    if df.empty:
        return df
    df.insert(0, "index_name", name)
    df = df.reindex(columns=list(INDEX_COLUMNS))
    for col in INDEX_COLUMNS[2:]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def load_fundamentals(symbols: list[str] | None) -> pd.DataFrame:
    df = normalize(psxdata.fundamentals())
    if symbols and "symbol" in df.columns:
        df = df[df["symbol"].isin(symbols)].reset_index(drop=True)
    return df


def _flatten(tables: dict[str, pd.DataFrame], labels: tuple[str, ...]) -> pd.DataFrame:
    use_labels = len(tables) == len(labels)
    frames: list[pd.DataFrame] = []
    for i, (key, df) in enumerate(tables.items()):
        if df.empty:
            continue
        df = normalize(df)
        df.insert(0, "category", labels[i] if use_labels else key)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_debt_market() -> pd.DataFrame:
    return _flatten(psxdata.debt_market(), DEBT_CATEGORIES)


def load_eligible_scrips() -> pd.DataFrame:
    return _flatten(psxdata.eligible_scrips(), ELIGIBLE_CATEGORIES)


class Loaders(Protocol):
    """The loader functions build_server calls. This module itself satisfies it."""

    def known_symbols(self) -> frozenset[str]: ...
    def load_prices(
        self, symbols: list[str], start: dt.date | None, end: dt.date | None
    ) -> LoadResult: ...
    def load_screener(self) -> pd.DataFrame: ...
    def load_sectors(self) -> pd.DataFrame: ...
    def load_symbols(self) -> pd.DataFrame: ...
    def load_quote(self, symbol: str) -> pd.DataFrame: ...
    def load_index(self, name: str) -> pd.DataFrame: ...
    def load_fundamentals(self, symbols: list[str] | None) -> pd.DataFrame: ...
    def load_debt_market(self) -> pd.DataFrame: ...
    def load_eligible_scrips(self) -> pd.DataFrame: ...
