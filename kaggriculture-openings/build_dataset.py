"""Extract top-player opening data from downloaded episode replays.

Produces three CSVs:
  1. openings_summary.csv  — one row per (team, episode): aggregate opening spend
  2. openings_actions.csv  — one row per farmer/market action in the first 2 days
  3. openings_clusters.csv — team → strategy cluster classification
"""
import json
import os
import csv
import collections

CACHE = "C:/Users/iamre/AppData/Local/Temp/claude/C--Users-iamre-Boat/30a8441c-2600-4ac8-be05-68fcc23d00d9/scratchpad/top5_eps"
OUT_DIR = "C:/Users/iamre/kaggriculture-dataset"
FIRST_TURNS = 48   # first 2 in-game days (24 turns × 2)

TARGET_TEAM_NAMES = {
    "Seb":          "Seb",
    "HealthStone":  "HealthStone",
    "tao_wu11":     "tao wu11",
    "Mohamed":      "Mohamed abdelrazik",
    "mrgrishninsb": "mrgrishninsb",
}
LADDER_SCORE = {
    "Seb": 3201.1, "HealthStone": 3132.9, "tao_wu11": 3131.4,
    "Mohamed": 3123.1, "mrgrishninsb": 3117.6,
}


def _seat(names, team_key):
    tt = TARGET_TEAM_NAMES.get(team_key, team_key).lower()
    for i, n in enumerate(names):
        if tt in (n or "").lower():
            return i
    return 0


files = sorted(f for f in os.listdir(CACHE) if f.endswith(".json"))

# ------------------------------------------------------------------
# Extract per-episode summaries + per-turn actions
# ------------------------------------------------------------------
summary_rows = []
action_rows = []

for fn in files:
    team_key, rest = fn.split("__", 1)
    ep_id = rest.replace(".json", "")
    d = json.load(open(os.path.join(CACHE, fn), encoding="utf-8"))
    names = d["info"]["TeamNames"]
    seat = _seat(names, team_key)
    steps = d["steps"][:FIRST_TURNS]

    # Aggregate spend
    market = collections.Counter()
    farmer = collections.Counter()
    for i, st in enumerate(steps):
        obs = st[0].get("observation") or {}
        day = obs.get("day", i // 24)
        hour = obs.get("hour", i % 24)
        farm_state = obs.get("farms", [{}])[seat] if obs.get("farms") else {}
        money = farm_state.get("money", None)

        a = st[seat].get("action")
        if not isinstance(a, dict):
            continue

        f_act = a.get("farmer") or []
        if f_act:
            farmer[f_act[0]] += 1
            action_rows.append({
                "team": team_key,
                "episode_id": ep_id,
                "turn": i,
                "day": day,
                "hour": hour,
                "money": money if money is not None else "",
                "actor": "farmer",
                "action": f_act[0],
                "arg1": f_act[1] if len(f_act) > 1 else "",
                "arg2": f_act[2] if len(f_act) > 2 else "",
            })

        for hi, h_act in enumerate(a.get("hands") or []):
            if h_act:
                action_rows.append({
                    "team": team_key,
                    "episode_id": ep_id,
                    "turn": i,
                    "day": day,
                    "hour": hour,
                    "money": money if money is not None else "",
                    "actor": f"hand_{hi}",
                    "action": h_act[0],
                    "arg1": h_act[1] if len(h_act) > 1 else "",
                    "arg2": h_act[2] if len(h_act) > 2 else "",
                })

        for m in (a.get("market") or []):
            if not m:
                continue
            op = m[0]
            if op in ("HIRE", "BUY_LAND"):
                market[op] += 1
            elif op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "SELL"):
                key = f"{op}_{m[1] if len(m) > 1 else ''}"
                market[key] += int(m[2]) if len(m) > 2 else 1
            action_rows.append({
                "team": team_key,
                "episode_id": ep_id,
                "turn": i,
                "day": day,
                "hour": hour,
                "money": money if money is not None else "",
                "actor": "market",
                "action": op,
                "arg1": m[1] if len(m) > 1 else "",
                "arg2": m[2] if len(m) > 2 else "",
            })

    # Final reward
    r = d.get("rewards", [0, 0])
    final_reward = r[seat] if len(r) > seat else 0
    opponent = names[1 - seat] if len(names) > 1 else "?"

    summary_rows.append({
        "team": team_key,
        "episode_id": ep_id,
        "opponent": opponent,
        "final_reward": final_reward,
        "ladder_score": LADDER_SCORE.get(team_key, ""),
        "hires_first48": market.get("HIRE", 0),
        "land_first48": market.get("BUY_LAND", 0),
        "cows_first48": market.get("BUY_ANIMAL_COW", 0),
        "sheep_first48": market.get("BUY_ANIMAL_SHEEP", 0),
        "geese_first48": market.get("BUY_ANIMAL_GOOSE", 0),
        "wheat_seeds_first48": market.get("BUY_SEED_WHEAT", 0),
        "melon_seeds_first48": market.get("BUY_SEED_MELON", 0),
        "strawberry_seeds_first48": market.get("BUY_SEED_STRAWBERRY", 0),
        "wheat_bought_first48": market.get("BUY_PRODUCT_WHEAT", 0),
        "sold_wheat_first48": market.get("SELL_WHEAT", 0),
        "sold_fertilizer_first48": market.get("SELL_FERTILIZER", 0),
    })

