"""Download daily prices (free, via yfinance) for every ticker the project needs.

Tickers come from data/events/seed_events.csv (`target`) plus the benchmarks below.
Each ticker is saved to data/raw/prices/<ticker>.parquet and skipped if it was
already fetched today (use --force to refetch).

    .venv\\Scripts\\python src/fetch_prices.py
    .venv\\Scripts\\python src/fetch_prices.py --tickers NVDA TSLA --force
    .venv\\Scripts\\python src/fetch_prices.py --hourly   # also grow the hourly archive (yfinance keeps ~730 days)
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data" / "raw" / "prices"
SEED = ROOT / "data" / "events" / "seed_events.csv"

# Benchmarks: "the market" for each country, plus the US fear gauge for regime control.
BENCHMARKS = ["SPY", "QQQ", "^JKSE", "IDR=X", "BTC-USD", "^VIX"]
START = "2015-01-01"


def ticker_file(ticker: str) -> Path:
    safe = ticker.replace("^", "idx_").replace("=", "_").replace("/", "_")
    return PRICES / f"{safe}.parquet"


def load_prices(ticker: str) -> pd.DataFrame:
    """Read one cached ticker. Index = date, columns = open/high/low/close/adj_close/volume."""
    return pd.read_parquet(ticker_file(ticker))


def seed_tickers() -> list[str]:
    ev = pd.read_csv(SEED)
    out: set[str] = set()
    for t in ev["target"].dropna():
        out.update(x.strip() for x in str(t).split(";") if x.strip())
    return sorted(out)


def fetch(ticker: str, force: bool = False) -> str:
    path = ticker_file(ticker)
    if path.exists() and not force:
        modified = dt.date.fromtimestamp(path.stat().st_mtime)
        if modified == dt.date.today():
            return "cached"
    # auto_adjust=False keeps both: `close` (what the screen showed that day) and
    # `adj_close` (dividends/splits removed). Returns always use adj_close; the raw
    # close is kept to spot ex-dividend drops that look like "news" (the Ronaldo case).
    df = yf.download(ticker, start=START, interval="1d", auto_adjust=False,
                     progress=False, multi_level_index=False)
    if df is None or df.empty:
        return "EMPTY"
    df = df.rename(columns=lambda c: c.lower().replace(" ", "_"))
    df = df[["open", "high", "low", "close", "adj_close", "volume"]]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    df.to_parquet(path)
    return f"{len(df)} rows {df.index.min().date()} -> {df.index.max().date()}"


PRICES_1H = ROOT / "data" / "raw" / "prices_1h"
INTRADAY = ["SPY", "QQQ", "BTC-USD", "^JKSE", "IDR=X", "TSLA", "NVDA", "SMH", "TLT", "GME", "MSFT"]


def fetch_hourly(ticker: str) -> str:
    """Hourly bars. yfinance only serves the last ~730 days of 1h data, so new data is
    MERGED into the cached file: run this regularly and the archive keeps growing."""
    PRICES_1H.mkdir(parents=True, exist_ok=True)
    path = PRICES_1H / ticker_file(ticker).name
    df = yf.download(ticker, period="730d", interval="1h", auto_adjust=False,
                     progress=False, multi_level_index=False)
    if df is None or df.empty:
        return "EMPTY"
    df = df.rename(columns=lambda c: c.lower().replace(" ", "_"))
    df = df[["open", "high", "low", "close", "volume"]]
    idx = pd.to_datetime(df.index)
    df.index = (idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC"))
    df.index.name = "ts_utc"
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_parquet(path)
    return f"{len(df)} hourly bars {df.index.min():%Y-%m-%d} -> {df.index.max():%Y-%m-%d %H:%M} UTC"


def load_hourly(ticker: str) -> pd.DataFrame:
    return pd.read_parquet(PRICES_1H / ticker_file(ticker).name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="*", help="default: benchmarks + seed event targets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hourly", action="store_true", help="also update the hourly archive")
    args = ap.parse_args()

    PRICES.mkdir(parents=True, exist_ok=True)
    tickers = args.tickers or sorted(set(BENCHMARKS) | set(seed_tickers()))
    for t in tickers:
        try:
            print(f"{t:10s} {fetch(t, args.force)}")
        except Exception as e:  # one bad ticker shouldn't stop the rest
            print(f"{t:10s} FAILED: {e}")
    if args.hourly:
        for t in INTRADAY:
            try:
                print(f"{t:10s} 1h: {fetch_hourly(t)}")
            except Exception as e:
                print(f"{t:10s} 1h FAILED: {e}")


if __name__ == "__main__":
    main()
