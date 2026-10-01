import datetime as dt

import pandas as pd

from psxdata_mcp import loaders


def test_snake() -> None:
    assert loaders.snake("Coupon/Rental Rate") == "coupon_rental_rate"
    assert loaders.snake(" P/E ") == "p_e"
    assert loaders.snake("close") == "close"


def test_normalize_converts_datetimes_to_dates() -> None:
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", None]),
            "mixed": [pd.Timestamp("2025-01-01"), None],
            "v": [1, 2],
        }
    )
    out = loaders.normalize(df)
    assert list(out.columns) == ["date", "mixed", "v"]
    assert out["date"].tolist() == [dt.date(2024, 1, 2), None]
    assert out["mixed"].tolist() == [dt.date(2025, 1, 1), None]


def test_normalize_object_column_with_nat() -> None:
    df = pd.DataFrame({"d": pd.Series([pd.Timestamp("2025-01-01"), pd.NaT], dtype=object)})
    assert loaders.normalize(df)["d"].tolist() == [dt.date(2025, 1, 1), None]


def test_load_prices_adds_symbol_and_collects_failures(fake_psx: dict[str, list[str]]) -> None:
    r = loaders.load_prices(["OGDC", "EMPTY", "PPL"], None, None)
    assert r.df.columns[0] == "symbol"
    assert sorted(r.df["symbol"].unique()) == ["OGDC", "PPL"]
    assert isinstance(r.df["date"].iloc[0], dt.date)
    assert r.failures == {"EMPTY": "no data in range"}


def test_load_prices_circuit_breaker(fake_psx: dict[str, list[str]]) -> None:
    r = loaders.load_prices(["DOWN", "LATER"], None, None)
    assert r.df.empty
    assert r.failures == {"DOWN": "PSX unreachable", "LATER": "skipped — PSX unreachable"}
    assert fake_psx["stocks"] == ["DOWN"]


def test_known_symbols(fake_psx: dict[str, list[str]]) -> None:
    assert "OGDC" in loaders.known_symbols()


def test_load_index_fixed_float_columns(fake_psx: dict[str, list[str]]) -> None:
    kse = loaders.load_index("KSE100")
    kmi = loaders.load_index("KMI30")
    for df in (kse, kmi):
        assert tuple(df.columns) == loaders.INDEX_COLUMNS
        assert df["shares_m"].dtype == "float64"
        assert df["freefloat_m"].dtype == "float64"
    assert kse["index_name"].unique().tolist() == ["KSE100"]
    assert kse["shares_m"].isna().all()
    assert kmi["shares_m"].tolist() == [12.5, 7.25]


def test_load_fundamentals_filters(fake_psx: dict[str, list[str]]) -> None:
    assert loaders.load_fundamentals(["OGDC"])["symbol"].tolist() == ["OGDC"]
    assert len(loaders.load_fundamentals(None)) == 2


def test_eligible_categories_labelled(fake_psx: dict[str, list[str]]) -> None:
    df = loaders.load_eligible_scrips()
    assert df.columns[0] == "category"
    assert df["category"].tolist() == list(loaders.ELIGIBLE_CATEGORIES)


def test_flatten_falls_back_to_table_keys_on_count_mismatch() -> None:
    tables = {"table_0": pd.DataFrame({"x": [1]}), "table_1": pd.DataFrame({"x": [2]})}
    out = loaders._flatten(tables, ("Only one label",))
    assert out["category"].tolist() == ["table_0", "table_1"]


def test_flatten_skips_empty_tables() -> None:
    tables = {"table_0": pd.DataFrame(), "table_1": pd.DataFrame({"x": [2]})}
    assert loaders._flatten(tables, ()).shape == (1, 2)


def test_load_debt_market(fake_psx: dict[str, list[str]]) -> None:
    df = loaders.load_debt_market()
    assert len(df) == 4
    assert df.columns[0] == "category"
    assert isinstance(df["maturity_date"].iloc[0], dt.date)


def test_snapshot_loaders(fake_psx: dict[str, list[str]]) -> None:
    assert len(loaders.load_screener()) == 2
    assert len(loaders.load_sectors()) == 1
    assert len(loaders.load_symbols()) == 5
    assert loaders.load_quote("ogdc")["price"].tolist() == [200.0]


def test_debt_categories_labelled(fake_psx: dict[str, list[str]]) -> None:
    assert loaders.load_debt_market()["category"].tolist() == list(loaders.DEBT_CATEGORIES)
