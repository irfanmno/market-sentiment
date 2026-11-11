"""Public attention per watchlist person = daily Wikipedia page views (free, no key, since 2015-07).

Why Wikipedia and not news counts: GDELT (news counts) blocked this machine after a few
dozen requests. Page views measure something slightly different -- how many people went
to look the person up -- which is closer to "general consensus reaching the public" (Q2)
than "first article published". Limits: daily resolution only (UTC days), and an attention
spike can be CAUSED by a market move (Huang gets looked up because NVDA crashed). The
study checks the day before the spike for exactly that.

Only MOBILE views are used (desktop is where undetected bots live).
Indonesian people use id.wikipedia (+ en for Prabowo), since that's where their public is.

    .venv\\Scripts\\python src/fetch_wiki_attention.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "wiki"
OUT = ROOT / "data" / "processed"
API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{proj}/{acc}/user/{art}/daily/20150701/{end}"
# Mobile only. Undetected bots show up as desktop traffic: Sam Altman's "record" in June 2025
# was ~500k desktop views/day vs ~8k mobile. Real spikes (Musk buying Twitter, Huang Nov 2026)
# are mostly mobile.
ACCESS = ["mobile-web", "mobile-app"]
HEADERS = {"User-Agent": "market-sentiment research script (python-requests)"}

# person -> list of (wiki project, article[, from, to]). Views of all pages are summed;
# optional from/to (inclusive) keep only the days that page counts for that role.
PAGES = {
    "Elon Musk": [("en.wikipedia.org", "Elon_Musk")],
    "Jensen Huang": [("en.wikipedia.org", "Jensen_Huang")],
    # Chair = Yellen until 3 Feb 2018 (her later views are as Treasury Secretary, so clipped),
    # then Powell, then Warsh (chair by the July 2026 testimony).
    "Fed chair": [("en.wikipedia.org", "Janet_Yellen", None, "2018-02-04"),
                  ("en.wikipedia.org", "Jerome_Powell"), ("en.wikipedia.org", "Kevin_Warsh")],
    "Prabowo Subianto": [("en.wikipedia.org", "Prabowo_Subianto"), ("id.wikipedia.org", "Prabowo_Subianto")],
    "Purbaya (ID finance minister)": [("id.wikipedia.org", "Purbaya_Yudhi_Sadewa")],
    "Sam Altman": [("en.wikipedia.org", "Sam_Altman")],
    "Scott Bessent": [("en.wikipedia.org", "Scott_Bessent")],
    "Howard Lutnick": [("en.wikipedia.org", "Howard_Lutnick")],
    "Roaring Kitty": [("en.wikipedia.org", "Keith_Gill")],
    "Taylor Swift (control)": [("en.wikipedia.org", "Taylor_Swift")],
}


def fetch(proj: str, art: str, end: str, acc: str) -> pd.Series:
    path = CACHE / f"{proj.split('.')[0]}_{art}_{acc}_{end}.json"
    if path.exists():
        items = json.loads(path.read_text(encoding="utf-8"))
    else:
        wait = 10
        for _ in range(6):
            r = requests.get(API.format(proj=proj, art=art, end=end, acc=acc), headers=HEADERS, timeout=60)
            if r.status_code != 429:
                break
            print(f"    429, waiting {wait}s"); time.sleep(wait); wait *= 2
        if r.status_code == 404:  # page didn't exist / no views
            return pd.Series(dtype=float)
        r.raise_for_status()
        items = r.json()["items"]
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items), encoding="utf-8")
        time.sleep(2)
    s = pd.Series({pd.Timestamp(i["timestamp"][:8]): i["views"] for i in items}, dtype=float)
    return s


def main() -> None:
    end = (pd.Timestamp.now("UTC") - pd.Timedelta(days=1)).strftime("%Y%m%d")
    rows = []
    for person, pages in PAGES.items():
        total = None
        for proj, art, *clip in pages:
            for acc in ACCESS:
                s = fetch(proj, art, end, acc)
                if clip:
                    s = s.loc[clip[0]:clip[1]]
                total = s if total is None else total.add(s, fill_value=0)
        total = total.asfreq("D", fill_value=0)
        print(f"{person:32s} {len(total)} days {total.index.min():%Y-%m-%d} -> {total.index.max():%Y-%m-%d}, "
              f"median {total.median():,.0f}/day, max {total.max():,.0f} on {total.idxmax():%Y-%m-%d}")
        rows.append(pd.DataFrame({"date": total.index, "person": person, "views": total.to_numpy()}))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.concat(rows).to_parquet(OUT / "wiki_views.parquet", index=False)
    print("saved data/processed/wiki_views.parquet")


if __name__ == "__main__":
    main()
