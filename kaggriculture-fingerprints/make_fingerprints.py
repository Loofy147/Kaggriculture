"""Fingerprint every seat in the whole dataset, once, into a small table.

    .venv/bin/python research/census_at_scale.py --limit 0

Parsing 23,000 replays takes tens of minutes; classifying them takes seconds.
So this does the parsing ONCE and writes what the census actually reads: per
(episode, seat), a hash of the action stream at several prefix lengths, plus
the team, bank and time. Everything downstream -- clustering, the open-loop
proof, the divergence spectrum -- then runs on a few megabytes.

The prefix hashes are the whole trick. Two seats belong to the same schedule
at horizon N exactly when their hash at N matches, so clustering becomes a
group-by instead of an O(n^2) comparison. Divergence is then located by
bisection over the horizons rather than by scanning 720 turns for every pair.

`full_sha` is the stream hashed to the end. Two seats of the SAME team with
equal `full_sha`, from different episodes at different seeds, is the proof of
an open-loop agent that `research/fixed_schedules.py` requires.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
from dataset import connect, DATA                       # noqa: E402

LENGTHS = [24, 48, 100, 200, 300, 400, 500, 600, 719]
OUT = ROOT / "results/data/seat_fingerprints.parquet"


def canon(action):
    if not isinstance(action, dict):
        return "{}"
    return json.dumps(action, sort_keys=True, separators=(",", ":"))


def fingerprints(steps, seat):
    """Prefix hashes plus the full-stream hash, in one pass."""
    h = hashlib.sha256()
    out, k = {}, 0
    want = set(LENGTHS)
    for t in range(1, len(steps)):          # steps[0] carries no action
        st = steps[t]
        h.update(canon(st[seat].get("action") if len(st) > seat else None).encode())
        h.update(b"\x00")
        k += 1
        if k in want:
            out[f"h{k}"] = h.hexdigest()[:16]
    out["full_sha"] = h.hexdigest()[:16]
    out["turns"] = k
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--batch", type=int, default=4,
                    help="replays held in memory at once. Each replay_json "
                         "averages 27.5 MB decompressed and peaks at 36.8, so "
                         "a batch of 250 is ~7 GB and the OOM killer takes the "
                         "process (exit 137). Keep this small.")
    ap.add_argument("--teams", type=int, default=0,
                    help="team-stratified sample: N teams across four bands "
                         "of activity, all with >=2 episodes")
    ap.add_argument("--per-team", type=int, default=4,
                    help="episodes per sampled team")
    ap.add_argument("--sample", type=int, default=0,
                    help="fingerprint an evenly-spaced sample of N episodes "
                         "instead of all of them. The full corpus is 635 GB of "
                         "JSON; a sample answers the census questions in "
                         "minutes and says so honestly.")
    ap.add_argument("--random", type=int, default=0,
                    help="uniformly random sample of N public episodes. This is "
                         "the CONTROL for --teams: team-stratified sampling "
                         "over-weights teams with many episodes and packs the "
                         "corpus with within-team repeats, which can manufacture "
                         "both coarse concentration and fine fragmentation. Use "
                         "--out to keep it in its own table.")
    ap.add_argument("--seed", type=int, default=20260812,
                    help="seed for --random, so the sample is reproducible")
    ap.add_argument("--out", type=Path, default=OUT,
                    help="where to write. Two samples must NEVER share a file: "
                         "the resume logic keys on episode_id and would silently "
                         "merge them into a corpus that is neither.")
    ap.add_argument("--flush", type=int, default=4,
                    help="write partial results every N batches so a crash "
                         "costs minutes, not the whole pass")
    ap.add_argument("--restart", action="store_true",
                    help="ignore any existing output and start over")
    args = ap.parse_args()
    out_path = args.out

    con = connect()
    total = con.execute("SELECT count(*) FROM replays").fetchone()[0]
    n = total if args.limit == 0 else min(args.limit, total)
    print(f"fingerprinting {n} of {total} replays", flush=True)

    meta = {r[0]: r for r in con.execute(
        "SELECT episode_id, team_0, team_1, bank_0, bank_1, create_time, type "
        "FROM episodes").fetchall()}

    # RESUMABLE. This pass takes about an hour, and losing it to a crash once
    # was enough: partial results are flushed every `--flush` batches, and a
    # restart skips whatever is already on disk. The cost of a crash is now
    # minutes rather than the whole run.
    import pandas as pd
    have = set()
    if out_path.exists() and not args.restart:
        try:
            prev = pd.read_parquet(out_path)
            have = set(prev["episode_id"].tolist())
            rows_prev = prev.to_dict("records")
            print(f"resuming: {len(have)} episodes already fingerprinted")
        except Exception:
            rows_prev = []
    else:
        rows_prev = []

    # ONE query, streamed with fetchmany. Paging with LIMIT/OFFSET re-scans the
    # Parquet from the start on every page, so the cost grows quadratically and
    # a 23k-row pass that should take an hour takes considerably longer.
    if args.teams:
        # TEAM-STRATIFIED, because the open-loop proof needs two episodes of
        # the SAME team. Sampling episodes at random spreads thin across 2,380
        # teams and leaves most with one game, which proves nothing. Sampling
        # TEAMS and taking several of each keeps within-team pairs, which is
        # the only expensive thing here.
        rows = con.execute(f"""
            WITH seat AS (
              SELECT team_0 AS team, episode_id, create_time FROM episodes
                WHERE type='EPISODE_TYPE_PUBLIC'
              UNION ALL
              SELECT team_1, episode_id, create_time FROM episodes
                WHERE type='EPISODE_TYPE_PUBLIC'),
            g AS (SELECT team, count(*) n FROM seat GROUP BY 1 HAVING count(*) >= 2),
            band AS (SELECT team, n, ntile(4) OVER (ORDER BY n) AS b FROM g),
            pick AS (SELECT team FROM band QUALIFY
                     row_number() OVER (PARTITION BY b ORDER BY hash(team))
                       <= {max(1, args.teams // 4)}),
            e AS (SELECT s.team, s.episode_id,
                         row_number() OVER (PARTITION BY s.team
                                            ORDER BY s.create_time) AS k
                  FROM seat s JOIN pick p ON p.team = s.team)
            SELECT DISTINCT episode_id FROM e WHERE k <= {args.per_team}
        """).fetchall()
        ids = [r[0] for r in rows]
        print(f"team-stratified: {len(ids)} episodes from ~{args.teams} teams, "
              f"up to {args.per_team} each")
    elif args.random:
        # The control for --teams. Sample EPISODES, not teams: every public
        # episode has the same chance of being drawn, so the seat population is
        # the field's own, not a re-weighting of it. Seeded once, outside any
        # comprehension -- `random.Random(k)` constructed inside a loop re-seeds
        # every iteration and silently draws the same element N times.
        import random
        pool = [r[0] for r in con.execute(
            "SELECT e.episode_id FROM episodes e JOIN replays r USING(episode_id) "
            "WHERE e.type='EPISODE_TYPE_PUBLIC' ORDER BY e.episode_id").fetchall()]
        rng = random.Random(args.seed)
        ids = sorted(rng.sample(pool, min(args.random, len(pool))))
        print(f"random: {len(ids)} of {len(pool)} public episodes, seed {args.seed}")
    else:
        ids = [r[0] for r in con.execute(
            "SELECT episode_id FROM replays ORDER BY episode_id").fetchall()]
    if args.sample and args.sample < len(ids):
        step = len(ids) / args.sample
        ids = [ids[int(i * step)] for i in range(args.sample)]
        n = len(ids)
        print(f"evenly-spaced sample of {n} episodes across the corpus")
    ids = [i for i in ids if i not in have][:n]
    n = len(ids)          # the denominator is the work LEFT, not the corpus:
                          # reporting progress against 23,083 while doing 2,670
                          # made a 10-minute pass advertise a two-hour ETA.

    def stream():
        """One small chunk at a time, by id. Predicate pushdown keeps memory
        flat where a single streamed cursor materialised gigabytes."""
        for k in range(0, len(ids), args.batch):
            chunk = ids[k:k + args.batch]
            q = ("SELECT episode_id, replay_json FROM replays WHERE episode_id IN ("
                 + ",".join(str(int(x)) for x in chunk) + ")")
            yield con.execute(q).fetchall()
    pages = stream()
    rows, done, t0, skipped, since_flush = list(rows_prev), 0, time.time(), 0, 0

    def flush():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(out_path, index=False)

    for batch in pages:
        if not batch:
            continue
        for eid, js in batch:
            try:
                blob = json.loads(js)
                steps = blob.get("steps") or []
            except Exception:
                skipped += 1
                continue
            if len(steps) < 700:
                skipped += 1
                continue
            info = blob.get("info") or {}
            m = meta.get(eid)
            for seat in (0, 1):
                fp = fingerprints(steps, seat)
                fp.update({
                    "episode_id": eid, "seat": seat,
                    "team": (m[1 + seat] if m else None),
                    "team_name": ((info.get("TeamNames") or [None, None])[seat]),
                    "bank": (m[3 + seat] if m else None),
                    "create_time": str(m[5]) if m else None,
                    "type": (m[6] if m else None),
                    "seed": info.get("seed"),
                })
                rows.append(fp)
        done += len(batch)
        since_flush += 1
        if since_flush >= args.flush:
            flush(); since_flush = 0
        rate = done / max(1e-9, time.time() - t0)
        print(f"  {done}/{n}  {rate:.1f} replays/s  "
              f"eta {(n - done) / max(rate, 1e-9) / 60:.1f} min", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(out_path, index=False)
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path
    print(f"\n{len(df)} seat fingerprints ({skipped} replays skipped) -> "
          f"{shown} ({out_path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
