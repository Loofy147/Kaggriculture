# Kaggriculture action-stream fingerprints

Per-seat hashes of what each agent actually **did**, at a series of prefix lengths, so that clustering agents by behaviour costs a group-by instead of hours of JSON parsing.

Two seats whose hash at turn *N* matches played **identical actions** through turn *N*. An agent that does not read the board plays the same 720 actions whatever happens in front of it, so identical streams across two different games is an observation rather than a model fit. There is no distance threshold to choose and no number of clusters to guess.

## If you have never seen this competition

Two agents each farm a 10x10 grid for 720 turns, which is 30 in-game days of 24 hours, sharing one market. Whoever banks the most money wins. A **seat** is one agent in one game, so every episode contributes exactly two seats and each is the other's opponent.

An **action** is what a seat submitted on one turn: a dict of orders for the farmer, the hired hands and the market. A **schedule** is the sequence of 720 of them. That sequence is what this dataset hashes.

## Start like this

```python
import pandas as pd

fp = pd.read_parquet("/kaggle/input/kaggriculture-stream-fingerprints/"
                     "seat_fingerprints_random.parquet")

# how much of the field shares an opening, as a curve over how long they agree
for h in (24, 100, 200, 400, 719):
    c = fp[f"h{h}"].value_counts()
    print(f"turn {h:>3}: {len(c):>5} distinct schedules, "
          f"largest holds {100 * c.iloc[0] / len(fp):.1f}% of seats")

# the teams provably replaying a fixed recording: same team, identical stream,
# two games, two seeds, two opponents
sfp = pd.read_parquet("/kaggle/input/kaggriculture-stream-fingerprints/"
                      "seat_fingerprints_teams.parquet")
proven = [
    team for team, g in sfp.groupby("team")
    if any(gg.episode_id.nunique() >= 2 and gg.seed.nunique() >= 2
           and gg.opponent.nunique() >= 2
           for _, gg in g.groupby("full_sha"))
]
print(f"{len(proven)} teams provably open-loop")
```

## What this is, and what it is not

**It is a fixed snapshot, not a live feed.** Every episode in it was played between **2026-07-30 17:29 UTC and 2026-08-11 23:19 UTC**, thirteen days of the competition. It will not be updated, and nothing here should be read as describing the ladder after that window.

**It is not a census.** It is **two targeted samples**, drawn to answer two specific questions in a first study, and it covers **4,546 of the 22,702 public episodes** the source corpus held at that moment, about **20%**, across 1,552 of the competition's roughly 3,947 teams.

It exists because hashing 2,670 replays takes ten minutes and produces under a megabyte. Anyone who wants those particular questions answered should not have to spend the ten minutes, and anyone who wants *different* questions answered should not assume these samples suit them.

**What it was built for.** A census of what the field plays, published as a notebook: how much of the field shares an opening, which teams are provably replaying a fixed recording, and when a particular line appeared and how fast it spread. The samples were designed around those questions and are honest about it rather than general-purpose.

**What would be better, in order.** The full corpus. `make_fingerprints.py` is included and will fingerprint every episode with `--limit 0`; it takes a couple of hours, which is the only reason this is a sample. Better still, hashes computed **upstream**, in the collector that already parses every replay, which would cover everything and cost almost nothing. That is proposed here: <https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes/discussion/734833>

**Why it is not kept up to date.** A scheduled notebook could refresh it, which is how the source corpus is maintained. I decided against it deliberately: an auto-updating dataset is a promise, and an abandoned one is worse than an honest snapshot, because its documentation quietly stops matching its contents. A dated window is citable forever and cannot rot. If the hashes end up computed upstream, as proposed in the link above, this dataset should disappear rather than compete with them.

**If you extend it, please say so in the discussion** and I will point at yours instead. An exhaustive version makes this one obsolete, which is the outcome I would prefer.

This is derived data. It carries no replays and no per-turn game state: the hashes, plus the episode metadata you need to join and interpret them.

## Files

| file | rows | what it is |
|---|---|---|
| `seat_fingerprints_random.parquet` | 5,340 seats / 2,670 episodes / 1,263 teams | a **uniform random sample of public episodes**, seed 20260812 |
| `seat_fingerprints_teams.parquet` | 4,258 seats / 2,129 episodes / 897 teams | a **team-stratified sample**: 600 teams across four activity bands, up to 4 episodes each |
| `coverage_weights.parquet` | 9,137 submissions | inverse-probability weights, so frequencies can be corrected for the source's uneven coverage |
| `make_fingerprints.py` | | the script that produced the two tables, unmodified |
| `measure_coverage.py` | | the script that measured the weights against Kaggle's episode API |

### Columns

