# Kaggriculture: 18,144 Measured Episodes

Every episode our agents played during the 2026-08-08 sweep night, as one tidy table, plus
six derived tables that answer the questions we actually needed answered: which strategy
knobs move the win rate, which ones are structurally unreachable, what a competitive
opponent pool does to your metric, and — the uncomfortable one — whether local self-play
predicts the leaderboard at all.

**It does not.** That is the most useful thing in this dataset and it is stated up front
rather than buried.

---

## The result that should change how you test

We ran two of our own agents, `v8` and `v9`, against a 15-opponent pool, 192 paired
episodes each, 2,880 episodes per agent:

| agent | local pool win rate (n=2,880) | public leaderboard score |
|---|---|---|
| `v9` | **28.5%** [26.9, 30.2] | 752.7 |
| `v8` | 20.4% [19.0, 21.9] | **758.6** |

`v9` wins local self-play by eight points and is *behind* on the actual ladder. Against
the single opponent we tuned hardest against (`opp_c03`), the local gap is enormous —
42.7% vs 1.6% — and it still inverts on the board.

Look at `opponent_matrix.csv` and the reason is visible immediately: **9 of the 15
opponents sit at exactly 0.0% and 3 sit at exactly 100.0%.** Only a three-opponent cluster
is competitive at all. An "overall win rate" computed over that pool is mostly a readout of
who you put in the pool, not of how good your agent is.

If you are screening agent variants by local head-to-head win rate, this dataset is
evidence that the screen can rank two agents backwards. Use it, but do not let it pick your
submission on its own.

---

## What's in here

| file | rows | what it is |
|---|---|---|
| `episodes.csv` | 18,144 | one row per episode: sweep, config label, opponent, seed, seating, both final banks, win flag. Everything else is derived from this. |
| `config_benchmarks.csv` | 184 | per (sweep, config, opponent) and per-config overall: win rate with a Wilson 95% interval, plus the **paired** McNemar test against that sweep's own baseline arm. |
| `opponent_matrix.csv` | 15 | the pool matrix: `v8` and `v9` win rate and mean bank against each of the 15 opponents, plus their head-to-head discordance. |
| `local_vs_ladder.csv` | 2 | the rank inversion above, as data. |
| `shadowed_configs.csv` | 37 | which swept configurations returned **bank values byte-identical to baseline on every episode** — i.e. the knob was structurally unreachable. |
| `care_economics.csv` | 3 | the animal CARE mechanic priced out, recomputed live from the engine. |
| `episode_cost.csv` | 8 | measured wall-clock seconds per episode, so you can budget a sweep. |

---

## Verified findings

Every number below is recomputed from `episodes.csv` by
`scripts/gen_benchmark_dataset.py`; none of it is transcribed from a log.

**`max_quadrants=2` is the strongest lever we found.** Cutting land from three quadrants to
two moved the win rate against `opp_c03` from 57.3% to **81.2%** (n=96), paired **28 wins /
5 losses**, McNemar **z = +4.00**.

**`wheat_late_tiles=10` is a genuine second lever**: 57.3% → 67.7%, paired 11 W / 1 L,
z = +2.89.

Both are honest about their scope: **every discordant pair in the entire mix sweep lives
against `opp_c03`.** Against `opp_c25` and `opp_adaptive` both configurations are at 0.0%,
same as baseline. These are levers against one opponent, not general improvements.

**Five swept configurations were shadowed** — `strawberry_cap=40`, `strawberry_cap=50`,
`cap11_marg80`, `ctrl_cap16_only`, `ctrl_marg250_only` returned bank values identical to
baseline on all 384 episodes. The mechanism is worth internalising if your agent hires
labour: hand count is `min(max_hands, largest k where fib(k) <= hire_marginal_max)`. Wages
are Fibonacci, so **both gates must open together**; moving either one alone does literally
nothing. `fib(11) = 89`, which is why a marginal cap of 80 and a hand cap of 16 are each
individually inert.

Note the distinction `shadowed_configs.csv` lets you make: `water_window_mult=2.8` is *not*
shadowed — it has 22 discordant pairs — it simply had no *net* effect. "Had no effect" and
"could not have had an effect" are different claims and only the per-episode data separates
them.

**The CARE mechanic is an interval multiplier.** Caring for an animal banks a bonus that is
only spent on a production day, so it accumulates across the whole interval — the slower the
animal, the more CARE is worth. Recomputed by driving the engine's own
`_daily_refresh_animals` for a 30-day season, one animal, fed daily, harvested daily:

| animal | interval | units with CARE | units without | multiplier | net $/animal/day |
|---|---|---|---|---|---|
| GOOSE | 1 day | 56 | 27 | 2.07x | $75.00 |
| COW | 2 days | 39 | 12 | 3.25x | $215.00 |
| SHEEP | 3 days | 38 | 9 | **4.22x** | $241.67 |

Net figures are gross revenue at the base price with inventory at `I0`, less one wheat of
feed per day.

**Episode cost is ~1–2 seconds single-core**, not the ~21 seconds an earlier estimate in
this campaign assumed. That correction is the difference between "local sweeps are
impossible" and the 18,144 episodes in this file. See `episode_cost.csv` — and note the
measurement is load-dependent: repeat runs of the same built-in matchup on the same machine
ranged 0.62–1.67 s.

---

## Harness protocol

