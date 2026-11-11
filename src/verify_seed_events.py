"""Check the seed events against real daily prices (first, rough pass of RESEARCH_PLAN §8.1).

For each event x target asset:
  day 0     = the event date, or the next trading day if the event came after the close
              (time_et >= 16:00) or on a non-trading day. Unknown time -> the event date,
              and day +1 is shown too in case it was really after hours.
  ret       = adj_close return on that day (raw, in %)
  AR        = abnormal return = ret - (alpha + beta * benchmark return), the market model
              fitted on the 120 trading days ending 10 days before the event.
              Index targets (SPY, ^JKSE, ...) ARE the market, so AR = ret - their mean.
  z         = AR / standard deviation of the model's errors in the fit window
              ("how many normal days' worth of move was this?")
  p_emp     = share of the previous 250 days whose |AR| was at least as big (placebo-style)
  CAR+1/+5  = abnormal return summed over days 0..1 and 0..5 (does it stick or bounce back?)

    .venv\\Scripts\\python src/verify_seed_events.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import SEED, load_prices  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "seed_event_check.csv"

INDEX_TARGETS = {"SPY", "QQQ", "^JKSE", "IDR=X", "BTC-USD"}
FIT_LEN, GAP, PLACEBO_LEN = 120, 10, 250


def benchmark_for(ticker: str) -> str:
    if ticker.endswith(".JK") or ticker in {"^JKSE", "IDR=X"}:
        return "^JKSE"
    return "SPY"


def returns(ticker: str) -> pd.Series:
    return load_prices(ticker)["adj_close"].pct_change().dropna() * 100


def day0_position(idx: pd.DatetimeIndex, date: pd.Timestamp, time_et: str | float) -> int:
    after_close = isinstance(time_et, str) and time_et >= "16:00"
    pos = idx.searchsorted(date, side="right" if after_close else "left")
    return int(pos)


def check(ticker: str, date: pd.Timestamp, time_et) -> dict:
    r = returns(ticker)
    pos = day0_position(r.index, date, time_et)
    if pos >= len(r) or pos < FIT_LEN + GAP:
        return {"error": "not enough data"}

    fit = r.iloc[pos - GAP - FIT_LEN: pos - GAP]
    if ticker in INDEX_TARGETS:
        # The asset is the market itself: expected return = its own recent average.
        def expected(sl):
            return pd.Series(fit.mean(), index=sl.index)
        resid_sd = fit.std()
        beta = np.nan
    else:
        m = returns(benchmark_for(ticker)).reindex(r.index)
        x, y = m.loc[fit.index], fit
        beta, alpha = np.polyfit(x, y, 1)
        resid_sd = (y - (alpha + beta * x)).std()

        def expected(sl):
            return alpha + beta * m.loc[sl.index]

    ar = r - expected(r)
    window = ar.iloc[pos: pos + 6]
    hist = ar.iloc[max(0, pos - PLACEBO_LEN): pos]
    a0 = window.iloc[0]
    return {
        "day0": r.index[pos].date(),
        "ret0": round(r.iloc[pos], 2),
        "AR0": round(a0, 2),
        "z0": round(a0 / resid_sd, 1),
        "p_emp": round((hist.abs() >= abs(a0)).mean(), 3),
        "AR+1": round(window.iloc[1], 2) if len(window) > 1 else np.nan,
        "CAR+1": round(window.iloc[:2].sum(), 2),
        "CAR+5": round(window.sum(), 2) if len(window) == 6 else np.nan,
        "beta": round(beta, 2) if beta == beta else np.nan,
    }


def main() -> None:
    ev = pd.read_csv(SEED, dtype={"time_et": str})
    rows = []
    for _, e in ev.iterrows():
        for t in str(e["target"]).split(";"):
            t = t.strip()
            res = check(t, pd.Timestamp(e["date"]), e["time_et"])
            rows.append({"event_id": e["event_id"], "who": e["who"], "target": t,
                         "date": e["date"], "time_et": e["time_et"],
                         "expected_dir": e["expected_dir"], **res})
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    pd.set_option("display.width", 200)
    print(out.drop(columns=["who"]).to_string(index=False))
    print(f"\nsaved -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
