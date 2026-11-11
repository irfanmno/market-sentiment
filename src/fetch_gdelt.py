"""News-coverage timelines for the watchlist people, from the free GDELT DOC 2.0 API.

GDELT is strict about traffic (one request per 5 s, and it penalises bursts for minutes),
so this works in two passes and caches every response (re-running resumes):
  1. DAILY pass: one request per person for the whole period -> find spike days
     (coverage share >= 2x the person's trailing 30-day median, top N, >= 3 days apart).
  2. HOURLY pass: a 4-day window around each spike day -> hourly article counts.

Counts are turned into a share of all monitored articles (value / norm), so the daily
and weekly cycle of total news volume doesn't look like a spike.

    .venv\\Scripts\\python src/fetch_gdelt.py                 # both passes, all people
    .venv\\Scripts\\python src/fetch_gdelt.py --people Musk   # names containing "Musk"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "gdelt"
OUT = ROOT / "data" / "processed"
API = "https://api.gdeltproject.org/api/v2/doc/doc"

START, END = "20241101000000", "20261109000000"
PACE_S = 20          # seconds between requests (GDELT asks >= 5, but punishes bursts)
MAX_SPIKES = 15
SPIKE_RATIO = 2      # 3x was too strict for always-in-the-news people (Musk: 2 days in 2 years)

# person -> GDELT query. Trump is covered by his own posts (Truth Social).
QUERIES = {
    "Elon Musk": '"Elon Musk"',
    "Jensen Huang": '"Jensen Huang"',
    "Fed chair": '("Jerome Powell" OR "Kevin Warsh")',
    "Prabowo Subianto": 'Prabowo',
    "Purbaya (ID finance minister)": 'Purbaya',
    "Sam Altman": '"Sam Altman"',
    "Scott Bessent": '"Scott Bessent"',
    "Howard Lutnick": '"Howard Lutnick"',
    "Roaring Kitty": '("Roaring Kitty" OR "Keith Gill")',
    "Taylor Swift (control)": '"Taylor Swift"',
}

_last_call = 0.0


def call(query: str, start: str, end: str) -> dict:
    key = hashlib.md5(f"{query}|{start}|{end}".encode()).hexdigest()[:16]
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    global _last_call
    params = {"query": query, "mode": "timelinevolraw", "format": "json",
              "startdatetime": start, "enddatetime": end}
    wait = 60
    for attempt in range(5):
        time.sleep(max(0.0, PACE_S - (time.time() - _last_call)))
        _last_call = time.time()
        try:
            r = requests.get(API, params=params, timeout=90,
                             headers={"User-Agent": "market-sentiment research script"})
        except requests.RequestException as e:
            print(f"    network error ({e.__class__.__name__}), waiting {wait}s")
            time.sleep(wait); wait = min(wait * 2, 600)
            continue
        if r.status_code == 200 and r.text.lstrip().startswith("{"):
            data = r.json()
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        print(f"    HTTP {r.status_code}, waiting {wait}s (attempt {attempt + 1})")
        time.sleep(wait); wait = min(wait * 2, 600)
    raise RuntimeError(f"GDELT gave up on {query} {start}-{end}")


def to_series(data: dict) -> pd.DataFrame:
    tl = data.get("timeline") or []
    if not tl:
        return pd.DataFrame(columns=["value", "norm", "share"])
    df = pd.DataFrame(tl[0]["data"])
    df["ts"] = pd.to_datetime(df["date"], format="%Y%m%dT%H%M%SZ", utc=True)
    df = df.set_index("ts")[["value", "norm"]].astype(float)
    df["share"] = df["value"] / df["norm"].where(df["norm"] > 0) * 1e4  # per 10k monitored articles
    return df


def spike_days(daily: pd.DataFrame) -> list[pd.Timestamp]:
    s = daily["share"].fillna(0)
    base = s.rolling(30, min_periods=10).median().shift(1)
    ratio = s / base.where(base > 0)
    cand = ratio[(ratio >= SPIKE_RATIO) & (s >= s.quantile(0.9))].sort_values(ascending=False)
    picked: list[pd.Timestamp] = []
    for d in cand.index:
        if all(abs((d - p).days) >= 3 for p in picked):
            picked.append(d)
        if len(picked) >= MAX_SPIKES:
            break
    return sorted(picked)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--people", nargs="*")
    args = ap.parse_args()
    people = {k: v for k, v in QUERIES.items()
              if not args.people or any(p.lower() in k.lower() for p in args.people)}
    daily_rows, hourly_rows, spikes, failed = [], [], [], []
    for person, q in people.items():
        print(f"{person}: daily pass")
        try:
            d = to_series(call(q, START, END))
        except RuntimeError as e:
            print(f"    SKIPPED ({e}); re-run later, cached parts are kept"); failed.append(person); continue
        if d.empty:
            print("    no data"); continue
        d["person"] = person
        daily_rows.append(d.reset_index())
        days = spike_days(d)
        print(f"    {len(d)} daily points, {len(days)} spike days: "
              + ", ".join(f"{x:%Y-%m-%d}" for x in days))
        for day in days:
            s = (day - pd.Timedelta(days=1)).strftime("%Y%m%d000000")
            e = (day + pd.Timedelta(days=3)).strftime("%Y%m%d000000")
            try:
                h = to_series(call(q, s, e))
            except RuntimeError:
                print(f"    hourly window {day:%Y-%m-%d} SKIPPED"); failed.append(f"{person} {day:%Y-%m-%d}"); continue
            h["person"], h["spike_day"] = person, day
            hourly_rows.append(h.reset_index())
            spikes.append({"person": person, "spike_day": day})
    OUT.mkdir(parents=True, exist_ok=True)
    if daily_rows:
        pd.concat(daily_rows).to_parquet(OUT / "gdelt_daily.parquet")
    if hourly_rows:
        pd.concat(hourly_rows).to_parquet(OUT / "gdelt_hourly.parquet")
    pd.DataFrame(spikes).to_csv(OUT / "gdelt_spike_days.csv", index=False)
    print("saved gdelt_daily.parquet, gdelt_hourly.parquet, gdelt_spike_days.csv")
    if failed:
        print(f"{len(failed)} requests still missing (GDELT rate limit), re-run to fill: " + "; ".join(failed))


if __name__ == "__main__":
    main()
