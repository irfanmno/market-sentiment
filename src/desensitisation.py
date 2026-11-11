"""Q4a: does the market get used to Trump's tariff posts?

Unit = an hourly bar containing at least one original tariff post (first such post in the
bar describes it). Outcome = |z| of that bar (see post_hour_study.py).

Three features per tariff bar:
  nth        how many tariff posts he had made before this one (since Feb 2022)
  gap_h      hours since his previous tariff post (a post 1h after the last one is old news)
  concrete   the post contains something new and specific: a % or $ figure, "effective",
             "pause", a deadline. A crude, rule-based "new information" flag.

Two views:
  A. Premium by stage: tariff bars split into 4 equal groups by nth. Premium = mean |z| of
     tariff bars - mean |z| of no-post bars in the SAME date range, with a bootstrap 95% CI.
     If the market gets used to it, the premium shrinks group by group.
  B. Regression on tariff bars: |z| ~ log(nth) + log(gap_h) + concrete + hour-of-day,
     SEs clustered by date.

Caveat: nth and calendar time move together, so "got used to it" can't be fully separated
from "2025 was a special year". The gap and concrete features help separate the two.

    .venv\\Scripts\\python src/desensitisation.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_hour_study import bars_with_posts, tag_posts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
CONCRETE = re.compile(r"\d+(?:\.\d+)?\s?%|\$\s?\d|(?i:effective|pause|deadline|beginning on|starting on|"
                      r"august 1|april 2|liberation day|\d+\s?day)")
rng = np.random.default_rng(0)


def tariff_posts(posts: pd.DataFrame) -> pd.DataFrame:
    t = posts[(posts["kind"] == "original") & posts["tariff"]].sort_values("created_utc").copy()
    t["nth"] = np.arange(1, len(t) + 1)
    t["gap_h"] = t["created_utc"].diff().dt.total_seconds() / 3600
    t["concrete"] = t["text"].map(lambda s: bool(CONCRETE.search(s))).astype(int)
    return t


def attach(b: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    """For each tariff bar, the first tariff post inside it."""
    bars = b.reset_index()[["ts_utc", "bar_end"]]
    m = pd.merge_asof(t, bars, left_on="created_utc", right_on="ts_utc", direction="backward")
    m = m[m["created_utc"] < m["bar_end"]].groupby("ts_utc").first()
    return b.join(m[["nth", "gap_h", "concrete", "text"]], how="left")


def boot_ci(x: np.ndarray, base: np.ndarray, n: int = 5000) -> tuple[float, float]:
    d = [rng.choice(x, len(x)).mean() - rng.choice(base, len(base)).mean() for _ in range(n)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def stages(b: pd.DataFrame, asset: str) -> pd.DataFrame:
    tb = b[b["nth"].notna()].copy()
    tb["stage"] = pd.qcut(tb["nth"], 4, labels=["1st quarter", "2nd", "3rd", "4th"])
    rows = []
    for s, g in tb.groupby("stage", observed=True):
        lo, hi = g.index.min(), g.index.max()
        base = b.loc[lo:hi]
        base = base[base["any_post"] == 0]["absz"].to_numpy()
        ci = boot_ci(g["absz"].to_numpy(), base)
        rows.append({"asset": asset, "stage": s, "posts_nth": f"{int(g.nth.min())}-{int(g.nth.max())}",
                     "dates": f"{lo:%Y-%m} to {hi:%Y-%m}", "bars": len(g),
                     "tariff_absz": g["absz"].mean(), "no_post_absz": base.mean(),
                     "premium": g["absz"].mean() - base.mean(), "ci_low": ci[0], "ci_high": ci[1],
                     "big_share": (g["absz"] > 2).mean()})
    return pd.DataFrame(rows)


def regression(b: pd.DataFrame, asset: str) -> pd.DataFrame:
    tb = b[b["nth"].notna() & b["gap_h"].notna()].copy()
    tb["log_nth"] = np.log(tb["nth"])
    tb["log_gap"] = np.log1p(tb["gap_h"])
    r = smf.ols("absz ~ log_nth + log_gap + concrete + C(hour)", data=tb).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(tb["date"])[0]})
    ci = r.conf_int()
    return pd.DataFrame([{"asset": asset, "term": k, "coef": r.params[k], "ci_low": ci.loc[k, 0],
                          "ci_high": ci.loc[k, 1], "p": r.pvalues[k], "n_bars": int(r.nobs)}
                         for k in ["log_nth", "log_gap", "concrete"]])


def main() -> None:
    posts = tag_posts()
    t = tariff_posts(posts)
    print(f"{len(t)} original tariff posts; concrete: {t.concrete.mean():.0%}; "
          f"median gap to previous tariff post: {t.gap_h.median():.1f} h\n")
    st, rg, tops = [], [], []
    for asset in ["SPY", "QQQ", "BTC-USD"]:
        b = attach(bars_with_posts(asset, posts, asset != "BTC-USD"), t)
        st.append(stages(b, asset))
        rg.append(regression(b, asset))
        if asset == "SPY":
            top = b[b["nth"].notna()].nlargest(8, "absz")
            for ts, r in top.iterrows():
                tops.append(f"{ts.tz_convert('America/New_York'):%Y-%m-%d %H:%M} z={r.z:+.1f} "
                            f"nth={int(r.nth)} gap={r.gap_h:.0f}h concrete={int(r.concrete)} | {r.text[:90]}")
    st, rg = pd.concat(st), pd.concat(rg)
    st.to_csv(OUT / "desensitisation_stages.csv", index=False)
    rg.to_csv(OUT / "desensitisation_regression.csv", index=False)
    pd.set_option("display.width", 220)
    print("A. Tariff premium by stage (extra |z| vs no-post hours in the same period)")
    print(st.round(3).to_string(index=False), "\n")
    print("B. Regression on tariff hours (date-clustered SEs)")
    print(rg.round(3).to_string(index=False), "\n")
    print("Biggest SPY tariff hours:")
    print("\n".join(tops))


if __name__ == "__main__":
    main()
