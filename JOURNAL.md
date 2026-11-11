# Journal

The messy middle. Short dated entries covering what I tried, what broke and what surprised me. This is where the portfolio story comes from later.

---

## 2026-11-10: Day 0

- Idea: influential people (Trump, Prabowo, CEOs like Jensen Huang, celebrities) seem to move the market just by talking. Want to test it properly instead of going off memory.
- Set up the folder and research plan. Questions: who moves markets, how fast vs how fast news spreads, fastest sources, and whether there's an overreaction that reverses.
- Constraint: free and no paid AI. Turns out that's mostly fine. The big gap is X/Twitter (no free read access since Feb 2026) and old minute-level data for Indonesia.
- Seed list of 12 famous events in `data/events/seed_events.csv`, all unverified. Suspect at least one (Ronaldo/Coca-Cola) is a myth.
- My takes: (fill in)

## 2026-11-10: Models and the "actually use it" pipeline

- Asked: is the point finding what events/people have in common when the market moves a lot? Yes, in two steps: first test each event on its own against random non-event times (did it move at all?), then regress the size of the move on features (who, topic, tone, attention, scheduled or not) to find what they share.
- So many variables → multiple regression is the base, but with guards: errors clustered by day, control for market mood (VIX), FDR correction because we test lots of people, and confirm on a later time period.
- My pipeline idea: scrape → events → model filters to the significant ones → predict the window to short/buy. Kept it, but the honest catch: surprise posts move prices in minutes, so a weekly pipeline can only catch the slow multi-day stuff (the bounce-back after a shock, scheduled events). Paper trade before any real money.
- Tracking 19 people, including celebrities as a control group: if the method says Taylor Swift moves the S&P, the method is broken.

## 2026-11-10: It's about the people, not the markets

- Realised I care more about the influential people than about any particular market. Markets are just how we measure them.
- So the markets are picked per person: US stocks (most people, best free data), Indonesia (Prabowo; smaller market, maybe bigger effects) and Bitcoin (open 24/7, the only way to measure weekend and late-night posts).

## 2026-11-10: First data: checking the famous events

- Set up Python, pulled daily prices since 2015 (free, yfinance) for SPY, QQQ, IHSG, the rupiah, Bitcoin, VIX and the seed stocks.
- Checked the 12 famous events against prices. Compared each day's move to "a normal day" for that stock.
- Real and huge: Liberation Day (S&P −4.9%, then −5.9% the next day), the tariff pause (+10.5%, one of the biggest days ever), Jensen Huang's quantum comment (quantum stocks −36% to −45% in a day), DeepSeek (NVDA −13% beyond what the market did), Musk "funding secured" (+10.6%).
- **Ronaldo and Coca-Cola is a myth.** Coke's raw price fell 1.1% that day, but that was the ex-dividend date. Strip the dividend out and it's −0.45%, a completely normal day.
- Surprisingly not big on the day: Trump telling Intel's CEO to resign, Powell's Jackson Hole speech, and Sri Mulyani getting replaced (the drop came the next day, so the news was probably after the market closed).
- Found a flaw in my own method: "a normal day" was measured over a window that included the April 2025 crash, so later shocks look smaller than they are. Need a baseline that adapts.
- My takes: I didn't hear about any of these when they happened, and I didn't even know about them. Which shows why having a pipeline that tells me the window would be helpful.

## 2026-11-10: Every Trump post, not just the famous ones

- Found a free archive of every Truth Social post (CNN keeps one): 38,003 posts since Feb 2022. Checked the timestamps against the post IDs: all within a second.
- He posts about 20 times a day, so "did Trump post today" is useless (he always did). Switched to hourly prices: do the hours with a post move more than the hours without?
- **A random Trump post does nothing.** Hours with a post look exactly like hours without.
- **Tariff posts do something:** those hours are ~18% more volatile in the S&P and ~25% in Bitcoin, and about twice as likely to be a big hour. But it's a handful of posts doing the work. One China post on 10 Oct 2025 at 10:57am made that hour ~10× a normal hour's move. Most of the other 461 tariff posts are repeats that nothing happens after.
- Nothing carries into the next hour. Whatever happens, happens within the hour.
- Weird one: hours where he posts about companies were *calmer*. Looking at the posts, they're mostly political (Google and elections, suing JPMorgan), not business news. Not reading into it yet.
- So the real question isn't "does Trump move markets" but "which posts". Next: does the market get used to tariff threats, and can a simple rule spot the posts with new information?
- My takes: (fill in)

## 2026-11-10: Did the market get used to the tariff posts?

- Expected the effect to fade with every new tariff post. It didn't, at least not smoothly.
- Split his 461 tariff posts into four stages:
  - before Apr 2025: no extra movement (tariffs were mostly talk)
  - Apr–Jul 2025: some
  - Jul 2025–Feb 2026: the peak, about 1 in 5 tariff hours was a big hour
  - since Feb 2026: nothing at all (0 big hours out of 33)
- So it's not "the market got used to him". It's more like there was a period where his tariff posts had real power, and then it ended. Need to find out what happened around Feb 2026.
- My "concrete post" rule (has a % or a deadline) didn't predict anything. The biggest post of all (10 Oct 2025) didn't even have a number in it. It was a surprise escalation after things had been calm. So the thing to measure is surprise: how different a post is from what he's been saying lately.
- Also caught a false alarm: a big drop on 4 Apr 2024 lined up with him sharing a Breitbart link that mentioned tariffs. Almost certainly a coincidence. One post is never proof.
- My takes: (fill in)

