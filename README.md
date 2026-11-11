# market-sentiment

> 🚧 Work in progress. This is not financial advice 😛

Every time Trump or Prabowo gives a speech, it feels like the market drops. Same with CEO scandals and the odd celebrity post. This repo checks whether that's actually true, how fast prices move compared with how fast the news reaches normal people, and which sources get there first.

I'm not trying to beat quants. They react in milliseconds. The interesting question is what's left for someone who reads the news like a normal person.

## Questions

1. Which people and events actually move prices (measured on *every* speech or post, not just the ones I remember)?
2. How long between the first report, the price move, and the moment everyone knows?
3. Which outlets and apps report fastest?
4. Does the market get used to it? Does it overreact and bounce back?

Details: [`RESEARCH_PLAN.md`](RESEARCH_PLAN.md). Dev log, dead ends included: [`JOURNAL.md`](JOURNAL.md).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env            # free keys only, see comments inside
```

Everything runs on free data and free tools. No paid AI APIs.

## Layout

```
src/              scripts (fetching, collector, event study)
notebooks/        analysis, one per question
data/events/      hand-made event lists (tracked)
data/raw/         downloaded data (gitignored)
data/processed/   cleaned tables (gitignored)
```
