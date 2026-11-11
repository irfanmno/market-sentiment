"""Fed chair: are the attention spikes that move markets just the calendar, or real surprises?

Each Fed-chair attention spike (person_attention_study.spikes) gets a label from the
official calendar (fetch_fomc_dates.py):
  FOMC          spike within -1..+1 days of a scheduled FOMC decision day
  testimony     within -1..+2 days of a semiannual testimony (House + Senate, 2 days)
  Jackson Hole  20-31 Aug, Thu-Sat (the chair's speech is the Friday)
  surprise      everything else, incl. the 2 emergency meetings of March 2020
Surprises are split once more: "market-led" if SPY already had a big day (|z| > 2) on
day -1, i.e. the crash probably came first and people then looked up the Fed chair.

Same placebo test as the main study (max |z| on day 0/+1 vs 2,000 random day sets).
Extra check for the FOMC group: is a meeting WITH an attention spike bigger than a
meeting without one? If yes, attention helps flag the surprising meetings.

    .venv\\Scripts\\python src/fed_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from person_attention_study import N_PLACEBO, spikes, zdaily  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC, EVT = ROOT / "data" / "processed", ROOT / "data" / "events"
rng = np.random.default_rng(1)


def label(day: pd.Timestamp, fomc: pd.Series, emergency: pd.Series, testimony: pd.Series) -> str:
    def near(dates: pd.Series, lo: int, hi: int) -> bool:
        d = (day - dates).dt.days
        return bool(((d >= lo) & (d <= hi)).any())
    if near(emergency, -1, 1):
        return "surprise"
    if near(fomc, -1, 1):
        return "FOMC"
    if near(testimony, -1, 2):
        return "testimony"
    if day.month == 8 and day.day >= 20 and day.day_of_week in (3, 4, 5):
        return "Jackson Hole"
    return "surprise"


def placebo(absz: np.ndarray, pos: np.ndarray) -> dict:
    resp = np.maximum(absz[pos], absz[pos + 1])
    valid = np.arange(1, len(absz) - 1)
    sims = np.array([np.maximum(absz[s], absz[s + 1]).mean()
                     for s in (rng.choice(valid, len(pos)) for _ in range(N_PLACEBO))])
    return {"events": len(pos), "resp_mean": resp.mean(), "ratio": resp.mean() / sims.mean(),
            "p_placebo": (np.sum(sims >= resp.mean()) + 1) / (N_PLACEBO + 1),
            "big_%": (resp > 2).mean() * 100}


def main() -> None:
    meetings = pd.read_csv(EVT / "fomc_meetings.csv", parse_dates=["decision_day"])
    fomc = meetings.loc[~meetings.unscheduled, "decision_day"]
    emergency = meetings.loc[meetings.unscheduled, "decision_day"]
    testimony = pd.read_csv(EVT / "fed_testimony.csv", parse_dates=["testimony_day"])["testimony_day"]

    views = pd.read_parquet(PROC / "wiki_views.parquet")
    ev = spikes(views[views.person == "Fed chair"].set_index("date")["views"])
    ev["kind"] = [label(d, fomc, emergency, testimony) for d in ev["spike_day"]]

    spy = zdaily("SPY")
    pos_spy = spy.index.searchsorted(ev["spike_day"])
    ok = (pos_spy >= 1) & (pos_spy + 1 < len(spy))
    ev, pos_spy = ev[ok].reset_index(drop=True), pos_spy[ok]
    zs = spy.to_numpy()
    ev["z_-1"], ev["z_0"], ev["z_+1"] = zs[pos_spy - 1], zs[pos_spy], zs[pos_spy + 1]
    ev.loc[(ev.kind == "surprise") & (ev["z_-1"].abs() > 2), "kind"] = "surprise (market-led)"
    ev.to_csv(PROC / "fed_split_events.csv", index=False)
    print("Fed chair attention spikes by kind:")
    print(ev.kind.value_counts().to_string(), "\n")

    rows = []
    for asset in ["SPY", "TLT"]:
        z = zdaily(asset)
        absz = z.abs().to_numpy()
        pos_all = z.index.searchsorted(ev["spike_day"])
        groups = {"all": np.ones(len(ev), bool),
                  "scheduled (FOMC + testimony + Jackson Hole)": ev.kind.isin(["FOMC", "testimony", "Jackson Hole"]).to_numpy(),
                  "  FOMC": (ev.kind == "FOMC").to_numpy(),
                  "  testimony + Jackson Hole": ev.kind.isin(["testimony", "Jackson Hole"]).to_numpy(),
                  "surprise (not market-led)": (ev.kind == "surprise").to_numpy(),
                  "surprise (market-led)": (ev.kind == "surprise (market-led)").to_numpy()}
        for g, m in groups.items():
            pos = pos_all[m]
            pos = pos[(pos >= 1) & (pos + 1 < len(z))]
            if len(pos) >= 3:
                rows.append({"asset": asset, "group": g, **placebo(absz, pos)})
        # FOMC meetings with vs without an attention spike (both vs random days)
        spiked = ev.loc[ev.kind == "FOMC", "spike_day"]
        has = fomc.apply(lambda d: bool(((spiked - d).dt.days.between(-1, 1)).any()))
        for g, dates in [("all FOMC meetings", fomc), ("  FOMC with attention spike", fomc[has]),
                         ("  FOMC without spike", fomc[~has])]:
            pos = z.index.searchsorted(dates)
            pos = pos[(pos >= 1) & (pos + 1 < len(z))]
            rows.append({"asset": asset, "group": g, **placebo(absz, pos)})
    res = pd.DataFrame(rows)
    res.to_csv(PROC / "fed_split_results.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.round(3).to_string(index=False), "\n")
    s = ev[ev.kind == "surprise"].assign(resp=lambda d: d[["z_0", "z_+1"]].abs().max(axis=1))
    print("Surprise spikes, biggest SPY response first:")
    print(s.sort_values("resp", ascending=False)[["spike_day", "views", "ratio", "z_-1", "z_0", "z_+1"]]
          .head(15).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