## 2026-11-10: Trying to measure "surprise" (dead end)

- Built a surprise score for every post without AI: how different it is from his recent posts (word-overlap similarity, TF-IDF), and whether it suddenly turns more aggressive or more friendly than his recent tariff posts (counting words like "hostile", "massive", "retaliate" vs "deal", "pause", "negotiate").
- It caught the 10 Oct post (more aggressive than 98% of tariff posts) but that's cheating a bit: I wrote the word list after reading that post. Take out the two famous posts and the effect disappears.
- "How different from his recent posts" didn't work either. Basically everything he posts is different from his last 50 posts. A tiny effect in Bitcoin, but useless for picking out the big hours.
- The real reason, I think: what surprises the market depends on what the market expected, not on his words. On 10 Oct there was a trade truce with China, so a hostile post was a shock. The same words in April 2025 would've been old news.
- So the pipeline shouldn't try to guess the first move from the text. It should notice the move as it happens and tell me what usually happens next (does it keep falling, or bounce back?).
- My takes: (fill in)

## 2026-11-10: After the shock: buy the dip?

- Took every big hour (about 2× a normal hour's move or more) that had a Trump tariff post in it, and checked what happened over the next hour, day and week.
- Normal big hours (no post) slightly bounce back over the following days. Standard stuff.
- Trump tariff shocks did the opposite: if anything they **kept going**. On average +1.1% further in the same direction over 5 days in the S&P. But it's only 13 events in 2 years, and one week (7–9 Apr 2025) carries a lot of it. Take that week out and it's +0.4%.
- Bitcoin: no pattern at all.
- So "buy the dip after Trump scares the market" isn't supported. The honest version: these shocks look like real news rather than overreactions, but there are too few to be sure. For the pipeline it's more "don't panic, and don't blindly buy the dip" than a trading signal.
- Big lesson so far: the sample is the problem. One person + one topic = ~6 events a year. Need more people, finer data, and time.
- My takes: (fill in)

## 2026-11-11: Who else moves markets?

- Wanted more people than just Trump. Plan was news counts from GDELT (a free news database), but it blocked my computer after a few dozen requests and kept blocking it for a day.
- Switched to Wikipedia page views instead: how many people looked someone up each day, back to 2015. Had to use mobile views only, because bots inflate the desktop numbers (Sam Altman "had" 500k views a day in June 2025, almost all bots).
- Took the days when attention on a person jumped 3× or more, and checked if their stock/market moved more than on random days. 10 people, 10 years.
- What passed: the Fed chair (S&P and bonds, but those are mostly scheduled meeting days), Prabowo (IHSG moves the next day, because Jakarta's market closes before the US news day), and Roaring Kitty (GME).
- What didn't: Musk, Sam Altman, Lutnick, Purbaya. Bessent looked significant but it was only the tariff week in April 2025, so that's really Trump.
- Taylor Swift was my control. Nothing. Good: the method isn't just finding stuff everywhere.
- Most interesting bit: for GME and Nvidia, the price moved first and the attention came after. People look up Jensen Huang *because* Nvidia moved, not the other way round. By the time the public is paying attention, the move has mostly happened.
- My takes: (fill in)

## 2026-11-11: The Fed: calendar or surprise?

- The Fed chair came out as the strongest "person" result, but Fed meetings are on a calendar everyone knows. So I pulled the official meeting and testimony dates from the Fed's website and split the attention spikes into meeting days, testimony, Jackson Hole, and everything else.
- Fixed a mistake on the way: before Feb 2018 the chair was Yellen, not Powell, so I was tracking the wrong person for 2015–2017.
- Surprise 1: the average Fed meeting doesn't move the S&P more than a random day. The market already expects most of what they say.
- But the meetings that got a burst of public attention did move it (about 1.3× a normal day), and the ones without a burst were calmer than normal. So attention picks out the meetings where the Fed surprised people. The catch: the attention comes at the same time as the move or after, so it tells you it's happening, not that it's about to happen.
- Surprise 2: news about the chair outside meetings does nothing. Nominations (even Warsh in January 2026), Trump attacking Powell, "will he get fired": zero effect on the day.
- The rest of the effect was crashes, where the market fell first and then everyone looked up the Fed chair.
- My takes: (fill in)

## 2026-11-11: Building the forward collector

- Question 3 (which outlets are fastest) can't be answered from history, because news feeds only show the latest items. So I need something that checks the news every few minutes and writes down when each headline first appeared, then leave it running for weeks.
- Built it to check about 40 free sources every 10 minutes: CNBC, WSJ, FT, BBC, Yahoo, the Fed, the White House, the SEC, Indonesian outlets (CNBC Indonesia, Detik, Antara), StockTwits, and a Google News search for every person on my list.
- The Google News part is the best bit: one search returns articles from hundreds of outlets, and each one says who published it. Nearly 300 different outlets in the first run.
- Also saving minute-by-minute prices every day (S&P, Nvidia, Tesla, GME, IHSG, Bitcoin...). Yahoo only keeps the last 7 days of minute data, so if I don't save it now it's gone. This is how I'll eventually see how fast a market reacts in minutes, not days. IHSG minute data works, which I couldn't get any other free way.
- It runs on GitHub's free scheduled jobs, so my laptop doesn't need to stay on.
- Things that didn't work: Reddit blocks you after one request, Bluesky's search is closed, and a few outlets have dead feeds.
- My takes: (fill in)
