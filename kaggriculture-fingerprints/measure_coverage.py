"""Measure the community dataset's sampling probability, then reweight by it.

    .venv/bin/python research/coverage_audit.py --sample 250        # measure
    .venv/bin/python research/coverage_audit.py --report            # reweight

WHY THIS EXISTS. `georgymamarin/kaggriculture-episodes` is the only
analysis-ready corpus of this competition, and it is not a random sample. Its
`scrape.py` sorts submissions by most recent activity and stops at a time
budget, deferring the rest, so a submission's chance of being fully indexed
depends on how recently it played. Measured on two of them: one has 352 of its
352 in-window episodes present, another has 1 of 77.

That does not make the corpus unusable. It makes the corpus a SAMPLE WITH
UNEQUAL PROBABILITIES, which is a solved problem as long as you can estimate
the probabilities. This file estimates them.

THE MEASUREMENT. `ListEpisodes` is the same public endpoint the dataset's own
collector uses, unauthenticated, and it returns a submission's COMPLETE episode
list. So for any submission we can compute

    p(s) = (episodes of s in the dataset) / (episodes of s per the API,
                                             counted only up to the crawl cutoff)

without downloading a single replay. Episodes after the cutoff are excluded:
the dataset cannot be blamed for games played after it last ran.

THE ESTIMATOR. p(s) is measured on a sample of submissions and extrapolated to
the rest by strata, using the one covariate that is free and strongly related:
how many episodes of that submission the dataset already holds. Within a
stratum the ratio estimator is

    p_hat(stratum) = sum(dataset counts) / sum(API counts)

which is the standard combined ratio estimator, and it is more stable than
averaging per-submission ratios when some denominators are tiny. A seat then
carries weight 1 / p_hat(its submission's stratum).

WHAT THIS FIXES AND WHAT IT DOES NOT. It fixes frequency statements: how much
of the field plays an opening, how concentrated the field is. It does not fix
anything about WHICH episodes were kept inside a submission, so if the crawl
prefers a submission's early games over its late ones, that remains. And it
cannot recover a submission the crawl never touched at all; those are invisible
here and are a floor on the residual bias, quantified below as the share of
sampled submissions with zero coverage.

BE POLITE, AND THIS IS NOT DECORATION. A first attempt fired 270 requests at
1.2 s, which is the rate the dataset's own scraper uses -- but that scraper runs
once a day, not in a burst. The endpoint throttled us into ~30 s per request of
429 backoff, so the aggressive run was slower than the polite one would have
been, and it collected nothing. The default delay is now 6 s and small samples
are preferred. The cache is resumable and keyed by submission, so this is meant
to be run in short passes over days rather than in one sitting.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
from dataset import connect                               # noqa: E402

CACHE = ROOT / "results/data/coverage_audit.json"
LIST_URL = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
BINS = [0, 1, 2, 4, 8, 16, 32, 64, 128, 10 ** 9]


def dataset_counts(con):
    """Episodes per submission held by the dataset, and the crawl cutoff."""
    d = con.execute("""
        WITH s AS (SELECT sub_0 AS sub, episode_id FROM episodes
                     WHERE type='EPISODE_TYPE_PUBLIC'
                   UNION ALL
                   SELECT sub_1, episode_id FROM episodes
                     WHERE type='EPISODE_TYPE_PUBLIC')
        SELECT sub, count(DISTINCT episode_id) AS n FROM s
        WHERE sub IS NOT NULL GROUP BY 1""").df()
    cutoff = con.execute("SELECT max(create_time) FROM episodes").fetchone()[0]
    return d, str(cutoff)


def fetch(session, sid, cutoff, delay, tries=3):
    """The submission's true public-episode count up to the crawl cutoff.

    Returns (count, status). Throttling here is ambient rather than transient,
    exactly as the dataset's own scraper notes, so a 429 is retried with a
    pause. An earlier version returned None on any non-200 and logged nothing,
    which turned 249 rate-limited requests into a silent 21-submission sample
    that still printed a confident total.
    """
    for attempt in range(tries):
        r = session.post(LIST_URL, json={"submissionId": int(sid)}, timeout=30)
        if r.status_code == 429:
            # HONOUR Retry-After. An earlier version backed off 5, 10, 15
            # seconds while the server was asking for 30, so every retry landed
            # inside the window it had just been told to wait out and the run
            # never recovered. The server states the answer; do not guess it.
            wait = r.headers.get("Retry-After")
            try:
                wait = float(wait)
            except (TypeError, ValueError):
                wait = 30.0
            time.sleep(wait + 1)
            continue
        time.sleep(delay)
        break
    if r.status_code != 200:
        return None, r.status_code
    eps = r.json().get("episodes", [])
    n = 0
    for e in eps:
        if e.get("type") != "EPISODE_TYPE_PUBLIC":
            continue
        # createTime is ISO with a Z; the cutoff is a local-tz string from the
        # CSV. Compare on the date+time prefix in UTC by normalising both.
        t = str(e.get("createTime") or "")
        if t and t[:19] <= _utc_prefix(cutoff):
            n += 1
    return n, 200


def _utc_prefix(cutoff):
    """The cutoff as a bare UTC 'YYYY-MM-DDTHH:MM:SS' string."""
    ts = pd.Timestamp(cutoff)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def measure(args):
    import requests
    con = connect()
    counts, cutoff = dataset_counts(con)
    print(f"{len(counts):,} submissions in the dataset, crawl cutoff {cutoff}")
    print(f"cutoff in UTC: {_utc_prefix(cutoff)}\n")

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    known = cache.get("api", {})

    # Stratified so the whole range of dataset-side counts is represented, not
    # just the crowded bottom. Sampling uniformly would put almost every draw
    # in the 1-2 episode bin and say nothing about the well-covered tail.
    counts["stratum"] = pd.cut(counts["n"], BINS, labels=False, right=True)
    rng = np.random.default_rng(args.seed)
    picks = []
    per = max(1, args.sample // counts.stratum.nunique())
    for st, g in counts.groupby("stratum"):
        take = g.sample(n=min(per, len(g)), random_state=int(rng.integers(1 << 31)))
        picks += take["sub"].tolist()
    picks = [s for s in picks if str(s) not in known]
    print(f"sampling {len(picks)} submissions ({per} per stratum), "
          f"{len(known)} already cached")

    from collections import Counter
    session = requests.Session()
    session.headers["User-Agent"] = "kaggriculture-coverage-audit (research)"
    fails = Counter()
    for i, sid in enumerate(picks, 1):
        try:
            n, status = fetch(session, sid, cutoff, args.delay)
        except Exception as exc:
            fails[type(exc).__name__] += 1
            continue
        if n is None:
            fails[f"HTTP {status}"] += 1
        else:
            known[str(sid)] = n
        if i % 25 == 0:
            print(f"  {i}/{len(picks)}  ok {len(known)}  failed {sum(fails.values())} "
                  f"{dict(fails)}", flush=True)
            CACHE.write_text(json.dumps({"api": known, "cutoff": cutoff}, indent=0))
    CACHE.write_text(json.dumps({"api": known, "cutoff": cutoff}, indent=0))
    print(f"\ncached {len(known)} submissions, {sum(fails.values())} failed {dict(fails)}")
    if fails:
        print("  A failed request is NOT a zero-coverage submission. It is a gap in")
        print("  the measurement, and the report below refuses to extrapolate over it.")


def report(args):
    con = connect()
    counts, cutoff = dataset_counts(con)
    cache = json.loads(CACHE.read_text())
    api = {int(k): v for k, v in cache["api"].items()}
    counts["api"] = counts["sub"].map(api)
    m = counts.dropna(subset=["api"]).copy()
    m = m[m.api > 0]
    print(f"{len(m)} submissions measured against the API\n")

    m["stratum"] = pd.cut(m["n"], BINS, labels=False, right=True)
    counts["stratum"] = pd.cut(counts["n"], BINS, labels=False, right=True)

    print("COVERAGE BY STRATUM  (combined ratio estimator per stratum)\n")
    hdr = (f"{'dataset episodes':>18}{'subs measured':>15}{'dataset':>10}"
           f"{'API':>10}{'coverage':>11}{'zero-cov subs':>15}")
    print(hdr); print("-" * len(hdr))
    p = {}
    for st, g in m.groupby("stratum"):
        cov = g.n.sum() / g.api.sum()
        p[st] = cov
        lo, hi = BINS[int(st)], BINS[int(st) + 1]
        label = f"{lo + 1}-{hi}" if hi < 10 ** 9 else f"{lo + 1}+"
        print(f"{label:>18}{len(g):>15}{int(g.n.sum()):>10}{int(g.api.sum()):>10}"
              f"{100 * cov:>10.1f}%{int((g.n == 0).sum()):>15}")

    # Overall, weighted by how many seats each stratum contributes. This REFUSES
    # to run unless every stratum has been measured: pandas skips NaN in .sum(),
    # so extrapolating over unmeasured strata silently drops their seats and
    # still prints a confident total. The first version of this file did that.
    counts["p"] = counts["stratum"].map(p)
    counts["w"] = 1.0 / counts["p"]
    total_seats = counts["n"].sum()
    unmeasured = counts[counts["p"].isna()]
    if len(unmeasured):
        miss = sorted(unmeasured["stratum"].dropna().unique())
        print(f"\n  NO OVERALL ESTIMATE. {len(miss)} of {counts['stratum'].nunique()} "
              f"strata have no measurement, covering "
              f"{int(unmeasured['n'].sum()):,} of {int(total_seats):,} seats "
              f"({100 * unmeasured['n'].sum() / total_seats:.0f} %).")
        print(f"  Unmeasured strata (by dataset episodes): "
              f"{[f'{BINS[int(k)] + 1}-{BINS[int(k) + 1]}' for k in miss]}")
        print("  Re-run the measurement until they are covered; an average over the")
        print("  strata that happened to succeed is not an estimate of anything.")
        return
    est_true = (counts["n"] * counts["w"]).sum()
    print(f"\n  seats in the dataset        {int(total_seats):>12,}")
    print(f"  estimated seats in the field{est_true:>12,.0f}")
    print(f"  implied overall coverage    {100 * total_seats / est_true:>11.1f} %")
    print("\n  The estimate is a LOWER bound on the field: a submission the crawl")
    print("  never touched contributes nothing to any stratum and cannot be seen")
    print("  from inside the corpus at all.")

    out = counts[["sub", "n", "stratum", "p", "w"]]
    out.to_parquet(ROOT / "results/data/coverage_weights.parquet", index=False)
    print(f"\nwrote results/data/coverage_weights.parquet "
          f"({len(out)} submissions with a weight)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=250)
    ap.add_argument("--delay", type=float, default=6.0,
                    help="seconds between requests. The dataset's own scraper "
                         "uses 1.2, but it runs ONCE A DAY; a 270-request burst "
                         "at that rate got this throttled to ~30 s per request "
                         "in 429 retries, which is slower than being polite in "
                         "the first place. Default deliberately slow.")
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        report(args)
    else:
        measure(args)
        report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
