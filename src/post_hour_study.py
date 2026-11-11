"""Q1 first pass on ALL Trump posts: do hours with market-relevant posts move more?

Why hourly: he posts ~20 times a day, so nearly every trading day has a post, and
"post day vs no-post day" can't work. Hourly bars (free, yfinance) let us compare
hours that contain a post on a topic with hours that don't.

Steps
 1. Tag every original post with topics, using keyword rules (no AI): tariff/trade, fed,
    market, china, company, crypto. A post can have several topics, or none ("other").
 2. For each asset's hourly bars: bar return = close/open - 1 (inside the bar only, so the
    overnight gap is excluded). z = return / std of the previous 70 bars (~10 trading
    days), so a move counts relative to how jumpy the market was recently.
 3. Flag each bar with the topics of the posts made during it.
 4. Regression |z| ~ topic flags + any-post flag + hour-of-day, standard errors clustered
    by date (posts on the same day aren't independent). Also the NEXT bar's |z|, because a
    post at 10:55 only gets 5 minutes inside its own bar.

    .venv\\Scripts\\python src/post_hour_study.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_prices import load_hourly  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "data" / "processed" / "truth_posts.parquet"
OUT_DIR = ROOT / "data" / "processed"

TOPICS = {
    "tariff": r"(?i:tariff|trade deal|trade war|reciprocal|trade deficit|duties)",
    "fed": r"\bFed\b|\bFED\b|(?i:federal reserve|powell|interest rate|rate cut|too late)",
    "market": r"(?i:stock market|\bthe markets?\b|s&p|nasdaq|401\(?k|great time to buy)|\bDow\b|\bDOW\b",
    "china": r"(?i:\bchina\b|chinese)|\bXi\b",
    "company": (r"\b(?:Apple|Amazon|Intel|Tesla|Nvidia|NVIDIA|Boeing|Walmart|Google|Microsoft|"
                r"Ford|General Motors|Exxon|Harley|Mattel|Disney|Comcast|Goldman|JPMorgan|"
                r"Netflix|AT&T|Verizon|Oracle|Lockheed|U\.S\. Steel|Nippon Steel|Pfizer)\b"),
    "crypto": r"(?i:crypto|bitcoin|\bbtc\b|stablecoin|\$trump)",
}
FLAGS = list(TOPICS)


def tag_posts() -> pd.DataFrame:
    p = pd.read_parquet(POSTS)
    p = p[p["kind"].isin(["original", "repost", "media_only"])].copy()
    for name, pat in TOPICS.items():
        rx = re.compile(pat)
        # Topics only from his own words: reposts are often whole articles.
        p[name] = (p["kind"] == "original") & p["text"].map(lambda t: bool(rx.search(t)))
    return p


def bars_with_posts(asset: str, posts: pd.DataFrame, market_hours_only: bool) -> pd.DataFrame:
    b = load_hourly(asset).copy()
    b["ret"] = (b["close"] / b["open"] - 1) * 100
    b = b[b["ret"].notna() & (b["open"] > 0)]
    b["sd_prev"] = b["ret"].rolling(70, min_periods=50).std().shift(1)
    b["z"] = b["ret"] / b["sd_prev"]
    b["absz"] = b["z"].abs()
    b["absz_next"] = b["absz"].shift(-1)
    et = b.index.tz_convert("America/New_York")
    b["hour"] = et.hour
    b["date"] = et.date
    b["bar_end"] = b.index.to_series().shift(-1).clip(upper=b.index.to_series() + pd.Timedelta("1h"))
    b = b.dropna(subset=["absz", "absz_next", "bar_end"])

    p = posts[["created_utc", "kind", *FLAGS]].sort_values("created_utc")
    p = p[(p["created_utc"] >= b.index.min()) & (p["created_utc"] <= b.index.max())]
    m = pd.merge_asof(p, b[["bar_end"]].reset_index().rename(columns={"ts_utc": "bar"}),
                      left_on="created_utc", right_on="bar", direction="backward")
    m = m[m["created_utc"] < m["bar_end"]]  # post falls inside the bar, not in a closed-market gap
    agg = m.groupby("bar").agg(n_posts=("kind", "size"), **{f: (f, "any") for f in FLAGS})
    b = b.join(agg)
    b["n_posts"] = b["n_posts"].fillna(0).astype(int)
    for f in FLAGS:
        b[f] = b[f].astype("boolean").fillna(False).astype(int)
    b["any_post"] = (b["n_posts"] > 0).astype(int)
    return b


def summarise(b: pd.DataFrame, asset: str) -> pd.DataFrame:
    rows = []
    groups = {"no post": b["any_post"] == 0,
              "post, no market topic": (b["any_post"] == 1) & (b[FLAGS].sum(axis=1) == 0)}
    groups.update({f: b[f] == 1 for f in FLAGS})
    for name, mask in groups.items():
        g = b[mask]
        rows.append({"asset": asset, "group": name, "bars": len(g),
                     "mean_absz": g["absz"].mean(), "mean_absz_next": g["absz_next"].mean(),
                     "share_big(|z|>2)": (g["absz"] > 2).mean()})
    return pd.DataFrame(rows)


def regress(b: pd.DataFrame, y: str):
    f = f"{y} ~ any_post + " + " + ".join(FLAGS) + " + C(hour)"
    return smf.ols(f, data=b).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(b["date"])[0]})


def main() -> None:
    posts = tag_posts()
    orig = posts[posts["kind"] == "original"]
    print("original posts tagged:", len(orig))
    print(orig[FLAGS].sum().rename("posts").to_string(), "\n")

    all_summ, coefs = [], []
    for asset, mh in [("SPY", True), ("QQQ", True), ("BTC-USD", False)]:
        b = bars_with_posts(asset, posts, mh)
        all_summ.append(summarise(b, asset))
        for y in ["absz", "absz_next"]:
            r = regress(b, y)
            for term in ["any_post", *FLAGS]:
                coefs.append({"asset": asset, "outcome": y, "term": term,
                              "coef": r.params[term], "ci_low": r.conf_int().loc[term, 0],
                              "ci_high": r.conf_int().loc[term, 1], "p": r.pvalues[term]})
        top = b[b["tariff"] == 1].nlargest(5, "absz")[["ret", "z"]]
        top.index = top.index.tz_convert("America/New_York").strftime("%Y-%m-%d %H:%M ET")
        print(f"{asset}: biggest hours containing a tariff post\n{top.round(2).to_string()}\n")

    summ = pd.concat(all_summ)
    coef = pd.DataFrame(coefs)
    summ.to_csv(OUT_DIR / "post_hour_summary.csv", index=False)
    coef.to_csv(OUT_DIR / "post_hour_regression.csv", index=False)
    pd.set_option("display.width", 200)
    print(summ.round(3).to_string(index=False), "\n")
    print("Regression: extra |z| in bars containing a post on each topic (hour-of-day controlled, date-clustered SEs)")
    print(coef.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