`h24`, `h48`, `h100`, `h200`, `h300`, `h400`, `h500`, `h600`, `h719` are the first 16 hex characters of a SHA-256 over the seat's actions from turn 1 up to that turn. `full_sha` is the same over the whole stream, `turns` is how many actions were hashed.

The rest is what you need to use them without going back to the 2.7 GB replay table: `episode_id`, `seat`, `team`, `team_name`, `opponent` (the other seat's team id), `sub` (submission id), `bank` (final coins), `rating` (skill rating after the game), `create_time`, `day` (an `MM-DD` convenience), `type` (`EPISODE_TYPE_PUBLIC` is a ladder game, `EPISODE_TYPE_VALIDATION` is self-play, filter it out for strength analysis) and `seed`.

`opponent` and `seed` are what the open-loop proof needs: the same team emitting a byte-identical stream in two different games, against different opponents, at different seeds, demonstrably read neither the board nor its rival.

Actions are canonicalised as `json.dumps(action, sort_keys=True, separators=(",", ":"))`, with anything that is not a dict mapped to `{}`. `steps[0]` carries no action and is skipped.

**On the truncation.** Keeping 16 hex characters leaves 64 bits. Across the 9,598 seats here the chance of any two distinct schedules colliding is about 2.5e-12, one in four hundred billion, so a hash match is a schedule match for every practical purpose. If you extend this to millions of seats, rerun `make_fingerprints.py` and keep more characters.

**What a hash cannot see.** Two agents that reach identical outcomes by different actions look different here, and two that differ on a single irrelevant order look as different as two that share nothing. Exactness is the point, and it is also the limit: this measures what agents *emit*, never what they *intend*.

## Two samples, because two questions need different designs

Using one sample for both is how the first version of this analysis went wrong, by a factor of three.

**Random** is the right frame for *what is the field playing*. Every public episode has the same chance of being drawn, so the seat population is the source corpus's own rather than a re-weighting of it.

**Team-stratified** is the right frame for *who is replaying a fixed recording*, which needs two or more games of the **same team**. A random draw over episodes spreads thin across thousands of teams and leaves most with a single game, and one game proves nothing.

## What each sample supports statistically

**`seat_fingerprints_random.parquet` is a probability sample.** A simple random sample without replacement of 2,670 of the 22,702 public episodes the source corpus held, a sampling fraction of 11.8%, so the finite-population correction is sqrt(1 - 0.118) = 0.94. Frequencies computed from it are unbiased *for that corpus*.

**But do not treat its 5,340 seats as 5,340 independent observations.** The sampling unit is the episode and each episode contributes two seats, which are each other's opponent. Measured on the indicator "this seat plays the most common opening", the intraclass correlation between the two seats of an episode is **0.27**, so the design effect is **1.27** and the effective sample size is about **4,200**, not 5,340. Standard errors computed as sqrt(p(1-p)/n) are roughly 13% too small.

That correlation is itself worth knowing: opponents tend to play the same opening, which is what matchmaking by rating produces once openings correlate with rating.

With the design effect and the correction applied, this sample resolves:

| a share of | 1 s.e. | smallest resolvable difference |
|---|---|---|
| 5% | 0.32 pp | 0.9 pp |
| 10% | 0.43 pp | 1.2 pp |
| 22% | 0.60 pp | 1.7 pp |
| 50% | 0.72 pp | 2.0 pp |

Per day the sample is much smaller, and the intervals widen accordingly, from about ±2 pp on the busiest days to ±6 pp on the thinnest.

**`seat_fingerprints_teams.parquet` is NOT a probability sample and must not be used for frequencies.** Teams are drawn evenly from four activity bands, which over-represents rare teams, and within a team it takes the **earliest** episodes rather than a random draw, which over-samples the opening days by roughly tenfold. Inclusion probabilities are unequal and unknown, and no weights are shipped, because the table exists for a question that does not need them: comparisons that hold a team fixed, where the selection cancels.

**No interval here covers the upstream bias**, but `coverage_weights.parquet` now lets you correct for it.

## Correcting for the source's coverage

The source corpus is not a uniform sample, and it is not a hopeless one either: it is a sample with unequal probabilities, which is a solved problem once you can estimate them. `measure_coverage.py` estimates, for a stratified sample of submissions, `p = episodes in the corpus / episodes the Kaggle episode API lists up to the crawl cutoff`, and extrapolates by strata using the one covariate that is free and strongly related, how many episodes the corpus already holds.

Measured, and the pattern is the crawl's priority ordering seen end to end:

| episodes the corpus holds | coverage |
|---|---|
| 1 | 1.2% |
| 2 | 2.1% |
| 3-4 | 3.1% |
| 5-8 | 4.0% |
| 9-16 | 5.3% |
| 17-32 | 18.4% |
| 33-64 | 96.4% |
| 65-128 | 64.3% |
| 129+ | 85.0% |

**Implied overall coverage: about 4.8%.** The corpus holds roughly one seat in twenty of the competition, and per submission that ranges over a factor of eighty.

Join `coverage_weights.parquet` on `sub` and weight by `w = 1/p`. On these samples the correction moves the headline numbers substantially and in the direction the mechanism predicts, because the crawl over-samples heavily covered submissions and those are the ones playing the most common line:

| | unweighted | weighted |
|---|---|---|
| effective openings at turn 24 | 9.5 | **17.3** |
| share held by the most common opening | 22.1% | **15.1%** |
| its peak daily share | 58.8% | **44.7%** |

The day-by-day collapse survives it intact, from 88.7 effective openings to 3.1.

**Three caveats on the weights.** They come from 90 measured submissions extrapolated by nine strata, so they carry their own error, which is not propagated into anything above. They cannot see a submission the crawl never touched at all, which makes 4.8% a **lower** bound on the field. And they correct *which submissions* are over-represented, not *which of a submission's episodes* were kept, so any bias in the latter survives.

## Provenance, and a bias you inherit

Built from [`georgymamarin/kaggriculture-episodes`](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes) **version 23**, crawled up to **2026-08-11 23:23 UTC**. That collection is Apache-2.0; the games belong to their players and to Kaggle.

**The upstream corpus is not a uniform sample of the competition**, and anything counted per seat here inherits that. Its `scrape.py` sorts submissions by most recent activity and stops at a time budget, so how completely a submission is indexed depends on how recently it played. Measured against Kaggle's episode API, one submission has 352 of its 352 in-window episodes present while another has 1 of 77, and across the collection the median submission is represented by 2 episodes while the top 1% hold about a third of all seats. Discussion: <https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes/discussion/734824>

So: **treat frequency statements computed from this as descriptive of the sample, not as estimates of the competition.**

Comparisons that hold a team fixed, such as "did these same teams change what they play", are unaffected in their *direction*, because how the teams were selected cancels within a team. Their *magnitude* is not unaffected, and this is the subtle part worth spelling out, because the upstream bias is structural rather than random and it propagates into who is available to compare.

A team can only be compared with itself if the crawl caught it twice, and the crawl favours submissions that played recently. The teams available for a before-and-after comparison are therefore the persistent, more-heavily-observed ones: in these samples about 6% of teams, with a median of nine episodes each against three for the rest. Measured, that subset is **not** skewed on skill, its median rating inside the late window being 2,031 against 2,046 for the others, but it **is** skewed toward whoever was iterating: it plays the most common late opening on 47.3% of its seats against 40.9% for the teams outside it.

Six percentage points. Enough that a within-team adoption rate computed here should be read as an upper bound, while the direction and one-sidedness of the change are what the design actually establishes.

`daily_stats.csv` upstream reports `replay_coverage = 1.0`; that is replays per *indexed* episode, not coverage of the competition.

## Regenerating it

`make_fingerprints.py` reproduces both files from the upstream dataset:

```bash
python make_fingerprints.py --random 2670 --seed 20260812 --out random.parquet
python make_fingerprints.py --teams 600 --per-team 4 --out teams.parquet
```

It takes roughly ten minutes per sample, which is the reason this dataset exists.

**One trap.** The source corpus refreshes daily and only grows, so running those commands today draws from a larger pool than version 23 did and will not reproduce these files. The samples are seeded, not pinned. To reproduce exactly you need version 23 of the source; to build a comparable sample from a later version, keep the seed and say which version you drew from.

## Built with, and used by

* **Source data:** [`georgymamarin/kaggriculture-episodes`](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes), version 23, Apache-2.0.
* **The competition:** [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture).
* **The engine:** [kaggle-environments](https://github.com/Kaggle/kaggle-environments). Payouts differ substantially between releases, so any money figure is only comparable within one engine version. Nothing in this dataset depends on the engine, since it hashes actions rather than outcomes, but `bank` does.
* **What it was built for:** [Everyone is playing the same opening](https://www.kaggle.com/code/destbreso/everyone-is-playing-the-same-opening), the notebook this exists to make fast. It is the worked example: the coverage curve, the collapse, the panel design, the rarefaction diagnostic and the open-loop audit are all computed from these two files.
* **On the source's coverage:** [the measurement](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes/discussion/734824) and [a proposal that would make this dataset unnecessary](https://www.kaggle.com/datasets/georgymamarin/kaggriculture-episodes/discussion/734833).

## Citation

```
destbreso (2026). Kaggriculture Action-Stream Fingerprints.
Kaggle. https://www.kaggle.com/datasets/destbreso/kaggriculture-stream-fingerprints
Derived from georgymamarin/kaggriculture-episodes v23, Apache-2.0.
Snapshot of 2026-07-30 to 2026-08-11; not maintained.
```
