"""Forward collector (Q3: which outlets are fastest). Run every ~10 min (GitHub Actions).

Every run polls ~40 free sources, and logs each NEW item once with:
  first_seen_utc  when THIS collector first saw it (our clock; resolution = run interval)
  published_utc   the time the source itself claims (finer, but self-reported)
  source, group, title, people (watchlist names found in the title), query, id
RSS keeps no history, so this only works going forward: the longer it runs, the better Q3
gets. It also gives us the "origin" clock for Q2 (Fed / White House / SEC feeds = t0).

No keys, no AI, standard library + requests + feedparser only (fast to install in CI).
Output (CSV, append-only, one file per UTC day; git-friendly):
  <COLLECTOR_DIR>/items/YYYY-MM-DD.csv     new headlines/posts
  <COLLECTOR_DIR>/runs/YYYY-MM.csv         one row per source per run (status, counts, timing)

    .venv\\Scripts\\python src/collect.py              # COLLECTOR_DIR defaults to data/collector
"""
from __future__ import annotations

import calendar
import csv
import datetime as dt
import hashlib
import os
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("COLLECTOR_DIR", ROOT / "data" / "collector"))
HEADERS = {"User-Agent": "Mozilla/5.0 (market-sentiment research collector)"}
FIELDS = ["first_seen_utc", "published_utc", "source", "group", "query", "people", "title", "link", "id"]

