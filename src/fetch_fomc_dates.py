"""Official FOMC meeting dates (federalreserve.gov), 2015 -> latest published schedule.

Decision day = last day of the meeting (statement 14:00 ET, chair press conference 14:30).
Unscheduled meetings (e.g. March 2020) are kept and flagged: they ARE surprises.
Notation votes are dropped (no meeting, no press conference).

Also the chair's semiannual Monetary Policy Report testimony (2 days: House + Senate),
read from the testimony links on the MPR page (dates are in the URLs, e.g. powell20250211a).

    .venv\\Scripts\\python src/fetch_fomc_dates.py   -> data/events/fomc_meetings.csv, fed_testimony.csv
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "events" / "fomc_meetings.csv"
OUT_TESTIMONY = ROOT / "data" / "events" / "fed_testimony.csv"
BASE = "https://www.federalreserve.gov/monetarypolicy/"
HEADERS = {"User-Agent": "Mozilla/5.0 (research script)"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], start=1)}


def decision_day(year: int, month_txt: str, days_txt: str) -> pd.Timestamp:
    """'April/May' + '30-1' -> May 1; 'March' + '17-18*' -> Mar 18; 'March' + '15' -> Mar 15."""
    month = month_txt.split("/")[-1].strip()
    day = re.findall(r"\d+", days_txt)[-1]
    mnum = next(v for k, v in MONTHS.items() if k[:3].lower() == month[:3].lower())
    return pd.Timestamp(year=year, month=mnum, day=int(day))


def current_page() -> list[dict]:
    html = requests.get(BASE + "fomccalendars.htm", headers=HEADERS, timeout=60).text
    rows = []
    for block in re.split(r'<h4><a id="\d+">', html)[1:]:
        year = int(block[:4])
        for m, d in re.findall(r'fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
                               block, flags=re.S):
            if not re.search(r"\d", d) or "notation" in d.lower():
                continue
            if not re.fullmatch(r"\s*[\d\-]+\*?\s*", d):
                print(f"    note: {year} {m} -> {d.strip()!r}")
            rows.append({"decision_day": decision_day(year, m, d), "unscheduled": "unscheduled" in d.lower(),
                         "source": "fomccalendars"})
    return rows


def historical_page(year: int) -> list[dict]:
    html = requests.get(BASE + f"fomchistorical{year}.htm", headers=HEADERS, timeout=60).text
    rows = []
    for title in re.findall(r'panel-heading--shaded">([^<]+)', html):
        m = re.match(r"\s*([A-Za-z/]+)\s+([\d\-]+)\s+(\(?unscheduled\)?\s+)?(Meeting|Conference Call)", title, flags=re.I)
        if not m:
            continue
        rows.append({"decision_day": decision_day(year, m.group(1), m.group(2)),
                     "unscheduled": bool(m.group(3)) or m.group(4).lower() == "conference call",
                     "source": f"fomchistorical{year}"})
    return rows


def main() -> None:
    rows = current_page()
    have = {r["decision_day"].year for r in rows}
    for y in range(2015, min(have)):
        rows += historical_page(y)
    df = (pd.DataFrame(rows).drop_duplicates("decision_day").sort_values("decision_day"))
    df = df[df.decision_day <= pd.Timestamp.today().normalize()]   # past meetings only
    df.to_csv(OUT, index=False)
    print(df.groupby(df.decision_day.dt.year).agg(meetings=("decision_day", "size"),
                                                  unscheduled=("unscheduled", "sum")).to_string())
    print(f"saved {OUT.relative_to(ROOT)}")
    html = requests.get(BASE + "publications/mpr_default.htm", headers=HEADERS, timeout=60).text
    t = sorted({(n, pd.Timestamp(d)) for n, d in re.findall(r"testimony/([a-z]+)(20\d{6})", html)}, key=lambda x: x[1])
    tdf = pd.DataFrame(t, columns=["chair", "testimony_day"])
    tdf = tdf[tdf.testimony_day >= "2015-01-01"]
    tdf.to_csv(OUT_TESTIMONY, index=False)
    print(f"saved {OUT_TESTIMONY.relative_to(ROOT)}: {len(tdf)} testimonies, "
          + ", ".join(f"{c} {g.testimony_day.min():%Y}-{g.testimony_day.max():%Y}" for c, g in tdf.groupby("chair", sort=False)))


if __name__ == "__main__":
    main()
