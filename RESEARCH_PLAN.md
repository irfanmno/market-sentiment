# Research plan

_Drafted 2026-11-10 (session 1). Sections 1–5 are the design and can still change. Lock them, like `cs2-analysis/EXPERIMENT.md`, before any result is looked at._

## The idea (my words, lightly tidied)

> Influential people can heavily affect the market simply by having a speech, e.g. Donald Trump or Prabowo: whenever they have a speech, the market goes down. This extends to celebrities and CEO scandals (e.g. Jensen Huang). Beating day traders and quants is impossible, since they have better equipment and inside information. But unexpected human behaviour can heavily move the market, especially in the short term.

**Honest framing:** I'm not trying to beat HFT, since they react in milliseconds. The questions are:
(a) which people and events actually move prices, and by how much, measured systematically instead of from memory;
(b) how fast the move happens compared with how fast the news spreads to normal people;
(c) whether there is anything left *after* the news has spread, e.g. an overreaction that reverses. That last one is the only place a slow retail person could have an edge. "Not financial advice 😛"

**Trap to avoid (same lesson as CS2 nb05):** "whenever Trump speaks the market goes down" is the kind of memory that selection bias builds. We remember the drops and forget the 50 speeches where nothing happened. So the event list must be **every** speech or post from a source, not the famous ones, and it is compared against **placebo times** (same weekday and time of day, no event).

---

## 1. Q1: Which people and events move the market?

**Method: event study.**
- For each event, t0 = the first public timestamp (to the minute where possible).
- Abnormal return = asset return − expected return (market model: beta × SPY/^JKSE over a pre-window of 60 trading days). For index-level events (a Trump tariff post affects SPY itself), compare against the same time of day on non-event days instead.
- Windows: [t0, +5m], [+30m], [+1h], [close], [+1d], [+5d]. Daily data for old events, minute data where available.
- Also measure **volume and volatility** (|return|, 1-min volume z-score). Some events add uncertainty without a direction.

**Event taxonomy** (the columns we group by):

| Dimension | Values |
|---|---|
| Who | head of state (Trump, Prabowo), central banker (Powell, BI governor), finance minister, CEO, celebrity/influencer |
| Channel | scheduled speech, unscheduled remark/Q&A, social post (Truth Social / X / Instagram), leak/report about them |
| Content | policy (tariffs, tax, fiscal), firing/appointment, company-specific praise/attack, product/tech claim, scandal |
| Scheduled? | yes (FOMC, State of the Union, earnings call) / no |
| Target | broad index, sector, single stock, currency (IDR, USD) |

**Expected from the literature (to confirm or contradict):** scheduled macro events (FOMC, CPI, payrolls) are the biggest and most reliable movers, but they are priced in seconds. Unscheduled *policy* posts (tariffs) are the biggest people-driven shocks. Company-specific posts by a president give a measurable abnormal return within minutes, mostly gone within days. Celebrity effects are mostly myth (Ronaldo/Coca-Cola: the drop was largely the ex-dividend date. This is a great "dead end" for the story).

**Seed list:** `data/events/seed_events.csv`. Famous cases only, used to test the pipeline. The real samples (§1b) come from complete sources.

**1b. Complete event sources (to avoid selection bias):**
- Trump: every Truth Social post (archive, see §5) + every speech (UCSB American Presidency Project).
- Prabowo: every speech/statement on presidenri.go.id / setkab.go.id + major Indonesian news.
- Powell: all FOMC press conferences + speeches (federalreserve.gov, scheduled = a clean control group).
- CEOs/celebrities: a fixed list of ~20 people. Events = every news article mentioning them in GDELT above a volume threshold.

## 2. Q2: How long from first report to market move to general consensus?

Three clocks per event:
1. **t0, origin:** the post or speech timestamp (Truth Social post IDs encode milliseconds).
2. **Price clock:** when the move starts (first 1-min bar with |abnormal return| > 3σ or a volume spike) and when 50% / 90% of the day's move is done.
3. **Diffusion clock (consensus):** the cumulative count of articles/posts about the event over time (GDELT, 15-min buckets, + RSS + Reddit). "Consensus" = 50% of the first 24h of coverage reached. Also: the time until Google Trends or r/wallstreetbets picks it up.

**Headline we expect to test:** *"the price had finished moving before half the coverage existed."* If true, reading the news is useless for trading the first move. Then the follow-up question: does the price **overshoot and revert** once retail piles in (Q4b)?

## 3. Q3: Which outlets and apps are fastest?

