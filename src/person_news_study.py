"""Q1 for the other watchlist people: when news about them spikes, do their assets move?
And (Q2) does the price move BEFORE or AFTER the news spike?

Events come from fetch_gdelt.py: days when coverage of a person jumped >= 3x their usual
level. Inside each 4-day hourly window:
  onset = first hour where coverage share >= max(3x the window's quiet baseline, 30% of the
          window's peak). This is "when the news took off".

Market side (hourly bars, as in post_hour_study.py): z = bar return / std of previous 70 bars.
  profile   mean |z| at -6..+6 bars around the onset bar (0 = bar containing the onset, or
            the next open bar if the market was closed). Shows whether price leads or lags.
  response  max |z| in bars -3..+3 around the onset.

Significance (the placebo test from RESEARCH_PLAN §8.1): draw 2,000 sets of random onsets
(same number of events) on the same asset and compute the same mean response. p = share of
random sets with a mean at least as big. Then Benjamini-Hochberg across all person x asset
tests, because with 18 tests some will look good by luck.

    .venv\\Scripts\\python src/person_news_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import load_hourly  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
rng = np.random.default_rng(0)
OFFSETS = range(-6, 7)
N_PLACEBO = 2000

ASSETS = {
    "Elon Musk": ["TSLA", "BTC-USD"],
    "Jensen Huang": ["NVDA", "SMH"],
    "Fed chair": ["SPY", "TLT"],
    "Prabowo Subianto": ["^JKSE", "IDR=X"],
    "Purbaya (ID finance minister)": ["^JKSE", "IDR=X"],
    "Sam Altman": ["MSFT", "NVDA"],
    "Scott Bessent": ["SPY"],
    "Howard Lutnick": ["SPY"],
    "Roaring Kitty": ["GME"],
    "Taylor Swift (control)": ["SPY"],
}


def zbars(asset: str) -> pd.DataFrame:
    b = load_hourly(asset).copy()
    b = b[(b["open"] > 0) & b["close"].notna()]
    b["ret"] = (b["close"] / b["open"] - 1) * 100
    b["z"] = b["ret"] / b["ret"].rolling(70, min_periods=50).std().shift(1)
    b["absz"] = b["z"].abs()
    return b.dropna(subset=["absz"])


def onsets(hourly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (person, day), w in hourly.groupby(["person", "spike_day"]):
        w = w.sort_values("ts")
        s = w["share"].fillna(0).to_numpy()
        if len(s) < 24 or s.max() <= 0:
            continue
        base = np.median(s[:12]) if np.median(s[:12]) > 0 else np.median(s[s > 0])
        thr = max(3 * base, 0.3 * s.max())
        i = int(np.argmax(s >= thr))
        rows.append({"person": person, "spike_day": day, "onset_utc": w["ts"].iloc[i],
                     "peak_utc": w["ts"].iloc[int(np.argmax(s))],
                     "hours_onset_to_peak": (w["ts"].iloc[int(np.argmax(s))] - w["ts"].iloc[i]).total_seconds() / 3600,
                     "peak_share": s.max(), "articles_peak_hour": w["value"].max()})
    return pd.DataFrame(rows)


def bar_position(b: pd.DataFrame, t: pd.Timestamp) -> int | None:
    """Index of the bar containing t, or the next bar if the market was closed at t."""
    i = int(b.index.searchsorted(t, side="right")) - 1
    if i >= 0 and t < b.index[i] + pd.Timedelta("1h"):
        return i
    j = i + 1
    return j if j < len(b) else None


def profile_at(absz: np.ndarray, i: int) -> np.ndarray | None:
    lo, hi = i + min(OFFSETS), i + max(OFFSETS)
    if lo < 0 or hi >= len(absz):
        return None
    return absz[lo: hi + 1]


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values."""
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n)
    prev = 1.0
    for rank, idx in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[idx] * n / rank)
        adj[idx] = prev
    return adj


def main() -> None:
    hourly = pd.read_parquet(PROC / "gdelt_hourly.parquet")
    ev = onsets(hourly)
    ev.to_csv(PROC / "person_news_events.csv", index=False)
    print(f"{len(ev)} news-spike events for {ev.person.nunique()} people")
    print(ev.groupby("person")["hours_onset_to_peak"].median().rename("median h onset->peak").round(1).to_string(), "\n")

    results, profiles = [], []
    for person, assets in ASSETS.items():
        e = ev[ev["person"] == person]
        if e.empty:
            continue
        for asset in assets:
            b = zbars(asset)
            absz = b["absz"].to_numpy()
            prof = []
            for t in e["onset_utc"]:
                i = bar_position(b, t)
                if i is None:
                    continue
                p = profile_at(absz, i)
                if p is not None:
                    prof.append(p)
            if len(prof) < 3:
                continue
            prof = np.array(prof)
            resp = prof[:, 3:10].max(axis=1)  # offsets -3..+3
            # placebo: random bar positions, same count
            valid = np.arange(-min(OFFSETS), len(absz) - max(OFFSETS))
            sims = np.empty(N_PLACEBO)
            for k in range(N_PLACEBO):
                idx = rng.choice(valid, len(prof))
                sims[k] = np.max(np.stack([absz[idx + o] for o in range(-3, 4)]), axis=0).mean()
            pval = (np.sum(sims >= resp.mean()) + 1) / (N_PLACEBO + 1)
            results.append({"person": person, "asset": asset, "events": len(prof),
                            "mean_max|z|_-3..+3": resp.mean(), "placebo_mean": sims.mean(),
                            "ratio": resp.mean() / sims.mean(), "p_placebo": pval,
                            "share_events_big(|z|>2)": (resp > 2).mean(),
                            "placebo_share_big": None})
            for o, v in zip(OFFSETS, prof.mean(axis=0)):
                profiles.append({"person": person, "asset": asset, "offset_h": o,
                                 "mean_absz": v, "ratio_vs_placebo": v / absz.mean()})
    res = pd.DataFrame(results).drop(columns="placebo_share_big")
    res["p_BH"] = bh(res["p_placebo"].to_numpy())
    res = res.sort_values("p_placebo")
    prof = pd.DataFrame(profiles)
    res.to_csv(PROC / "person_news_results.csv", index=False)
    prof.to_csv(PROC / "person_news_profiles.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(3).to_string(index=False), "\n")
    print("Lead/lag: mean |z| relative to a normal hour, by hours from news onset (all people pooled)")
    pooled = prof.groupby("offset_h")["ratio_vs_placebo"].mean()
    print(pooled.round(2).to_string())


if __name__ == "__main__":
    main()
