# Kaggriculture Top-Player Opening Fingerprints

A structured dataset of the **first 48 turns (2 in-game days)** played by the current
top-5 teams in the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
simulation competition. Extracted from 15 official episode replays (3 per team).

This dataset makes it easy to answer:

- **What does each top team do in their opening?** Aggregate spend per opening.
- **Are they all running the same public agent?** Compare opening signatures.
- **Which strategy cluster does an opponent match?** Cluster classifications
  are pre-computed based on distinctive opening actions.

Snapshot date: **2026-08-09**. Ladder scores from that day.

## Files

### `openings_summary.csv` (15 rows)

One row per (team, episode) with aggregated first-48-turn spend:

| Column | Meaning |
| --- | --- |
| `team` | Player identifier (Seb, HealthStone, tao_wu11, Mohamed, mrgrishninsb) |
| `episode_id` | Kaggle episode id (fetchable via `kaggle competitions replay`) |
| `opponent` | Opposing team in that specific episode |
| `final_reward` | Final coins at game end for the target team |
| `ladder_score` | Team's Kaggriculture ladder rating on 2026-08-09 |
| `hires_first48` | Count of HIRE market orders in first 48 turns |
| `land_first48` | Count of BUY_LAND market orders |
| `cows_first48` / `sheep_first48` / `geese_first48` | Units of each animal purchased |
| `wheat_seeds_first48` / `melon_seeds_first48` / `strawberry_seeds_first48` | Units of each seed purchased |
| `wheat_bought_first48` | Units of WHEAT purchased from the market (feed) |
| `sold_wheat_first48` / `sold_fertilizer_first48` | Units sold |

### `openings_actions.csv` (~3,200 rows)

Long-format action log for the same 15 episodes: one row per farmer / hand / market
action in the first 48 turns. Use this to reconstruct exact opening sequences.

| Column | Meaning |
| --- | --- |
| `team`, `episode_id`, `turn`, `day`, `hour` | Context |
| `money` | Team's cash at the start of that step |
| `actor` | `farmer`, `hand_0..hand_N`, or `market` |
| `action` | Operation name (e.g. `PLANT`, `BUY_ANIMAL`, `HIRE`) |
| `arg1`, `arg2` | Action arguments (item, quantity, etc.) |

### `openings_clusters.csv` (5 rows)

Distilled classification of the top-5 teams into strategy clusters:

| Column | Meaning |
| --- | --- |
| `team`, `ladder_score` | Player and rating |
| `cluster` | Strategy family: `v23_fork`, `sheep_first_hybrid`, `counter_meta` |
| `signature` | Human-readable opening fingerprint |
| `public_agent` | True if the opening matches a known public notebook |
| `notes` | Interpretation |

## Key finding: three genuine strategy clusters

The top 5 teams fall into exactly three clusters:

1. **`v23_fork`** — Mohamed, mrgrishninsb, tao_wu11. Identical opening signature to
   [kaitofukami's v23](https://www.kaggle.com/code/kaitofukami/23-23-strict-future-v23-sparse-closed-loop).
   Score band 3117–3131.
2. **`sheep_first_hybrid`** — HealthStone (rank #2). Buys 1 cow + 4 sheep on day 0,
   only 3 hires. Score 3133. Not a known public agent.
3. **`counter_meta`** — Seb (rank #1). Aggressive labor (14 hires day 0),
   ends with 4 quadrants and ~20 animals. Score 3201. Not a known public agent.

**The top-2 slots are held by private agents that beat the public fork race.**
Anyone at rank 3–15 is essentially running the same v23 opening.

## How this was built

1. Pulled the top-5 teams' active submissions via `kaggle competitions team-submissions <team_id>`
2. Downloaded 3 recent episodes each via `kaggle competitions replay <episode_id>`
3. Extracted the target player's actions from the first 48 steps of each replay
4. Aggregated into summary + long-format CSVs
5. Classified the 3 clusters by comparing opening signatures against
   [v23's known opening](https://www.kaggle.com/code/kaitofukami/23-23-strict-future-v23-sparse-closed-loop)

Full generator script is in the notebook that accompanies this dataset.

## Suggested uses

- **Benchmark your own agent's opening** — is your first-48 spend closer to v23-fork,
  HealthStone, or Seb? Which cluster does your win-rate look most similar to?
- **Detect what opponent you're facing** — a live agent could match its first-turn
  observations against these fingerprints to select a counter-strategy.
- **Reproduce private strategies** — if you can rebuild HealthStone's opening exactly,
  you may recover a chunk of their edge.

## Attribution and license

- Underlying replays are from
  [kaggle/kaggriculture-episodes-index](https://www.kaggle.com/datasets/kaggle/kaggriculture-episodes-index),
  redistributable under the Kaggle Terms of Use.
- Cluster classification and analysis by Revanth Tambisetty.
- **v23_fork** classification is based on the public opening signature from
  [kaitofukami v23](https://www.kaggle.com/code/kaitofukami/23-23-strict-future-v23-sparse-closed-loop).
- Released under Apache 2.0.

If you find the cluster analysis useful, please upvote the source notebooks that
made it possible.
