"""Q1 + Q2 for the wider watchlist, at DAILY resolution, using Wikipedia attention spikes.

Event = a day when a person's (mobile) Wikipedia views jump >= 3x their trailing 30-day
median AND are in the top 10% of their own history; spikes < 5 days apart are merged.

Market side, per asset, every trading day t:
  single stocks: abnormal return = ret - (alpha + beta * SPY ret), market model fit on
                 days t-130..t-11 (so the event itself can't leak into the fit)
  index / FX / bonds / BTC: raw return (they ARE the market)
  z = abnormal return / its std over the same window

Event day 0 = first trading day on/after the UTC spike day. Indonesian assets close at
09:00 UTC, so a story that breaks during the US day shows up there on day +1.

  profile    mean |z| from day -5 to +5 (lead/lag: does price move BEFORE attention?)
  response   max(|z| day 0, |z| day +1)
  placebo    2,000 random sets of days, same count, same response -> empirical p
  BH         Benjamini-Hochberg across all person x asset tests
  drop-top-2 same test with the 2 biggest events removed (and the 2 biggest of every
             placebo set, to keep it fair): is it a pattern or one or two famous days?
  Also: share of events where day -1 was already a big move (|z| > 2) = the attention
  spike was probably CAUSED by the market, not the other way round.

    .venv\\Scripts\\python src/person_attention_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import load_prices  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
rng = np.random.default_rng(0)
OFFSETS = np.arange(-5, 6)
N_PLACEBO = 2000
RATIO, GAP_DAYS = 3, 5

ASSETS = {
    "Elon Musk": ["TSLA", "BTC-USD"],
    "Jensen Huang": ["NVDA", "SMH"],
    "Fed chair": ["SPY", "TLT"],
    "Prabowo Subianto": ["^JKSE", "IDR=X"],
    "Purbaya (ID finance minister)": ["^JKSE", "IDR=X"],
    "Sam Altman": ["MSFT", "NVDA"],
    "Scott Bessent": ["SPY", "TLT"],
    "Howard Lutnick": ["SPY"],
    "Roaring Kitty": ["GME"],
    "Taylor Swift (control)": ["SPY"],
}
MARKET_MODEL = {"TSLA", "NVDA", "SMH", "MSFT", "GME"}


def spikes(v: pd.Series) -> pd.DataFrame:
    base = v.rolling(30, min_periods=20).median().shift(1)
    ratio = v / base.where(base > 0)
    floor = v[v > 0].quantile(0.9)
    cand = ratio[(ratio >= RATIO) & (v >= floor)].sort_values(ascending=False)
    picked: list[pd.Timestamp] = []
    for d in cand.index:
        if all(abs((d - p).days) >= GAP_DAYS for p in picked):
            picked.append(d)
    picked.sort()
    return pd.DataFrame({"spike_day": picked, "views": v.loc[picked].to_numpy(),
                         "ratio": ratio.loc[picked].round(1).to_numpy()})


def zdaily(asset: str) -> pd.Series:
    px = load_prices(asset)["adj_close"].dropna()
    r = px.pct_change().dropna() * 100
    if asset in MARKET_MODEL:
        m = load_prices("SPY")["adj_close"].pct_change().mul(100).reindex(r.index)
        win = dict(window=120, min_periods=100)
        rs, ms = r.shift(11), m.shift(11)          # window = days t-130..t-11
        beta = rs.rolling(**win).cov(ms) / ms.rolling(**win).var()
        alpha = rs.rolling(**win).mean() - beta * ms.rolling(**win).mean()
        ar = r - (alpha + beta * m)
        resid_hist = rs - (alpha + beta * ms)       # approximate: in-window residuals
        sd = resid_hist.rolling(**win).std()
    else:
        ar = r
        sd = r.shift(11).rolling(120, min_periods=100).std()
    return (ar / sd).dropna()


def bh(p: np.ndarray) -> np.ndarray:
    n, order = len(p), np.argsort(p)
    adj, prev = np.empty(n), 1.0
    for rank, idx in reversed(list(enumerate(order, start=1))):
        prev = min(prev, p[idx] * n / rank)
        adj[idx] = prev
    return adj


def main() -> None:
    views = pd.read_parquet(PROC / "wiki_views.parquet")
    results, profiles, events = [], [], []
    for person, assets in ASSETS.items():
        v = views[views.person == person].set_index("date")["views"]
        ev = spikes(v)
        for asset in assets:
            z = zdaily(asset)
            absz = z.abs().to_numpy()
            idx = z.index.searchsorted(ev["spike_day"])     # first trading day >= spike day
            keep = (idx + OFFSETS.min() >= 0) & (idx + OFFSETS.max() < len(z))
            pos = idx[keep]
            if len(pos) < 5:
                continue
            prof = np.stack([absz[pos + o] for o in OFFSETS], axis=1)
            resp = np.maximum(prof[:, 5], prof[:, 6])        # day 0, day +1
            valid = np.arange(-OFFSETS.min(), len(z) - OFFSETS.max())
            sim_sets = [np.sort(np.maximum(absz[s], absz[s + 1]))
                        for s in (rng.choice(valid, len(pos)) for _ in range(N_PLACEBO))]
            sims = np.array([x.mean() for x in sim_sets])
            sims_d2 = np.array([x[:-2].mean() for x in sim_sets])   # drop each set's 2 biggest
            resp_d2 = np.sort(resp)[:-2].mean()
            results.append({"person": person, "asset": asset, "events": len(pos),
                            "resp_mean": resp.mean(), "placebo_mean": sims.mean(),
                            "ratio": resp.mean() / sims.mean(),
                            "p_placebo": (np.sum(sims >= resp.mean()) + 1) / (N_PLACEBO + 1),
                            "p_drop_top2": (np.sum(sims_d2 >= resp_d2) + 1) / (N_PLACEBO + 1),
                            "big_day0or1_%": (resp > 2).mean() * 100,
                            "placebo_big_%": (np.maximum(absz[valid], absz[valid + 1]) > 2).mean() * 100,
                            "big_day-1_%": (prof[:, 4] > 2).mean() * 100})
            base = absz.mean()
            for o, m in zip(OFFSETS, prof.mean(axis=0)):
                profiles.append({"person": person, "asset": asset, "offset_d": int(o),
                                 "mean_absz": m, "vs_normal_day": m / base})
            e = ev[keep].copy()
            e["asset"], e["day0"] = asset, z.index[pos]
            e["z_-1"], e["z_0"], e["z_+1"] = z.to_numpy()[pos - 1], z.to_numpy()[pos], z.to_numpy()[pos + 1]
            events.append(e.assign(person=person))
    res = pd.DataFrame(results)
    res["p_BH"] = bh(res["p_placebo"].to_numpy())
    res = res.sort_values("p_placebo")
    prof = pd.DataFrame(profiles)
    evs = pd.concat(events)
    res.to_csv(PROC / "person_attention_results.csv", index=False)
    prof.to_csv(PROC / "person_attention_profiles.csv", index=False)
    evs.to_csv(PROC / "person_attention_events.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(3).to_string(index=False), "\n")
    print("Lead/lag: mean |z| vs a normal day, by trading days from the attention spike")
    print(prof.pivot_table(index=["person", "asset"], columns="offset_d", values="vs_normal_day").round(2).to_string())


if __name__ == "__main__":
    main()
