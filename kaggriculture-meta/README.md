# The Kaggriculture ladder meta, recomputed

Derived, aggregate view of the Kaggriculture simulation ladder. It ships ONLY computed rollups and per-episode
outcome summaries, never the raw 720-step replays, so it is the same class of derived-analysis output as a
public leaderboard rather than a redistribution of competition data.

## Files
- `daily_ladder.csv` - one row per day from the public kaggle-owned episode index manifest: episode_count,
  top and median average score, plus the derived top-to-median gap, day-over-day median change, and median
  growth from the first day. Shows the score inflation and the field catching up to the top over time.
- `episode_results.csv` - one row per sampled episode: the two agents, their final rewards (raw end-of-game
  money), the winner, the margin, whether both agents finished cleanly, and the step count. Outcomes only.
- `agent_outcomes.csv` - per agent over the sampled complete games: games, wins, ties, losses, win rate, and
  reward summaries. Win rate is scale invariant across days; reward summaries are raw final money.
- `matchups.csv` - head-to-head record for each ordered agent pair seen in the sample.

## Sample and provenance
The daily ladder covers every day in the public index (12 days). The episode outcome tables are
computed from a sample of 60 episodes (50 from 2026-08-10, 10 from the early ladder on
2026-08-02); win rates on a sample of this size are indicative, not final. Source episodes are the public
kaggle-owned datasets kaggle/kaggriculture-episodes-index and kaggle/kaggriculture-episodes-YYYY-MM-DD. Only
derived aggregates are shipped here; get the raw replays from those public datasets.

Companion notebook: https://www.kaggle.com/code/busyaprime/what-actually-wins-on-the-kaggriculture-ladder