# (name, group, url). group: wire / us_outlet / official / indonesia / crypto / social
FEEDS = [
    ("cnbc_top", "us_outlet", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("cnbc_markets", "us_outlet", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
    ("marketwatch_top", "us_outlet", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("wsj_markets", "us_outlet", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"),
    ("nyt_business", "us_outlet", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("ft_home", "us_outlet", "https://www.ft.com/rss/home"),
    ("bbc_business", "us_outlet", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("guardian_business", "us_outlet", "https://www.theguardian.com/uk/business/rss"),
    ("investing_news", "us_outlet", "https://www.investing.com/rss/news.rss"),
    ("seekingalpha_currents", "us_outlet", "https://seekingalpha.com/market_currents.xml"),
    ("benzinga", "us_outlet", "https://www.benzinga.com/feed"),
    ("coindesk", "crypto", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("fed_press", "official", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("fed_speeches", "official", "https://www.federalreserve.gov/feeds/speeches.xml"),
    ("whitehouse", "official", "https://www.whitehouse.gov/news/feed/"),
    ("sec_press", "official", "https://www.sec.gov/news/pressreleases.rss"),
    ("cnbc_indonesia", "indonesia", "https://www.cnbcindonesia.com/news/rss"),
    ("cnbc_indonesia_market", "indonesia", "https://www.cnbcindonesia.com/market/rss"),
    ("detik_finance", "indonesia", "https://finance.detik.com/rss"),
    ("antara_ekonomi", "indonesia", "https://www.antaranews.com/rss/ekonomi.xml"),
    ("reddit_wsb", "social", "https://www.reddit.com/r/wallstreetbets/new/.rss"),  # best effort: Reddit 429s quickly
]
for t in ["NVDA", "TSLA", "GME", "SPY"]:
    FEEDS.append((f"yahoo_{t}", "us_outlet", f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"))

# Google News search per watchlist person: each item names the outlet that published it,
# so one query covers hundreds of outlets (this is the main Q3 data).
GNEWS = {
    "Donald Trump": ('"Trump" (tariff OR tariffs OR Fed OR stocks OR market)', "en"),
    "Elon Musk": ('"Elon Musk"', "en"),
    "Jensen Huang": ('"Jensen Huang"', "en"),
    "Fed chair": ('"Kevin Warsh" OR "Federal Reserve chair"', "en"),
    "Sam Altman": ('"Sam Altman"', "en"),
    "Scott Bessent": ('"Scott Bessent"', "en"),
    "Howard Lutnick": ('"Howard Lutnick"', "en"),
    "Roaring Kitty": ('"Roaring Kitty" OR "Keith Gill"', "en"),
    "Prabowo Subianto": ("Prabowo", "id"),
    "Purbaya": ("Purbaya", "id"),
}
STOCKTWITS = ["NVDA", "TSLA", "GME", "SPY", "BTC.X"]

# watchlist names searched in every title (case-insensitive)
PEOPLE_RE = {
    "Donald Trump": r"\btrump\b", "Elon Musk": r"\bmusk\b", "Jensen Huang": r"\bjensen\b|\bhuang\b",
    "Fed chair": r"\bwarsh\b|\bpowell\b|\bfed chair", "Sam Altman": r"\baltman\b",
    "Scott Bessent": r"\bbessent\b", "Howard Lutnick": r"\blutnick\b",
    "Roaring Kitty": r"roaring kitty|keith gill", "Prabowo Subianto": r"\bprabowo\b",
    "Purbaya": r"\bpurbaya\b",
}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t: dt.datetime | None) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else ""


def people_in(text: str) -> str:
    return ";".join(p for p, rx in PEOPLE_RE.items() if re.search(rx, text, flags=re.I))


def item_id(source: str, key: str) -> str:
    return hashlib.sha1(f"{source}|{key}".encode()).hexdigest()[:16]


def parse_feed(name: str, group: str, content: bytes, query: str = "") -> list[dict]:
    rows = []
    for e in feedparser.parse(content).entries:
        title = re.sub(r"\s+", " ", e.get("title", "")).strip()
        if not title:
            continue
        st = e.get("published_parsed") or e.get("updated_parsed")
        pub = dt.datetime.fromtimestamp(calendar.timegm(st), dt.timezone.utc) if st else None
        link = e.get("link", "")
        src = name
        if name.startswith("gnews"):
            # Google News: the real outlet is in <source>; its links are long redirects, drop them
            outlet = (e.get("source") or {}).get("title", "")
            src = f"gnews:{outlet}" if outlet else name
            title = re.sub(r"\s+-\s+" + re.escape(outlet) + r"$", "", title) if outlet else title
            link = (e.get("source") or {}).get("href", "")
        rows.append({"published_utc": iso(pub), "source": src, "group": group, "query": query,
                     "people": people_in(title), "title": title[:300], "link": link[:300],
                     "id": item_id(src, e.get("id") or e.get("link") or title)})
    return rows


def stocktwits(symbol: str, content: bytes) -> list[dict]:
    import json
    rows = []
    for m in json.loads(content).get("messages", []):
        body = re.sub(r"\s+", " ", m.get("body", ""))
        body = re.sub(r"@\w+", "@user", body)  # data branch is public: don't republish handles
        senti = ((m.get("entities") or {}).get("sentiment") or {}) or {}
        rows.append({"published_utc": m.get("created_at", ""), "source": "stocktwits", "group": "social",
                     "query": symbol, "people": people_in(body),
                     "title": (f"[{senti.get('basic')}] " if senti.get("basic") else "") + body[:280],
                     "link": "", "id": item_id("stocktwits", str(m.get("id")))})
    return rows


def seen_ids(days: list[str]) -> set[str]:
    ids: set[str] = set()
    for d in days:
        f = OUT / "items" / f"{d}.csv"
        if f.exists():
            with f.open(encoding="utf-8", newline="") as fh:
                ids.update(r["id"] for r in csv.DictReader(fh))
    return ids


def append(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def main() -> None:
    run_at = now_utc()
    today, yday = run_at.date().isoformat(), (run_at.date() - dt.timedelta(days=1)).isoformat()
    seen = seen_ids([yday, today])
    jobs = [(n, g, u, "", "rss") for n, g, u in FEEDS]
    for person, (q, lang) in GNEWS.items():
        gl, ceid = ("ID", "ID:id") if lang == "id" else ("US", "US:en")
        url = f"https://news.google.com/rss/search?q={quote_plus(q + ' when:1d')}&hl={lang}&gl={gl}&ceid={ceid}"
        jobs.append((f"gnews_{person}", "aggregator", url, person, "rss"))
    for s in STOCKTWITS:
        jobs.append((f"stocktwits_{s}", "social", f"https://api.stocktwits.com/api/2/streams/symbol/{s}.json", s, "stocktwits"))

    new_rows, run_rows = [], []
    for name, group, url, query, kind in jobs:
        t0 = time.time()
        status, n, n_new = "", 0, 0
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            status = str(r.status_code)
            if r.ok:
                rows = stocktwits(query, r.content) if kind == "stocktwits" else parse_feed(name, group, r.content, query)
                n = len(rows)
                for row in rows:
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        row["first_seen_utc"] = iso(run_at)
                        new_rows.append(row)
                        n_new += 1
        except Exception as e:  # one dead source must not stop the run
            status = e.__class__.__name__
        run_rows.append({"run_utc": iso(run_at), "source": name, "status": status, "items": n,
                         "new": n_new, "seconds": round(time.time() - t0, 2)})
        time.sleep(0.3)
    append(OUT / "items" / f"{today}.csv", FIELDS, new_rows)
    append(OUT / "runs" / f"{today[:7]}.csv", ["run_utc", "source", "status", "items", "new", "seconds"], run_rows)
    bad = [r["source"] for r in run_rows if r["status"] != "200"]
    print(f"{iso(run_at)}: {len(new_rows)} new items from {len(run_rows)} sources"
          + (f"; failed: {', '.join(bad)}" if bad else ""))


if __name__ == "__main__":
    main()