# ------------------------------------------------------------------
# Cluster classifications from our analysis
# ------------------------------------------------------------------
clusters = [
    {"team": "Seb", "ladder_score": 3201.1,
     "cluster": "counter_meta",
     "signature": "14 hires day0, 4 quads eventual, 9C+11S final, aggressive labor",
     "public_agent": False,
     "notes": "Rank 1 on leaderboard. Big-footprint counter to standard fork race."},
    {"team": "HealthStone", "ladder_score": 3132.9,
     "cluster": "sheep_first_hybrid",
     "signature": "3 hires day0, 1C+4S day0, 8C+4S final, sheep-first CARE",
     "public_agent": False,
     "notes": "Rank 2. Sheep-first exploits CARE compounding (3-day interval)."},
    {"team": "tao_wu11", "ladder_score": 3131.4,
     "cluster": "v23_fork",
     "signature": "5 hires day0, 2C+2S day0, 8C+6S final, 7W/12M/0S seeds",
     "public_agent": True,
     "notes": "Identical opening to Mohamed, mrgrishninsb, v23 self-play."},
    {"team": "Mohamed", "ladder_score": 3123.1,
     "cluster": "v23_fork",
     "signature": "5 hires day0, 2C+2S day0, 8C+6S final, 7W/12M/0S seeds",
     "public_agent": True,
     "notes": "Same opening signature as v23 (kaitofukami)."},
    {"team": "mrgrishninsb", "ladder_score": 3117.6,
     "cluster": "v23_fork",
     "signature": "5 hires day0, 2C+2S day0, 8C+6S final, 7W/12M/0S seeds",
     "public_agent": True,
     "notes": "Same opening signature as v23."},
]

# ------------------------------------------------------------------
# Write CSVs
# ------------------------------------------------------------------
def write_csv(path, rows, fieldnames=None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


write_csv(os.path.join(OUT_DIR, "openings_summary.csv"), summary_rows)
write_csv(os.path.join(OUT_DIR, "openings_actions.csv"), action_rows)
write_csv(os.path.join(OUT_DIR, "openings_clusters.csv"), clusters)

print(f"summary rows: {len(summary_rows)}")
print(f"action rows:  {len(action_rows)}")
print(f"cluster rows: {len(clusters)}")
print()
print("preview of openings_summary.csv:")
for r in summary_rows[:3]:
    print(r)