- **Both seatings, always.** Every configuration plays every seed at `swap=0` and `swap=1`,
  so seat advantage cancels within a pair. `episodes.csv` keeps the seating column so you
  can check this yourself rather than take our word for it.
- **Arms share seeds, so the comparison is paired.** This matters more than it sounds.
- **Use McNemar on the discordant pairs**, and look at the tie count. The paired and
  unpaired tests disagree materially on this data, and **not always in the same direction**:
  for `wheat_late_tiles=10` the unpaired z is +1.49 against a paired +2.89 (almost every
  pair is concordant, and the unpaired test cannot see that); for the `cap12_marg100` arm
  both tests agree it fails (+1.13 unpaired, +1.15 paired) because 67 of its 128 pairs are
  ties and carry no information at all.

  The reason this matters to us is a false positive we published and then had to retract.
  An extra-farm-hand configuration cleared an unpaired two-proportion test at z = 2.69 on
  an **earlier** sweep — a different seed set, not included in this dataset — and did not
  survive pairing. The lesson is not "unpaired is conservative" or "pairing is more
  powerful"; neither is true in general. It is: run the test your design implies, and if
  the design changes, recompute. Both arms of every comparison above are in `episodes.csv`,
  so you can check us.
- **Ties count as losses** (`win = ours > theirs`, strictly). Verified against the bank
  columns for all 18,144 rows at build time.
- **All 18,144 episodes completed.** No timeouts, no errored agents, no dropped rows.

The three sweeps:

| sweep | episodes | question |
|---|---|---|
| `pool_wide` | 5,760 | does `v9`'s local lift hold against 15 opponents rather than 3? |
| `mix_recheck` | 6,624 | 22 crop / herd / market parameters re-swept against a fixed baseline |
| `hire_frontier` | 5,760 | the joint `max_hands` × `hire_marginal_max` frontier, with one-gate control arms |

---

## What this dataset deliberately does NOT contain

- **No competition code and no competition data.** Nothing here is downloadable from the
  competition and re-hosted.
- **No other competitor's agent, notebook, or submission.** Some of the opponents in our
  local pool were reconstructed from public notebooks for use as sparring partners. **None
  of that code is in this dataset and none of it is redistributed.** Opponents appear only
  as opaque labels (`opp_c03`, `opp_moon`, …) attached to *our own* win/loss and bank
  measurements. If you want a specific opponent's policy, go read their notebook — we are
  not the right source and are not trying to be.
- **No submission artifact.** This is the measurement layer, not a bot.

---

## Caveats

- Bank values are the engine's own end-of-episode figures; win/loss is derived from them,
  not from the competition's ranking system.
- The leaderboard scores in `local_vs_ladder.csv` were read from the Kaggle submissions API
  at 2026-08-08 05:57 UTC. Ladder scores in this competition drift as the pool re-plays —
  they are a snapshot, and they are labelled with the read time for that reason.
- **CORRECTION (2026-08-09).** An earlier version of this card said all 18,144 episodes ran
  on `kaggle-environments` **1.32.6**. That was wrong. An engine-provenance audit found the
  three generating scripts (`kaggri-pool-wide`, `kaggri-mix-recheck`, `kaggri-hire-frontier`)
  each execute `pip install kaggle-environments==1.32.5`, suppress pip output, use
  `check=False`, and never print the imported version. The correct provenance is
  **1.32.5, probable but not verified at runtime** — the result logs show old-economy banks
  consistent with 1.32.5. The within-engine statistics here (pairing, McNemar, shadowing,
  the local-vs-ladder inversion) are unaffected, because every comparison is between arms
  run on the *same* engine. What is affected is any attempt to carry an absolute number
  here onto the live 1.32.6 economy: don't, without replicating.
- The 1.29.3 image that Kaggle's default notebook environment ships is a *different economy*
  again — same constants, materially different outcomes. **Assert your engine version in the
  artifact itself**, and print it; a guard that only checks constants is not enough, because
  1.29.3 and 1.32.6 agree on every constant we checked and still disagreed by 4.3x on
  outcomes. This card is itself the cautionary example.
- `opp_ensemble` and `opp_kaito177` returned identical banks on the same seed during
  timing, and several pool members are known clones of one another. Treat the 15 opponents
  as fewer than 15 independent policies.
- The shadowed configurations show that the two hiring gates interact. They do **not** imply
  that all neighbouring configurations are equivalent — only that those specific arms could
  not have differed.
- Everything here is measured against our own agents and our own pool. It is evidence about
  the *engine* and about *measurement method*; it is not a claim about the leaderboard, and
  the headline result is precisely that those two things came apart.

---

## Reproducing

`scripts/gen_benchmark_dataset.py` in the project repository rebuilds every file here from
the raw sweep logs plus a clean `kaggle-environments` install, in seconds. The `care_economics.csv`
and `episode_cost.csv` tables are computed live against the installed engine each time it runs.

## Companion work

- **Kaggriculture Engine Reference Tables**
  (`dariushafshar/kaggriculture-engine-reference-tables`) — the engine's constants, price
  curve, and growth schedules as plain CSV. Where this dataset is what happened when agents
  played, that one is the rulebook they played under.
- **CARE Is a 4.2x Multiplier: Animal Economics**
  (https://www.kaggle.com/code/dariushafshar/care-is-a-4-2x-multiplier-animal-economics) —
  a notebook that prices the CARE mechanic and ships a runnable husbandry bot.

License: CC0-1.0. Take it, fork it, check our arithmetic.
