"""Download Trump's full Truth Social archive and turn it into a clean table.

Source: CNN's public archive (https://ix.cnn.io/data/truth-social/truth_archive.json),
refreshed by CNN every few minutes, posts from Feb 2022 on. Free, no key.

Output: data/processed/truth_posts.parquet, one row per post:
  id, created_utc, created_et, text (HTML stripped), kind (original / repost / media_only),
  has_media, url, replies, reblogs, likes, id_time_gap_s (sanity check, see below)

Sanity check: Truth Social is built on Mastodon, whose post IDs encode the creation time
(ID >> 16 = milliseconds since 1970). If `created_at` and the ID disagree, the timestamp
was edited or is wrong.

    .venv\\Scripts\\python src/fetch_truth_social.py            # download + build
    .venv\\Scripts\\python src/fetch_truth_social.py --offline  # rebuild from the cached file
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "truth_social" / "cnn_truth_archive.json"
OUT = ROOT / "data" / "processed" / "truth_posts.parquet"
URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"

TAG = re.compile(r"<[^>]+>")
REPOST = re.compile(r"^\s*RT[:\s]|^\s*RT @", re.I)


def download() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=120, headers={"User-Agent": "market-sentiment research script"})
    r.raise_for_status()
    RAW.write_bytes(r.content)
    print(f"downloaded {len(r.content) / 1e6:.1f} MB")


def fix_mojibake(s: str) -> str:
    """Some archive posts are double-encoded ("Worldâ\x80\x99s" instead of "World's")."""
    if "â" not in s and "Ã" not in s:
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s


def clean_text(s: str | None) -> str:
    s = fix_mojibake(TAG.sub(" ", s or ""))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def build() -> pd.DataFrame:
    posts = json.loads(RAW.read_text(encoding="utf-8"))
    df = pd.DataFrame(posts)
    df["created_utc"] = pd.to_datetime(df["created_at"], utc=True, format="ISO8601")
    df["created_et"] = df["created_utc"].dt.tz_convert("America/New_York")
    df["text"] = df["content"].map(clean_text)
    df["has_media"] = df["media"].map(lambda m: bool(m))
    df["kind"] = "original"
    df.loc[df["text"].str.match(REPOST), "kind"] = "repost"
    df.loc[(df["text"] == "") & df["has_media"], "kind"] = "media_only"
    df.loc[(df["text"] == "") & ~df["has_media"], "kind"] = "empty"

    id_ms = df["id"].map(lambda i: int(i) >> 16)
    created_ms = df["created_utc"].dt.as_unit("ms").astype("int64")  # pandas 3 may store us/ms, so be explicit
    df["id_time_gap_s"] = (id_ms - created_ms) / 1000

    df = (df.rename(columns={"replies_count": "replies", "reblogs_count": "reblogs",
                             "favourites_count": "likes"})
            [["id", "created_utc", "created_et", "text", "kind", "has_media", "url",
              "replies", "reblogs", "likes", "id_time_gap_s"]]
            .drop_duplicates("id")
            .sort_values("created_utc")
            .reset_index(drop=True))
    return df


def report(df: pd.DataFrame) -> None:
    print(f"{len(df):,} posts  {df.created_et.min():%Y-%m-%d} -> {df.created_et.max():%Y-%m-%d %H:%M} ET")
    print(df["kind"].value_counts().to_string())
    gap = df["id_time_gap_s"].abs()
    print(f"ID vs created_at: median gap {gap.median():.2f}s, >60s: {(gap > 60).sum()}")
    daily = df.set_index("created_et").resample("D").size()
    zero = daily[daily == 0]
    print(f"days with 0 posts: {len(zero)} of {len(daily)}")
    # Long silent stretches are either real (he wasn't posting) or archive gaps.
    runs, start, prev = [], None, None
    for d in zero.index:
        if prev is not None and (d - prev).days == 1:
            prev = d
            continue
        if start is not None:
            runs.append((start, prev))
        start = prev = d
    if start is not None:
        runs.append((start, prev))
    long_runs = [(a, b) for a, b in runs if (b - a).days >= 6]
    print("silent stretches >= 7 days:", [(f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}") for a, b in long_runs])
    print(df.set_index("created_et").resample("YE").size().rename("posts per year").to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip download, use cached file")
    args = ap.parse_args()
    if not args.offline:
        download()
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    report(df)
    print(f"saved -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
