"""What happens AFTER a big hour that contains a Trump post? Keep going, or bounce back?

This is the "detect, then follow" version of the pipeline: we don't predict the first
move, we look at what came after it.

Event = an hourly bar with |z| > 2 (a big hour) that contains a post on a topic.
Only the biggest such hour per day is kept, so one crazy day doesn't count five times.

Follow-through at horizon h = return from the END of the big hour to h bars later,
multiplied by the sign of the big hour's move:
    > 0  the move kept going (momentum)
    < 0  it bounced back (reversal)
Also as a share of the first move: -0.5 = half of the move was undone.

Control group = big hours with NO post at all. If Trump shocks behave like any other big
move, there's nothing Trump-specific to trade.

    .venv\\Scripts\\python src/after_shock.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_hour_study import bars_with_posts, tag_posts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
BIG = 2.0
rng = np.random.default_rng(0)

# Horizons in bars. SPY/QQQ have 7 bars per trading day; BTC trades 24 bars per day.
HORIZONS = {
    "SPY": {"+1h": 1, "+3h": 3, "+1 day": 7, "+5 days": 35},
    "QQQ": {"+1h": 1, "+3h": 3, "+1 day": 7, "+5 days": 35},
    "BTC-USD": {"+1h": 1, "+4h": 4, "+1 day": 24, "+5 days": 120},
}
GROUPS = {
    "tariff post": lambda b: b["tariff"] == 1,
    "any market-topic post": lambda b: b[["tariff", "fed", "market", "china"]].max(axis=1) == 1,
    "no post (control)": lambda b: b["any_post"] == 0,
}


def events(b: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    e = b[mask & (b["absz"] > BIG)]
    return e.loc[e.groupby("date")["absz"].idxmax()]


def boot_ci(x: np.ndarray, n: int = 5000) -> tuple[float, float]:
    if len(x) < 3:
        return np.nan, np.nan
    m = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main() -> None:
    posts = tag_posts()
    rows, detail = [], []
    for asset, hz in HORIZONS.items():
        b = bars_with_posts(asset, posts, asset != "BTC-USD")
        close = b["close"]
        for gname, gmask in GROUPS.items():
            e = events(b, gmask(b))
            sign = np.sign(e["ret"])
            for hname, h in hz.items():
                fwd = (close.shift(-h) / close - 1).loc[e.index] * 100
                ok = fwd.notna()
                follow = (fwd * sign)[ok].to_numpy()
                ratio = follow / e.loc[ok, "ret"].abs().to_numpy()
                lo, hi = boot_ci(follow)
                rows.append({"asset": asset, "group": gname, "horizon": hname, "events": int(ok.sum()),
                             "first_move_%": e.loc[ok, "ret"].abs().mean(),
                             "follow_mean_%": follow.mean() if len(follow) else np.nan,
                             "ci_low": lo, "ci_high": hi,
                             "follow_median_%": np.median(follow) if len(follow) else np.nan,
                             "share_of_first_move": np.median(ratio) if len(ratio) else np.nan,
                             "kept_going_%": (follow > 0).mean() * 100 if len(follow) else np.nan})
            if gname == "tariff post" and asset == "SPY":
                for ts, r in e.iterrows():
                    f = {k: (close.shift(-h) / close - 1).get(ts, np.nan) * 100 * np.sign(r.ret) for k, h in hz.items()}
                    detail.append({"hour_et": ts.tz_convert("America/New_York").strftime("%Y-%m-%d %H:%M"),
                                   "move_%": round(r.ret, 2), **{k: round(v, 2) for k, v in f.items()}})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "after_shock.csv", index=False)
    pd.set_option("display.width", 230)
    print("Follow-through after a big hour (+ = kept going, - = bounced back), in % of price")
    print(res.round(2).to_string(index=False))
    print("\nSPY big tariff hours, one by one (follow-through in %, signed):")
    print(pd.DataFrame(detail).to_string(index=False))


if __name__ == "__main__":
    main()