- Poll ~30–50 sources every minute (RSS + Reddit + Telegram + GDELT) and log `first_seen_at` per headline.
- Match headlines to events (keyword + time window; fuzzy match). Rank sources by the median lag behind t0 and by the hit rate (how often they cover the event at all).
- Candidates: wire services (Reuters/AP/Bloomberg via RSS where available), CNBC, MarketWatch, Yahoo Finance per-ticker RSS, Google News RSS, Reddit (r/wallstreetbets, r/stocks, r/investing, r/indonesia), Telegram news channels, Indonesian outlets (CNBC Indonesia, Kontan, Bisnis.com, Detik Finance), and Truth Social itself as ground truth.
- **This only works going forward.** RSS keeps no history, so the collector must run for weeks before Q3 has an answer. Start it early.

## 4. Extra questions (Q4)

- **a. Does the market get used to it?** Trump's 50th tariff post vs his 1st. Is the effect decaying (fatigue/desensitisation)? This is a great chart.
- **b. Overreaction and reversal:** after a person-driven drop, is +1d/+5d positive on average? (e.g. quantum stocks after Jensen Huang's CES 2025 comment.) This is the only "usable" edge for a slow trader, and the most likely to be noise, so it needs out-of-sample testing.
- **c. Does sentiment *tone* matter or just attention?** Compare lexicon tone vs plain mention volume as predictors. Often attention alone carries the signal.
- **d. Indonesia vs US:** does IHSG/IDR react more to Prabowo than SPY reacts to Trump (a smaller, more foreign-flow-driven market)? Foreign net sell data from IDX helps here.
- **e. Lead or lag:** does Reddit sentiment lead price, or just follow it? (Granger-style test, done honestly; it'll probably lag.)

## 5. Data sources, cost and limitations

### Free and no AI needed ✅
| Need | Source | Limitation |
|---|---|---|
| Daily prices (US, IHSG `^JKSE`, IDR `IDR=X`, any stock) | `yfinance`, Stooq | Unofficial scraper, can break. Daily history is fine for decades. |
| Intraday US (1-min) | Alpaca free plan (IEX feed) | IEX = only ~2–5% of US volume, so bars are noisier than consolidated data. History limit to verify on signup. Last 15 min unavailable on the free plan (irrelevant for history). |
| Intraday Indonesia / FX | `yfinance` 1-min | **Only the last ~7–30 days.** Can't get old minute data free, so we archive it ourselves going forward (a daily cron job). |
| Global news + tone | GDELT 2.0 (GKG/DOC API, 15-min updates, 2015→) | Already has a tone score (lexicon, no AI). DOC API search only covers ~3 months. Full history via raw files or BigQuery (free 1 TB/month). Noisy, includes Indonesian media. |
| Trump posts | trumpstruth.org (RSS with date filters), Hugging Face Truth Social dataset | Unofficial archives. Check coverage gaps. |
| Speeches | UCSB American Presidency Project, federalreserve.gov, presidenri.go.id | Speech *start* times are often only to the day, so the minute-level t0 is fuzzy for speeches (good for posts). |
| Reddit | Official API (free, OAuth, ~100 req/min) going forward. Arctic Shift dumps for history. | API terms limit commercial use (fine for a portfolio). |
| Telegram news channels | Telethon (free, your own account) | Needs a phone number and API id. Channel choice is manual. |
| RSS (outlets) | `feedparser` | Forward-only. Some outlets (Reuters) killed public RSS. Google News RSS is a workaround. |
| Sentiment scoring | VADER, Loughran-McDonald finance dictionary, GDELT tone; Indonesian: InSet lexicon | Lexicons miss sarcasm and context ("tariffs are a beautiful thing"). Fine for aggregates, bad on single posts. |

### Free but "AI-ish" (optional, runs locally, no API cost)
- FinBERT / IndoBERT sentiment models run on your laptop CPU. They're better than lexicons on finance text, slow-ish but fine for thousands of headlines. They're **not dependent on any paid AI service**. We can compare lexicon vs FinBERT as a finding.

### Not free ❌
- **X/Twitter.** The free read tier closed to new developers in Feb 2026. Pay-per-use is about $0.005 per post read. This is the biggest gap: many of the "fastest" accounts (squawk accounts) live on X. Workarounds: their Telegram mirrors, Truth Social for Trump, or a small paid budget later (e.g. $5 = ~1,000 posts for a targeted pull).
- Bloomberg/Reuters terminals, consolidated (SIP) real-time feeds, tick data, historical intraday for IDX.
- StockTwits API (closed to new registrations, last I checked).

### Practical limits of running it yourself
- A collector needs to be **always on** to measure Q3. Options: your laptop (gaps when it sleeps), a free GitHub Actions cron (every 5 min minimum, sometimes delayed, so not 1-min precision), or a free-tier cloud VM (Oracle Always Free). Start with GitHub Actions every 15 min for RSS/GDELT. Polling slower than the event creates *measurement* lag.
- Your timestamps measure when *you saw* the headline, not when it was published. Use the outlet's `published` time where provided and cross-check.
- Small samples: maybe 30–100 clean minute-level events per category. Expect wide confidence intervals and report them.
- Survivorship: delisted stocks vanish from free sources.

## 6. Pipeline sketch (research scripts; the usable version is §9)

```
src/fetch_prices.py      yfinance daily + Alpaca 1-min around events      -> data/raw/prices/
src/fetch_events.py      Truth Social archive, speeches, FOMC calendar    -> data/raw/events/
src/fetch_gdelt.py       article counts + tone per event, 15-min buckets  -> data/raw/gdelt/
src/collector.py         forward-only: RSS + Reddit + Telegram every N min -> data/raw/stream/  (Q3)
src/event_study.py       abnormal returns, timing clocks                  -> data/processed/
notebooks/01..           Q1 -> Q2 -> Q3 -> Q4
```

---

_Sections 7–9 added 2026-11-10 (session 1, part 2), after the user's follow-up questions._

## 7. Who we track

`data/events/people.csv`, 19 people in 7 groups, each with a priority (1 = build first).
- **Priority 1:** Trump, Prabowo, the Fed chair, the Indonesian finance minister, Musk, Jensen Huang.
- **Control groups on purpose:** the Fed chair (scheduled, so the market knows it's coming) and celebrities (expected to have ~no effect). If our method says Taylor Swift moves the S&P, the method is broken.
- Musk's main channel is X (paid), so for him we use news coverage of his posts (GDELT) as a proxy, which adds a few minutes of lag.

### 7.1 Markets: picked per person, not the other way round
The user cares about the **people**; markets are just the measuring stick. Each person is measured on the assets their words actually land on (`main_assets` in people.csv). Three markets cover everyone:
- **US stocks** (SPY/QQQ, sector ETFs, named tickers): most of the people on the list, and the best free data (1-min via Alpaca).
- **Indonesia** (IHSG `^JKSE`, rupiah `IDR=X`, big state banks): Prabowo and his ministers. It's a smaller market driven by foreign money, so effects may be *bigger*, which makes it an interesting contrast to the US. Free intraday data has to be archived going forward.
- **Bitcoin** (`BTC-USD`): trades 24/7, so it's the only market that can measure **weekend and late-night posts**, when stocks are closed. It's directly relevant to Trump, Musk and Saylor.
- Not a main market: Singapore (STI). Few of these people target it directly. Maybe later as a "spillover" check (do Trump tariffs on Asia hit STI?).

## 8. How we decide what's significant (the analysis toolkit)

Two different questions, and they need different tools:
- **"Did this event move the market?"** Per-event test (8.1).
- **"What do the events that move the market have in common?"** Regression on features (8.3).

### 8.1 Per-event: did it move? (the significance model)
1. **Expected return**, the "normal" move: market model `r_stock = α + β·r_market`, fit by OLS on the 60 days before the event. For index-level events, use the same time of day on non-event days.
2. **Abnormal return (AR)** = actual − expected. **CAR** = AR summed over a window (e.g. +30 min, +1 day).
3. **Placebo distribution:** compute the same CAR at ~1,000 random non-event times (same weekday and time of day, similar volatility). The **empirical p-value** = share of placebo CARs at least as extreme as the real one. This is a permutation test. It makes no normality assumption, so it handles fat tails, which stock returns have.
4. Volatility-adjusted: divide by the recent standard deviation, so a 1% move in a calm week counts more than a 1% move in a crash week.

### 8.2 Per person / category: do they move it *on average*?
- Average CAR across all of a person's events, with a **bootstrap confidence interval** (resample events 10,000×).
- Also the **hit rate**: the share of events with p < 0.05, compared with the 5% expected by chance. If Trump's posts "move the market" 7% of the time vs 5% by chance, that's a very different story from 40%.
- **Multiple testing:** with 19 people × several assets × windows, some will look significant by luck. Correct with **Benjamini–Hochberg (FDR)**: "of everything we flag, at most ~10% are false alarms."

### 8.3 Commonalities: what makes an event matter? (multiple regression, plus guards)
Yes, multiple linear regression is the core tool, with these guards:
- **Outcome:** `|CAR|` (did it move at all?) and signed `CAR` (which way?) as separate models. Most people-driven effects are about *size*, and the direction depends on content.
- **Features:** who, channel, scheduled?, topic, tone (lexicon), attention (article count in the first hour), market regime (VIX level), time of day, nth event of this topic (for desensitisation), country.
- **Each of the Q4 questions is one coefficient in the model:**
  - Desensitisation → coefficient on `log(nth post on the same topic)`; negative = the market is getting used to it.
  - Tone vs attention → put both in; compare coefficients (standardised) and the R² drop when each is removed.
  - Indonesia vs US → interaction `head_of_state × country`.
  - Reddit lead/lag → this one is a time-series question, not a regression on events: **Granger causality** (does yesterday's Reddit sentiment improve the forecast of today's return beyond past returns?), run both directions.
- **Guards:**
  - **Clustered standard errors by date.** Five posts on one crazy tariff day aren't five independent data points.
  - **Control for regime** (VIX, day of week) so "Trump posts more when markets are already falling" doesn't fool us. This is the same confounding trap as CS2 nb05, where clumping was a *result* of losing the opener and not the cause.
  - **Few events, many variables → overfitting.** Rule of thumb: ≥10–20 events per feature. Fewer → group the categories more coarsely.
  - **Exploration vs confirmation:** use Lasso or gradient boosting + SHAP to *explore* which features matter, then confirm with a plain regression on a **later time period** the exploration never saw (train on 2024–25, test on 2026).
  - **Statistical ≠ economic significance:** a real 0.05% effect is useless after the bid/ask spread and fees.

### 8.4 Timing (Q2)
- Price clock: time to 50% and 90% of the final move (from 1-min bars).
- Diffusion clock: cumulative article count fit with a **logistic (S-curve)** curve. Its midpoint = "consensus time".
- Compare the two clocks per event, and with regression: what makes the gap bigger? (Indonesian news, after-hours posts, ...)

### 8.5 Prediction (for the pipeline, §9)
- Classification: "will this new event move asset X by more than its normal noise within window W?" Start with **logistic regression** (interpretable), then try gradient boosting. **Calibrate** probabilities (same as CS2 nb04).
- Regression for direction and size, plus **quantile regression** to give a range instead of one number.
- Validation: **walk-forward only** (train on the past, test on the next month, roll forward). Never a random split, since that leaks the future.
- Then **backtest** the rule with realistic costs, then **paper-trade** (Alpaca has free paper trading) before any real money. This could be the project's honest "ending", like the CS2 experiment.

## 9. The usable pipeline (the user's design, refined)

The user's sketch: scrape weekly or on demand → events + people → model finds significant ones and filters → model predicts the window to short or buy.

```
[1] INGEST          weekly / on demand: prices, Truth Social, speeches, GDELT, Reddit
                    + always-on light collector: RSS / Truth Social every 1-5 min  (needed for live use + Q3)
        |
[2] EVENT TABLE     rules, no AI: who x keyword taxonomy (tariff, rate, resign, ...) -> one row per event
        |
[3] MEASURE         abnormal returns + placebo p-value for every past event      (8.1)
        |
[4] SIGNIFICANCE    per person x topic x asset: average CAR, CI, FDR-corrected    (8.2, 8.3)
    FILTER          -> watchlist.csv: only combos that are significant AND big enough to beat costs
        |                retrained weekly, walk-forward
[5] PREDICT         new event matches the watchlist -> expected move, range, probability,
                    and the *window*: when the move usually starts, peaks and reverts   (8.4, 8.5)
        |
[6] OUTPUT          alert (Telegram bot to yourself, free) + weekly report notebook
                    + paper-trade log to check if the alerts would have worked
```

**Honest limits of step 5 (the "when to short/buy" part):**
- For surprise posts the first move takes **minutes**. A weekly pipeline can't catch that, and a 1–5 min poll catches it late. Realistically usable windows are the **slow ones**: the multi-day drift or reversal after the shock (Q4b), and **scheduled** events (known in advance, so you can set things up before).
- Shorting: in the US, easy via inverse ETFs/puts (not advice 😛). In Indonesia, retail short-selling is very limited, so the IDX side is more "avoid / buy the dip" than "short".
- The watchlist will be small. Most people won't pass the filter, and that's a finding, not a failure.
