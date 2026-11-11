# PROGRESS: read this first in a new chat

_Last updated 2026-11-11 (session 1 continued). Update at the end of every session. Background: `RESEARCH_PLAN.md` (questions, methods, data sources, limitations), `JOURNAL.md` (dev log)._

## 0. Where things stand (start here)

- **Session 1 done: design only.** Folder scaffolded, research plan written, 12 seed events listed (unverified), 19 people to track (`data/events/people.csv`), analysis toolkit (RESEARCH_PLAN §8) and the usable pipeline (§9) designed. `git init` on `main`, nothing committed.
- **Truth Social archive in + first all-posts study + Q4a desensitisation test done** (§5). Text-only surprise score built and tested: **mostly a dead end** (§5). Pivoted to detect-then-follow; the after-shock study is done (§5): **no reliable bounce-back; Trump shocks tended to keep going, but only 13 SPY events**. Next: more events (other people, minute data), and/or start the forward collector so the sample grows. Still unknown: what changed around Feb 2026.
- **Forward collector built and tested locally, NOT live yet** (§4): needs a GitHub repo + push (user's call: public = every 10 min free, private = every 30 min).
- **Wider watchlist done (daily, 10 years, Wikipedia attention spikes, §5).** GDELT blocked this machine's IP, so attention = mobile Wikipedia page views instead. Prabowo→IHSG, Roaring Kitty→GME, Fed chair→SPY/TLT and Huang→NVDA pass; Musk, Altman, Lutnick, Purbaya and the Taylor Swift control don't; Bessent was only the tariff week.
- **Building started:** `.venv` created (Python 3.13), daily prices fetched for benchmarks + seed tickers, and the seed events checked against prices (§5). Event *times* are still unverified.
- Named `market-sentiment` (not stock-sentiment) because it covers indices and FX too, not just stocks.
- **Ask before committing or pushing.**

## 1. How to work on this project

- Write in plain words and in the owner's own voice (JOURNAL entries are theirs). Give UI/setup steps **one at a time**. Report as "finding → question for you".
- **Focus is the influential people, not the markets** (user, 2026-11-10). Frame findings around people ("who moves markets"), with markets as the measuring stick.
- Their motivation (own words in `RESEARCH_PLAN.md`): Trump/Prabowo speeches, CEO scandals (Jensen Huang), celebrities move markets short-term; they know they can't beat quants.
- **Wants to actually use the pipeline, and it must be free and not dependent on paid AI.** Lexicons (VADER, Loughran-McDonald, GDELT tone) are the default. Local FinBERT is an optional comparison.
- **The user is interested in the models and methods themselves.** Explain *why* each tool is used when introducing it (they asked for this).
- Running joke: "this is not financial advice 😛".

## 2. Questions (full detail in RESEARCH_PLAN.md)

| | Question | Method | Status |
|---|---|---|---|
| Q1 | Which people and events move markets? | Event study (abnormal returns) on complete event sources + placebo times | first answers: Trump tariffs (hourly), Fed chair, Prabowo, Roaring Kitty (daily) |
| Q2 | First report → price move → consensus: how long? | Three clocks: origin t0, price (1-min), diffusion (GDELT/RSS counts) | daily: price moves same day or before; public attention lags ~0–1 day |
| Q3 | Fastest outlets and apps | Forward-only collector logging first_seen per source | collector built, not live yet (needs weeks of running) |
| Q4 | Desensitisation, overreaction and reversal, tone vs attention, Indonesia vs US, does Reddit lead or lag | | not started |

## 3. Key decisions and constraints

- **Selection bias is the main trap.** Use every speech or post from a source, never just the famous ones. The seed list is for testing the pipeline only.
- Free data: yfinance (daily, any market), Alpaca free (US 1-min, IEX feed only), GDELT (news + tone), trumpstruth.org / Hugging Face (Truth Social), UCSB (speeches), Reddit API, RSS, Telegram.
- **Not free:** X/Twitter (pay-per-use since Feb 2026, ~$0.005/post read), consolidated real-time feeds, old IDX minute data. Indonesian intraday data must be archived going forward (yfinance only keeps recent 1-min).
- Q3 needs an always-on collector. Plan: GitHub Actions cron (free, ~5–15 min resolution) or a free VM later.

## 4. Code and pipeline

```bash
.venv\Scripts\python src/fetch_prices.py          # yfinance daily since 2015 -> data/raw/prices/<ticker>.parquet (skips if fetched today; --force, --tickers)
.venv\Scripts\python src/verify_seed_events.py    # seed events -> data/processed/seed_event_check.csv
.venv\Scripts\python src/fetch_prices.py --hourly   # + hourly bars for SPY QQQ BTC-USD ^JKSE IDR=X -> data/raw/prices_1h/ (MERGES: run regularly, yfinance only serves ~730 days)
.venv\Scripts\python src/fetch_truth_social.py      # CNN archive -> data/processed/truth_posts.parquet (--offline to rebuild from cache)
.venv\Scripts\python src/post_hour_study.py         # topic-tagged posts vs hourly |z| -> post_hour_summary.csv, post_hour_regression.csv
.venv\Scripts\python src/surprise_score.py          # TF-IDF novelty + escalation words per post -> post_scores.parquet, surprise_test.csv
.venv\Scripts\python src/after_shock.py             # follow-through after big post hours vs no-post big hours -> after_shock.csv
.venv\Scripts\python src/fetch_gdelt.py             # GDELT news timelines for 10 watchlist people -> gdelt_daily/hourly.parquet, gdelt_spike_days.csv (cached in data/raw/gdelt, resumable; SLOW, rate-limited)
.venv\Scripts\python src/person_news_study.py       # (needs GDELT data; NOT RUN yet) news-spike onsets vs hourly |z|, placebo p + BH; lead/lag
.venv\Scripts\python src/fetch_wiki_attention.py    # daily MOBILE Wikipedia views since 2015-07 for 10 watchlist people -> wiki_views.parquet (cached in data/raw/wiki)
.venv\Scripts\python src/collect.py                 # forward collector, one poll of ~40 free sources -> data/collector/items/YYYY-MM-DD.csv (+ runs/YYYY-MM.csv)
.venv\Scripts\python src/collect_minute.py          # archive 1-min bars (yfinance keeps ~7 days) -> data/collector/minute/<ticker>/YYYY-MM-DD.csv
.venv\Scripts\python src/fetch_fomc_dates.py        # official FOMC decision days (+2 emergency 2020) and semiannual testimony dates (federalreserve.gov) -> data/events/fomc_meetings.csv, fed_testimony.csv
.venv\Scripts\python src/fed_split.py               # Fed chair spikes split: FOMC / testimony / Jackson Hole / surprise / market-led -> fed_split_*.csv
.venv\Scripts\python src/person_attention_study.py  # attention spikes vs daily abnormal |z| of each person's assets, placebo p, drop-top-2, BH, lead/lag -> person_attention_*.csv
.venv\Scripts\python src/desensitisation.py         # Q4a: tariff premium by stage + regression on nth/gap/concrete -> desensitisation_*.csv
```
- **Truth Social source:** CNN's public archive `https://ix.cnn.io/data/truth-social/truth_archive.json` (free, refreshed every few minutes). 38,003 posts, 14 Feb 2022 → now. Kinds: 22,776 original, 7,567 repost, 7,658 media-only. Timestamps verified against Mastodon post IDs (ID >> 16 = ms): all within 1 s. Quiet Feb–Apr 2022 is real (he barely posted), not a gap. Some text was double-encoded (fixed; 11 still garbled). Only 29% of posts fall in US market hours.
- **Topic tags = keyword regexes** in `post_hour_study.py` (tariff, fed, market, china, company, crypto), original posts only. Coarse: "company" is mostly political (Google/elections, JPMorgan lawsuit), not market news.
- **GDELT DOC API** (`fetch_gdelt.py`): free, no key, but **very strict rate limit** (asks 1 req / 5 s; in practice 429s for minutes after any burst, sometimes connection timeouts). So: one daily-resolution request per person for Nov 2024 → Nov 2026 → spike days (share ≥ 3× trailing 30-day median, top 15, ≥ 3 days apart) → hourly 4-day windows only around spikes. ~160 requests, 12 s pacing + exponential back-off, every response cached in `data/raw/gdelt/`. Counts are converted to share of all monitored articles (value / norm). A 1-week window returns hourly resolution (confirmed). Queries are in `QUERIES` in the script. Fed chair query = Powell OR Warsh (verify who the chair is). Spike rule lowered to 2× (3× gave Musk 2 days in 2 years). **Status 2026-11-11: GDELT returns 429 to every request from this machine, even tiny ones, for over a day** (its message: high-traffic users should use the ngrams bulk dataset). Only Musk's daily series + 1 hourly window are cached. Retry later or from another network; until then use Wikipedia.
- **Forward collector** (`collect.py`, `collect_minute.py`, `.github/workflows/collect.yml`): GitHub Actions cron every 10 min (feeds) + 23:30 UTC daily (minute bars). Output is committed to a separate orphan branch **`collector-data`** (on main, `data/collector/` is gitignored; locally it's a plain folder). Stdlib + requests + feedparser only for the feeds job (fast CI install).
  - Sources that worked (2026-11-11): CNBC top/markets, MarketWatch top, WSJ markets, NYT business, FT, BBC business, Guardian business, Investing.com, Seeking Alpha currents, Benzinga, CoinDesk, Yahoo per-ticker (NVDA TSLA GME SPY), **official**: Fed press + speeches, White House, SEC; **Indonesia**: CNBC Indonesia news + market, Detik Finance, Antara ekonomi; **Google News search per watchlist person** (10 queries, `when:1d`; the `<source>` tag names the real outlet: 297 outlets in the first run); StockTwits public JSON (NVDA TSLA GME SPY BTC.X, no key); Reddit r/wallstreetbets RSS best-effort (Reddit 429s a 2nd request; may be blocked from GitHub IPs). Dead/blocked: CNN money RSS (stale since 2018), MarketWatch pulse (stale), Yahoo index (404), Kontan (empty), Bisnis (403), Kompas (404), Bluesky search (403).
  - Fields: first_seen_utc (our clock, resolution = cron interval, and GitHub delays crons at busy times), published_utc (source's own claim), source (`gnews:<outlet>` for Google News), group, query, people (regex on title), title, link, id (sha1 of source + guid). Dedup against today's + yesterday's ids. **The first run's items are backlog: their first_seen is meaningless.** For Q3 use items published after the source's previous successful poll (runs log).
  - Minute bars: SPY QQQ NVDA TSLA GME TLT MSFT ^JKSE IDR=X BTC-USD, one CSV per ticker per complete UTC day, skips days already saved (catches up within 7 days). ^JKSE ~320 bars/day (works!), IDR=X only ~30/day (thin). ~2.2 MB/week.
  - GitHub disables scheduled workflows after 60 days without repo activity; the data commits should count, but check.
- **Wikipedia attention** (`fetch_wiki_attention.py`): REST pageviews API, free, no key, gentle 429s (retry + cache). **Mobile views only** (mobile-web + mobile-app): undetected bots show up as desktop traffic (Altman's 'record' 12 Jun 2025 was ~500k desktop vs ~8k mobile; real spikes like Huang Nov 2026 are mostly mobile). Fed chair = Yellen (only up to 4 Feb 2018: later she's Treasury Secretary) + Powell + Warsh pages (Warsh testified as chair in July 2026, per federalreserve.gov); Prabowo = en + id wiki; Purbaya = id wiki only. Spike = views ≥ 3× trailing 30-day median AND ≥ the person's 90th percentile, ≥ 5 days apart. Daily study: market model vs SPY (window t−130..t−11) for single stocks, raw returns for SPY/TLT/^JKSE/IDR/BTC; day 0 = first trading day on/after the UTC spike day; response = max |z| on day 0/+1.
- Hourly archive now also has TSLA NVDA SMH TLT GME MSFT (`INTRADAY` in fetch_prices.py).
- Hourly method: bar return = close/open (no overnight gap), z = return / std of the previous 70 bars, regression |z| ~ topic flags + any_post + hour-of-day, SEs clustered by date. Also the next bar.
- Prices keep both `close` (raw) and `adj_close` (dividend/split adjusted). **Returns always use adj_close.** The raw close is there to catch ex-dividend drops (Ronaldo).
- `verify_seed_events.py` is the rough daily version of §8.1: market model (vs SPY, or ^JKSE for Indonesia) fit on 120 days ending 10 days before; index targets use their own mean. z = AR / residual sd; p_emp = share of the previous 250 days with |AR| at least as big. Day 0 = next trading day if time_et ≥ 16:00.
- Set `PYTHONIOENCODING=utf-8` on Windows.

Research scripts still to write: `RESEARCH_PLAN.md` §6. **The usable pipeline the user wants (§9):** ingest (weekly/on demand + light always-on collector) → rule-based event table → abnormal returns + placebo p-values → significance filter (bootstrap CI + Benjamini–Hochberg FDR) → `watchlist.csv` → predict move/range/window for new watchlist events → Telegram alert + paper-trade log. Retrain weekly, walk-forward only.

**Models agreed (§8):** market-model OLS for expected return; CAR; permutation/placebo test; bootstrap CI; BH-FDR; multiple regression on |CAR| and CAR with date-clustered SEs + VIX control (each Q4 question = one coefficient); Granger causality for Reddit lead/lag; Lasso / gradient boosting + SHAP for exploration only, confirmed on a later time period; logistic S-curve for news diffusion; calibrated logistic regression / GBM + quantile regression for prediction; backtest with costs, then Alpaca paper trading.

## 5. Findings so far

**Seed event check (daily, 12 events, rough; not the real sample):**
- Huge and clear: Liberation Day (SPY −4.9% day 0, −10.8% over 2 days), tariff pause (+10.5%, z 11.6), Huang quantum (IONQ/RGTI/QBTS −36 to −45%), DeepSeek (NVDA −13% abnormal), Musk "funding secured" (+10.6%, z 3.9), IHSG halt day (−3.8%).
- **Not significant at the daily level:** Ronaldo/Coke (adj −0.45%, p 0.58; the raw −1.1% was the ex-dividend date: **myth confirmed**), Intel CEO post (z −0.9; then +12.5% over 5 days on other news), Powell Jackson Hole 2025 (z 0.9), Sri Mulyani day 0 (z −1.0, but day +1 −1.95%, so the timing is probably after the close). Kylie/Snap borderline (z −1.9, p 0.08).
- Reversal hints (Q4b): IONQ bounced +10.9% the next day; NVDA +6.6% the next day after DeepSeek. RGTI/QBTS did NOT bounce.

**All Trump posts vs hourly prices (first pass, Dec 2023/Nov 2024 → Nov 2026):**
- **A random post does nothing.** Hours with a post ≈ hours without (SPY effect −0.007 |z|, 95% CI ±0.05). He posts too much for "Trump posted" to mean anything.
- **Tariff posts:** hours ~18% more volatile in SPY/QQQ (+0.13 |z|, p ≈ 0.13, not significant alone) and **+0.17 in Bitcoin (p = 0.01)**. Big hours (|z| > 2): SPY 9.8% vs 6.3% baseline, BTC 11.9% vs 6.0%. **Driven by a handful of posts**: 10 Oct 2025 10:57 ET China post (SPY hour z −10.7) and 9 Apr 2025 13:18 pause post (z +7.3). Most of the 461 tariff posts are repeats that do nothing → points to Q4a (desensitisation) and a "new information" flag.
- **No spill-over into the next hour** for any topic: whatever happens, happens within the hour (fits "it's fast", Q2).
- Fed / market / china: positive but noisy, not significant. "Company" hours were *calmer* (p < 0.01, survives Benjamini-Hochberg over the 42 tests), probably because those posts are political, not market news. Unexplained; don't over-read.

**Q4a: does the market get used to tariff posts? (`desensitisation.py`)**
- **No steady 'getting used to it'.** Regression on 132 SPY / 353 BTC tariff hours: nth post, hours since the last one, and a 'concrete' flag (%/$ figure, 'effective', 'pause', deadline) are all non-significant.
- **Instead a rise-and-fall regime.** Extra |z| vs no-post hours, 4 equal stages: SPY −0.02 (Dec 2023–Apr 2025) → +0.27 (Apr–Jul 2025) → **+0.55 (Jul 2025–Feb 2026, CI 0.06–1.28; 21% big hours)** → −0.02 (Feb–Oct 2026, 0 big hours out of 33). BTC is the same shape. Tariff posts mattered while they carried real policy power and stopped mattering around Feb 2026. **Why Feb 2026 is unknown**: find out (court rulings? deals done? ask the user).
- The biggest one (10 Oct 2025, z −10.7) was NOT 'concrete' by the rule: a surprise escalation after a calm stretch. **What matters looks like surprise vs expectation, not count or specificity.** Next proxy (no AI): novelty = TF-IDF cosine similarity to his previous ~50 posts, plus escalation/de-escalation word lists.
- Tagging false positive found: 4 Apr 2024 (z −4.3) was a Breitbart link that mentioned tariffs; the move was probably unrelated. Keyword tagging + coincidence = false hits, so the significance filter must look at many posts, never one.

**Surprise score (`surprise_score.py`): mostly a dead end.**
- Scores per original post: novelty = 1 − max TF-IDF cosine vs his previous 50 posts; novelty_topic = same vs previous 20 tariff posts; esc_shift = (escalation − de-escalation word counts) minus his recent tariff average. The word lists were written after reading the famous posts, so every test is also run without 10 Oct + 9 Apr.
- **Results:** general novelty: nothing (slightly negative). esc_shift: 10 Oct ranks in the 98th percentile, but drop the two famous hours and the effect is gone (SPY +0.07, n.s.). It was tuned to them. novelty_topic: small, real-ish effect in **Bitcoin only** (+0.95 |z| per unit, p 0.02, survives dropping the famous hours), but **AUC ≈ 0.53** for spotting big hours, so it's useless as a filter.
- **Why:** his posts are almost always 'novel' (median 0.88). What surprises the *market* is relative to what the market expects (e.g. 10 Oct came during a China truce), and that context isn't in his words. Plus only 11 big SPY tariff hours to learn from.
- **Implication for the pipeline:** don't try to predict the first move from text. **Detect it instead** (price jumps > kσ within minutes of a watchlist person's post) and answer 'what usually happens next' (drift vs bounce over hours/days). That matches the earlier limit (§9: the first move takes minutes). Optional later: context features (GDELT topic volume in the previous 24 h, VIX).

**After the shock (`after_shock.py`): keep going or bounce back?**
- Events = big hours (|z| > 2) containing a post, biggest per day only. Follow-through = return from the end of that hour, signed by the first move (+ = kept going). Control = big hours with no post.
- **Ordinary big hours (control) slightly bounce back:** SPY −0.17% after 1 day, −0.30% after 5 days (CIs just touch 0), 147 events. Normal mean reversion.
- **Trump tariff big hours did the opposite, if anything: kept going.** SPY +0.48% after 1 day, +1.09% after 5 days (CI −0.06 to +2.61), 62% kept going after 5 days. QQQ similar. **But n = 13**, and the week of 7–9 Apr 2025 does much of the work: without those two, 5-day mean is +0.36%. BTC (38 events): no pattern at all.
- **Verdict:** no evidence of an overreaction to fade (the 'buy the dip after a Trump post' idea fails). Weak, unproven hint that Trump shocks are 'real news' that keeps moving. ~6 such events per year in SPY, too rare for a trading rule on their own. For the pipeline this is more 'don't blindly buy the dip' than a trade signal.
- **Method issue found:** the "normal volatility" baseline can include earlier shocks (the Oct 2025 China post had z only −2.0, because the fit window contained the April 2025 crash). Fix later: volatility estimate that adapts (EWMA/GARCH) or exclude known event days from the baseline.

**Wider watchlist: Wikipedia attention spikes vs daily moves (`person_attention_study.py`, 2015→2026)**
- Placebo = 2,000 random day sets; drop-top-2 = same test without the 2 biggest events (and each placebo set's 2 biggest); BH over 17 tests.

| Person → asset | events | response vs normal day | p | p drop-top-2 | p BH | read |
|---|---|---|---|---|---|---|
| Fed chair → SPY | 129 | 1.48× | <0.001 | <0.001 | 0.008 | real, but it is surprising FOMC meetings + crashes: see Fed split below |
| Fed chair → TLT | 129 | 1.17× | 0.003 | 0.002 | 0.025 | same |
| Roaring Kitty → GME | 20 | 1.91× | 0.007 | 0.018 | 0.042 | real, but **price moves first** (day −1 big in 20%; May 2024: GME z +16 the day before the attention peak) |
| Prabowo → IHSG | 23 | 1.49× | 0.012 | 0.001 | 0.053 | robust; peak on **day +1** (Jakarta closes before the US-time news day). Elections 2019/2024, etc. |
| Huang → NVDA | 28 | 1.35× | 0.042 | 0.005 | 0.13 | but |z| is already high days −4..−1 → **attention follows NVDA** (earnings, crashes), not the other way |
| Bessent → SPY | 27 | 1.37× | 0.045 | **0.42** | 0.13 | **only the tariff week** (3 + 9 Apr 2025) = Trump, not Bessent |
| Musk → TSLA / BTC | 48 | 1.14× | 0.12 / 0.15 | ~0.09 | 0.3 | weak at best: he's always in the news |
| Altman → MSFT/NVDA, Lutnick → SPY, Purbaya → IHSG/IDR, Prabowo → IDR, Huang → SMH, Bessent → TLT | | ~1.0× | >0.3 | | >0.6 | nothing |
| **Taylor Swift (control) → SPY** | 52 | **1.00×** | 0.46 | | 0.64 | control passes: the method doesn't find effects everywhere |

- **Q2 (daily answer):** for market people the market usually moves **on or before** the day public attention peaks (GME, NVDA, Fed: elevated on day −1). Public 'consensus' (people looking someone up) lags the price by ~0–1 day. For Prabowo/IHSG the market reacts the next Jakarta session, which is a time-zone effect, not slowness.
- **So who moves markets?** Policy people with real power (Fed chair, Trump via tariffs, Prabowo for Indonesia) and the one meme-stock figure. CEOs (Huang, Altman) and Musk mostly *get attention because of* market moves, at least at daily level. Lutnick/Bessent/Purbaya: nothing on their own.
- Caveats: attention ≠ the person saying something (a spike can be news *about* them); daily resolution can't see the minutes-scale first move; Fed spikes are scheduled, so 'surprise' is not separated from 'importance'.

**Fed chair split: calendar or surprise? (`fed_split.py`)**
- 129 Fed-chair attention spikes (after adding Yellen for 2015–Feb 2018), labelled from the official calendar: FOMC ±1 day 47, testimony 14, Jackson Hole 8, other 47, other but SPY already had a big day on day −1 ('market-led') 13.

| Group (SPY) | events | vs random days | p | big day % |
|---|---|---|---|---|
| all FOMC meetings (2015→2026, no attention filter) | 91 | **0.99×** | 0.49 | 14 |
| FOMC meetings **with** an attention spike | 47 | **1.33×** | 0.03 | 26 |
| FOMC meetings **without** a spike | 44 | 0.64× | 1.00 | 2 |
| testimony + Jackson Hole | 22 | 1.07× | 0.32 | 14 |
| other, not market-led (nominations, Trump attacks, speeches) | 47 | **1.00×** | 0.46 | 15 |
| other, market-led (crash first, then people look him up) | 13 | 4.5× | <0.001 | 92 |

- **The average Fed meeting does not move the S&P more than a random day** (daily |z|; the move is priced in or happens within the 2 pm hour and partly reverses). The ones that move it are the ones the public then looks up: attention flags the *surprising* meetings, but at the same time as or after the move, so it's a detector, not a predictor.
- **Off-calendar news about the chair does nothing** on its own (nominations incl. Warsh 30 Jan 2026, Trump's attacks, 'will he be fired'): ratio 1.00. The original 'Fed chair' result was the meetings plus the crashes (Feb 2018, Mar 2020, Aug 2024, Apr 2025) where people looked the Fed up *because* markets fell.
- TLT: same pattern, weaker. Some 'other' days are actually scheduled speeches not in the calendar (28 Nov 2018 'just below neutral' speech, 30 Nov 2022 Brookings), so the surprise group is slightly contaminated toward *more* effect; still nothing.
- For the pipeline: Fed days go on a calendar (known in advance); the alert worth having is 'this meeting is drawing unusual attention' (hourly attention would show it during the press conference). Needs hourly data.

## 6. Questions to ask the user (open)

1. ~~Which people to track~~ → user accepted the suggested list (people.csv). Verify the current Fed chair and ID finance minister names.
2. ~~Markets~~ → user cares about the **people**, not markets; let me pick. Decided: US stocks + Indonesia (IHSG, IDR) + Bitcoin (24/7, catches weekend posts). STI only as a later spillover check. RESEARCH_PLAN §7.1.
3. OK to sign up for free Alpaca and Reddit API keys? (Telegram later.)
4. ~~Seed events take~~ → answered: they hadn't heard of *any* of the 12 events, not even afterwards. "This shows having a pipeline which tells me the window will be helpful." Story angle: **the pipeline is for people who don't follow the news**, so alerts must be self-explanatory (who, what, typical move, typical window).

## 7. What's next (in order)

1. Answer §6 with the user. Make the venv (`python -m venv .venv`, `pip install -r requirements.txt`).
2. ~~fetch_prices + seed check~~ done. Still: verify event **times** (to the minute) from sources and set `verified`; ask the user for their takes on the seed results.
3. **Forward collector: built + tested locally (2026-11-11).** To go live: user picks public/private → first commit on main → `gh repo create` → push → run the workflow once by hand → check the `collector-data` branch. Then leave it for weeks; Q3 analysis after ~4 weeks.
4. ~~Truth Social archive + first all-posts study~~ done (hourly). ~~(a) Q4a desensitisation~~ done: regime, not fatigue. ~~(b) novelty/surprise measure~~ done, dead end → pivot to detect-then-follow. ~~(b2) after-shock study~~ done: no bounce, weak keep-going hint, n too small. Next: ~~(b3) other people~~ done daily via Wikipedia (GDELT blocked); still: GDELT hourly when unblocked (Q2 in hours), ~~split Fed scheduled vs unscheduled~~ done, check Huang/NVDA with earnings dates removed, minute bars (Alpaca), and the forward collector (it only gets better with time) (numbers, 'effective', new country, 'pause') vs repeat rants; (c) minute data around the big hours (Alpaca key needed) to time the move (Q2); (d) turn into notebook 01.
5. Q2 timing clocks on the minute-level subset.
6. Lock the plan (like EXPERIMENT.md) before looking at Q4b reversal results.
7. Build the usable pipeline (§9): watchlist → alerts → paper trading. Only after Q1 shows something passes the filter.
