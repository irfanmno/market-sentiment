"""Archive 1-minute bars before yfinance forgets them (it only serves the last ~7 days).

Run once a day. Writes one CSV per ticker per UTC day; days already saved and complete are
skipped, so a missed day is caught up by the next run as long as it's within 7 days.
This is the only free way to get minute data for Indonesia (IHSG, IDR) going forward, and
it gives Q2 (how fast does price react) minute resolution from now on.

    .venv\\Scripts\\python src/collect_minute.py      # -> <COLLECTOR_DIR>/minute/<ticker>/YYYY-MM-DD.csv
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("COLLECTOR_DIR", ROOT / "data" / "collector")) / "minute"
TICKERS = ["SPY", "QQQ", "NVDA", "TSLA", "GME", "TLT", "MSFT", "^JKSE", "IDR=X", "BTC-USD"]


def main() -> None:
    today = dt.datetime.now(dt.timezone.utc).date()
    for t in TICKERS:
        folder = OUT / t.replace("^", "idx_").replace("=", "_")
        try:
            df = yf.download(t, period="7d", interval="1m", auto_adjust=False, progress=False,
                             multi_level_index=False)
        except Exception as e:
            print(f"{t:8s} FAILED {e.__class__.__name__}"); continue
        if df is None or df.empty:
            print(f"{t:8s} EMPTY"); continue
        df = df.rename(columns=lambda c: c.lower().replace(" ", "_"))[["open", "high", "low", "close", "volume"]]
        idx = pd.to_datetime(df.index)
        df.index = (idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")).strftime("%Y-%m-%dT%H:%MZ")
        df.index.name = "ts_utc"
        saved = []
        for day, g in df.groupby(df.index.str[:10]):
            if dt.date.fromisoformat(day) >= today:      # today is still in progress
                continue
            f = folder / f"{day}.csv"
            if f.exists():
                continue
            folder.mkdir(parents=True, exist_ok=True)
            g.round(6).to_csv(f)
            saved.append(f"{day}({len(g)})")
        print(f"{t:8s} saved {', '.join(saved) if saved else 'nothing new'}")


if __name__ == "__main__":
    main()
