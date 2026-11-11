"""A surprise score for every Trump post (no AI: word counts + similarity), and a test of
whether it picks out the tariff posts that moved markets.

Scores per original post:
  novelty         1 - max cosine similarity (TF-IDF) to his previous 50 original posts.
                  1 = says something he hasn't said lately; 0 = a repeat.
  novelty_topic   same, but only against his previous 20 posts on the same topic (tariff).
  esc             escalation words - de-escalation words in the post (word lists below).
  esc_shift       esc minus the average esc of his previous 10 tariff posts: a sudden turn
                  hawkish (+) or dovish (-) compared with how he'd been talking.

Honesty note: the word lists were written AFTER reading the 10 Oct 2025 and 9 Apr 2025
posts, so they may be tuned to those two. The test is therefore also run WITHOUT those
two hours; only a result that survives that counts.

    .venv\\Scripts\\python src/surprise_score.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desensitisation import attach, tariff_posts  # noqa: E402
from post_hour_study import bars_with_posts, tag_posts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
URL_RX = re.compile(r"https?://\S+")

ESCALATE = [r"hostil", r"retaliat", r"massive", r"rais(e|ing)", r"increas", r"impos", r"immediately",
            r"cancel", r"terminat", r"sanction", r"punish", r"\bwar\b", r"\bban\b", r"no longer",
            r"will be charged", r"unfair", r"ripp(ed|ing) off", r"embargo", r"cut off", r"threat"]
DEESCALATE = [r"\bdeals?\b", r"agreement", r"\bpaus", r"reduc", r"lower", r"productive", r"progress",
              r"truce", r"exempt", r"extension", r"extend", r"delay", r"great meeting",
              r"great relationship", r"friendship", r"negotiat", r"framework", r"settle"]
ESC_RX = [re.compile(p, re.I) for p in ESCALATE]
DEESC_RX = [re.compile(p, re.I) for p in DEESCALATE]


def esc_score(text: str) -> int:
    return sum(bool(r.search(text)) for r in ESC_RX) - sum(bool(r.search(text)) for r in DEESC_RX)


def rolling_max_sim(X, window: int) -> np.ndarray:
    """For each row i: max cosine similarity with rows i-window..i-1 (TF-IDF rows are L2-normed)."""
    out = np.full(X.shape[0], np.nan)
    for i in range(1, X.shape[0]):
        lo = max(0, i - window)
        if X[i].nnz == 0:
            continue
        out[i] = (X[lo:i] @ X[i].T).max()
    return out


def score_posts() -> pd.DataFrame:
    posts = tag_posts()
    o = posts[posts["kind"] == "original"].sort_values("created_utc").copy()
    o["clean"] = o["text"].str.replace(URL_RX, " ", regex=True).str.strip()
    # IDF is fit on the whole archive (mild look-ahead; for the live pipeline, refit on the past only).
    vec = TfidfVectorizer(min_df=3, max_df=0.5, ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    X = vec.fit_transform(o["clean"]).tocsr()
    o["novelty"] = 1 - rolling_max_sim(X, 50)
    t_idx = np.flatnonzero(o["tariff"].to_numpy())
    nov_t = 1 - rolling_max_sim(X[t_idx], 20)
    o["novelty_topic"] = np.nan
    o.iloc[t_idx, o.columns.get_loc("novelty_topic")] = nov_t
    o["esc"] = o["clean"].map(esc_score)
    tar = o[o["tariff"]]
    prev_mean = tar["esc"].shift(1).rolling(10, min_periods=3).mean()
    o["esc_shift"] = np.nan
    o.loc[tar.index, "esc_shift"] = tar["esc"] - prev_mean
    return o


def test(o: pd.DataFrame) -> None:
    posts = tag_posts()
    t = tariff_posts(posts).join(o[["novelty", "novelty_topic", "esc", "esc_shift"]])
    rows, ranks = [], []
    for asset in ["SPY", "QQQ", "BTC-USD"]:
        b = bars_with_posts(asset, posts, asset != "BTC-USD")
        bars = b.reset_index()[["ts_utc", "bar_end"]]
        m = pd.merge_asof(t, bars, left_on="created_utc", right_on="ts_utc", direction="backward")
        m = m[m["created_utc"] < m["bar_end"]]
        # Per bar: the most surprising tariff post in it.
        g = m.groupby("ts_utc").agg(novelty=("novelty", "max"), novelty_topic=("novelty_topic", "max"),
                                    esc_shift_abs=("esc_shift", lambda s: s.abs().max()),
                                    esc_shift=("esc_shift", lambda s: s.loc[s.abs().idxmax()] if s.notna().any() else np.nan))
        tb = b.join(g, how="inner").dropna(subset=["novelty", "novelty_topic", "esc_shift_abs"])
        key_hours = tb.index.tz_convert("America/New_York").strftime("%Y-%m-%d %H")
        famous = np.isin(key_hours, ["2025-10-10 10", "2025-04-09 12", "2025-10-10 11", "2025-04-09 13"])
        for label, data in [("all", tb), ("without 10 Oct + 9 Apr", tb[~famous])]:
            r = smf.ols("absz ~ novelty + novelty_topic + esc_shift_abs + C(hour)", data=data).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(data["date"])[0]})
            big = (data["absz"] > 2).astype(int)
            for term in ["novelty", "novelty_topic", "esc_shift_abs"]:
                auc = roc_auc_score(big, data[term]) if 0 < big.sum() < len(big) else np.nan
                rows.append({"asset": asset, "sample": label, "term": term, "coef": r.params[term],
                             "ci_low": r.conf_int().loc[term, 0], "ci_high": r.conf_int().loc[term, 1],
                             "p": r.pvalues[term], "AUC_big_hour": auc, "bars": int(r.nobs),
                             "big_hours": int(big.sum())})
        if asset == "SPY":
            for term in ["novelty_topic", "esc_shift_abs"]:
                pct = tb[term].rank(pct=True)
                for h in ["2025-10-10 10", "2025-04-09 12"]:
                    sel = key_hours == h
                    if sel.any():
                        ranks.append(f"  {h}:00 ET  {term} = {tb.loc[sel, term].iloc[0]:.2f} "
                                     f"(higher than {pct[sel].iloc[0]:.0%} of SPY tariff hours)")
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "surprise_test.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(3).to_string(index=False))
    print("\nWhere the two famous hours rank:")
    print("\n".join(ranks))


def main() -> None:
    o = score_posts()
    o[["id", "created_utc", "text", "tariff", "novelty", "novelty_topic", "esc", "esc_shift"]].to_parquet(
        OUT / "post_scores.parquet")
    print(f"scored {len(o):,} original posts -> data/processed/post_scores.parquet")
    print(o[["novelty", "novelty_topic", "esc", "esc_shift"]].describe().round(2).to_string(), "\n")
    test(o)


if __name__ == "__main__":
    main()
