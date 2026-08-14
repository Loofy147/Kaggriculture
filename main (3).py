"""
Kaggriculture agent.

Strategy (see chat for the full write-up):
  - CORE engine: Wheat + Goose/Egg. Both sit at the flat end of the market's
    price curve (above_target 0.20 for each), so they can be mass-produced
    and sold every turn without crashing our own price. This is the
    compounding backbone of the bank balance.
  - MODERATE: Carrot + Tomato. Decent yield, medium glut sensitivity -
    planted in smaller numbers, sold whenever price is reasonable.
  - OPPORTUNISTIC: Melon (+ later Cow/Milk). Highest nominal $/tile/day but
    the steepest glut penalty (above_target 3.60) and the smallest T needed
    to trigger it - capped in quantity and only sold while price is still
    healthy, otherwise held in the shed. Sheep/Wool is skipped by default:
    worst combination of small T and high above_target in the whole table.
  - Opponent-aware selling: the opponent's tiles are fully visible. If they
    are sitting on a lot of mature tiles of something we also grow, we bias
    toward selling/harvesting that resource sooner rather than later, since
    whoever sells first gets the pre-glut price.

Engineering notes:
  - Movement direction signs (does NORTH mean y-1 or y+1?) are not specified
    anywhere we could verify, so the agent starts from the standard
    (0,0)=top-left / NORTH=y-1 / EAST=x+1 assumption and self-corrects at
    runtime if a move's observed result doesn't match what was predicted.
    Costs at most ~1 wasted turn per axis if the assumption was backwards;
    costs nothing if it was right.
  - All positional reasoning (shed location, quadrant boundaries) is derived
    from the observed board size at runtime rather than hardcoded, so it
    still works if boardSize is reconfigured.
  - Never assumes an action succeeded; everything is re-derived from the
    fresh observation every turn (no open-loop planning), so a silently
    dropped/no-op action just gets retried or superseded next turn instead
    of desyncing internal state.
"""

# --------------------------------------------------------------------------
# Config: game constants taken directly from the competition spec
# --------------------------------------------------------------------------

CROP_INFO = {
    # seed_cost, base_price, first_yield_day, max_yield_day, ongoing?
    "WHEAT":      dict(seed_cost=10,  base_price=25,  first_yield_day=2,  max_yield_day=4,  ongoing=False),
    "CARROT":     dict(seed_cost=20,  base_price=35,  first_yield_day=2,  max_yield_day=3,  ongoing=False),
    "TOMATO":     dict(seed_cost=50,  base_price=60,  first_yield_day=8,  max_yield_day=11, ongoing=True),
    "STRAWBERRY": dict(seed_cost=100, base_price=120, first_yield_day=10, max_yield_day=16, ongoing=True),
    "MELON":      dict(seed_cost=80,  base_price=250, first_yield_day=10, max_yield_day=10, ongoing=False),
}

ANIMAL_INFO = {
    # cost, product, base_price, structure needed, first_yield_day
    "GOOSE": dict(cost=300, product="EGG",  base_price=50,  structure="COOP",    first_yield_day=4),
    "COW":   dict(cost=400, product="MILK", base_price=160, structure="PASTURE", first_yield_day=8),
    "SHEEP": dict(cost=500, product="WOOL", base_price=200, structure="PASTURE", first_yield_day=6),
}

# Crop planting mix (fractions of currently-planted crop tiles we aim for).
CROP_TARGET_FRACTION = {
    "WHEAT": 0.45,
    "CARROT": 0.15,
    "TOMATO": 0.15,
    "MELON": 0.15,
    "STRAWBERRY": 0.10,
}

# Only fertilize crops where the price payoff clearly beats the $100 cost.
FERTILIZE_WORTHY = {"MELON", "TOMATO", "STRAWBERRY", "CARROT"}

# Hold (don't sell) these below this fraction of base price; core goods are
# always sold immediately since their price floor is already high.
SELL_FLOOR_FRACTION = {
    "CARROT": 0.45,
    "TOMATO": 0.45,
    "MELON": 0.55,
    "STRAWBERRY": 0.55,
    "MILK": 0.55,
    "WOOL": 0.55,
}
CORE_SELL_ALWAYS = {"EGG"}

FERTILIZER_COST = 100
MAX_MARKET_ORDERS = 10           # documented default; safe conservative cap
SHED_SAFETY_MARGIN = 15          # start force-selling opportunistic goods once shed is this close to its 100 cap
MAX_HANDS = 6                    # soft cap; fib hiring cost gets steep past here
CASH_RESERVE = 150               # try not to spend the bank down below this
LAND_ORDER = ["NE", "SW", "SE"]
LAND_COST = {"NE": 1000, "SW": 2000, "SE": 4000}

DIRS = ("NORTH", "SOUTH", "EAST", "WEST")

# --------------------------------------------------------------------------
# Global (module-level) state - persists across agent() calls within one episode
# --------------------------------------------------------------------------

_STATE = {
    "day": -1,
    "dir_delta": {  # standard assumption: (0,0) top-left, x right, y down
        "NORTH": (0, -1),
        "SOUTH": (0, 1),
        "EAST": (1, 0),
        "WEST": (-1, 0),
    },
    "dir_calibrated": {"NORTH": False, "SOUTH": False, "EAST": False, "WEST": False},
    "last_pos": {},      # unit_id -> (x, y) observed at start of previous turn
    "last_dir": {},      # unit_id -> direction issued last turn (or None)
    "hands_seen_today": 0,
}


def _reset_for_new_day():
    _STATE["last_pos"] = {}
    _STATE["last_dir"] = {}
    _STATE["hands_seen_today"] = 0


def _calibrate_direction(unit_id, cur_pos):
    """Compare where a unit actually ended up to where we predicted, and
    correct our NORTH/SOUTH/EAST/WEST -> (dx, dy) mapping if it disagrees."""
    prev_dir = _STATE["last_dir"].get(unit_id)
    prev_pos = _STATE["last_pos"].get(unit_id)
    if prev_dir is None or prev_pos is None:
        return
    dx = cur_pos[0] - prev_pos[0]
    dy = cur_pos[1] - prev_pos[1]
    if abs(dx) + abs(dy) != 1:
        # (0,0): no-op (blocked at edge, or a locked-tile action no-op that
        # didn't move us) - ambiguous, learn nothing. >1: shouldn't happen.
        return
    observed = (dx, dy)
    if observed != _STATE["dir_delta"][prev_dir]:
        _STATE["dir_delta"][prev_dir] = observed
        _STATE["dir_calibrated"][prev_dir] = True


def _step_toward(cur, target):
    """Return a single direction command that reduces Manhattan distance
    from cur to target, or None if already there."""
    cx, cy = cur
    tx, ty = target
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return None
    # Prefer correcting the larger gap first.
    candidates = []
    if dx != 0:
        candidates.append(("EAST" if dx > 0 else "WEST", abs(dx)))
    if dy != 0:
        candidates.append(("SOUTH" if dy > 0 else "NORTH", abs(dy)))
    candidates.sort(key=lambda t: -t[1])
    wanted_name = candidates[0][0]
    # Translate the *logical* direction we want into whichever DIRS token
    # currently produces that delta, per our (possibly-calibrated) mapping.
    wanted_delta = {"EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, 1), "NORTH": (0, -1)}[wanted_name]
    for name, delta in _STATE["dir_delta"].items():
        if delta == wanted_delta:
            return name
    # Fallback (shouldn't happen once all 4 are known): use the raw name.
    return wanted_name


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# --------------------------------------------------------------------------
# Board helpers
# --------------------------------------------------------------------------

def _quadrant_of(x, y, half):
    if x < half and y < half:
        return "NW"
    if x >= half and y < half:
        return "NE"
    if x < half and y >= half:
        return "SW"
    return "SE"


def _shed_tiles(half):
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


# --------------------------------------------------------------------------
# Farm scan: turn the raw tile grid into prioritized task lists
# --------------------------------------------------------------------------

def _scan_farm(me, day, unlocked, half):
    tiles = me["tiles"]
    board = len(tiles)

    needs_water = []       # (x, y)
    harvest_ready = []     # (x, y, crop)
    weeds = []              # (x, y)
    empty_tiles = []        # (x, y)
    needs_fertilize = []    # (x, y, crop)
    empty_structures = []   # (x, y, kind)  kind = COOP/PASTURE
    animal_needs_feed = []  # (x, y)
    animal_needs_care = []  # (x, y)
    animal_fert_ready = []  # (x, y)
    animal_ready_harvest = []  # (x, y)
    crop_counts = {c: 0 for c in CROP_INFO}

    for y in range(board):
        for x in range(board):
            if _quadrant_of(x, y, half) not in unlocked:
                continue
            tile = tiles[y][x]
            if tile is None:
                if (x, y) not in _shed_tiles(half):
                    empty_tiles.append((x, y))
                continue
            if tile == "LOCKED":
                continue
            kind = tile.get("kind")
            if kind == "WEED":
                weeds.append((x, y))
            elif kind == "PLANT":
                crop = tile["crop"]
                crop_counts[crop] = crop_counts.get(crop, 0) + 1
                age = day - tile["planted_day"]
                if not tile.get("watered_today", False):
                    needs_water.append((x, y))
                if age >= CROP_INFO[crop]["first_yield_day"] and (tile.get("yield_units", 0) > 0 or age >= CROP_INFO[crop]["max_yield_day"]):
                    harvest_ready.append((x, y, crop))
                elif (
                    crop in FERTILIZE_WORTHY
                    and tile.get("fertilized_until_day", -1) < day
                    and age < CROP_INFO[crop]["max_yield_day"]
                ):
                    needs_fertilize.append((x, y, crop))
            elif kind in ("COOP", "PASTURE"):
                if tile.get("animal") is None:
                    empty_structures.append((x, y, kind))
                else:
                    if not tile.get("fed_today", False):
                        animal_needs_feed.append((x, y))
                    elif not tile.get("cared_today", False):
                        animal_needs_care.append((x, y))
                    if tile.get("fertilizer_available", False):
                        animal_fert_ready.append((x, y))
                    if tile.get("yield_units", 0) > 0:
                        animal_ready_harvest.append((x, y))

    return dict(
        needs_water=needs_water,
        harvest_ready=harvest_ready,
        weeds=weeds,
        empty_tiles=empty_tiles,
        needs_fertilize=needs_fertilize,
        empty_structures=empty_structures,
        animal_needs_feed=animal_needs_feed,
        animal_needs_care=animal_needs_care,
        animal_fert_ready=animal_fert_ready,
        animal_ready_harvest=animal_ready_harvest,
        crop_counts=crop_counts,
    )


def _pick_crop_to_plant(crop_counts, seeds, money):
    total = sum(crop_counts.values()) or 1
    best_crop, best_score = None, None
    for crop, target in CROP_TARGET_FRACTION.items():
        have = seeds.get(crop, 0) > 0 or money >= CROP_INFO[crop]["seed_cost"]
        if not have:
            continue
        current_frac = crop_counts.get(crop, 0) / total
        score = target - current_frac
        if best_score is None or score > best_score:
            best_crop, best_score = crop, score
    return best_crop


# --------------------------------------------------------------------------
# Task assignment: give each unit (farmer + hands) one op this turn
# --------------------------------------------------------------------------

def _assign_units(units, tasks, private, me, opp_pressure, half, step):
    ops = {}
    claimed = set()
    seeds = private.get("seeds", {})
    seeds_left = {k: int(v) for k, v in seeds.items()}
    inventories = list(private.get("inventories") or [])
    shed = dict(private.get("shed", {}))
    money = me["money"]

    # Define targets based on unlocked quadrants to avoid feed-bill bankruptcy
    unlocked_quads = me["unlocked_quadrants"]
    if len(unlocked_quads) >= 4:
        PASTURE_TARGET = 7
        COOP_TARGET = 1
    elif len(unlocked_quads) >= 3:
        PASTURE_TARGET = 6
        COOP_TARGET = 1
    elif len(unlocked_quads) >= 2:
        PASTURE_TARGET = 3
        COOP_TARGET = 1
    else:
        PASTURE_TARGET = 1
        COOP_TARGET = 1

    # Count current coops and pastures built on our farm
    coops_count = 0
    pastures_count = 0
    for row in me["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                if tile.get("kind") == "COOP":
                    coops_count += 1
                elif tile.get("kind") == "PASTURE":
                    pastures_count += 1

    can_build_coop = (step < 500) and (coops_count < COOP_TARGET) and (money >= 600 or shed.get("GOOSE", 0) > 0)
    can_build_pasture = (step < 500) and (pastures_count < PASTURE_TARGET) and (money >= 800 or shed.get("COW", 0) > 0 or shed.get("SHEEP", 0) > 0)

    def claim_nearest(pos_list, unit_pos):
        avail = [p for p in pos_list if p not in claimed]
        if not avail:
            return None
        best = min(avail, key=lambda p: (_manhattan(unit_pos, (p[0], p[1])), p[1], p[0]))
        claimed.add(best)
        return best

    # Priority tiers, highest first: survival > cashing in > cleanup > growth > polish
    for unit_id, pos in units:
        assigned = False
        unit_index = 0 if unit_id == "farmer" else int(unit_id.replace("hand", "")) + 1
        unit_inventory = inventories[unit_index] if unit_index < len(inventories) else {}

        # 1. Feed animals / water plants that are about to die.
        # Check animal feeding first (critical survival!)
        target = claim_nearest(tasks["animal_needs_feed"], pos)
        if target is not None:
            if unit_inventory.get("WHEAT", 0) > 0:
                if pos == (target[0], target[1]):
                    ops[unit_id] = ["FEED"]
                    unit_inventory["WHEAT"] -= 1
                else:
                    ops[unit_id] = [_step_toward(pos, (target[0], target[1]))]
                assigned = True
            else:
                # We need wheat to feed! Let's release the target and go pick up wheat from the shed
                claimed.remove(target)
                if shed.get("WHEAT", 0) > 0:
                    shed_tiles = _shed_tiles(half)
                    if pos in shed_tiles:
                        pickup_qty = min(5, shed["WHEAT"])
                        ops[unit_id] = ["PICKUP", "WHEAT", pickup_qty]
                        shed["WHEAT"] -= pickup_qty
                        assigned = True
                    else:
                        target_shed = min(shed_tiles, key=lambda s: _manhattan(pos, s))
                        ops[unit_id] = [_step_toward(pos, target_shed)]
                        assigned = True

        if assigned:
            continue

        # Water plants
        target = claim_nearest(tasks["needs_water"], pos)
        if target is not None:
            if pos == target:
                ops[unit_id] = ["WATER"]
            else:
                ops[unit_id] = [_step_toward(pos, target)]
            assigned = True

        if assigned:
            continue

        # 2. Harvest anything ready (bank the cash), incl. animal products.
        crop_targets = [(x, y) for (x, y, _c) in tasks["harvest_ready"]]
        target = claim_nearest(crop_targets, pos)
        if target is None:
            target = claim_nearest(tasks["animal_ready_harvest"], pos)
        if target is not None:
            if pos == (target[0], target[1]):
                ops[unit_id] = ["HARVEST"]
            else:
                ops[unit_id] = [_step_toward(pos, (target[0], target[1]))]
            assigned = True

        if assigned:
            continue

        # 3. Clear weeds.
        target = claim_nearest(tasks["weeds"], pos)
        if target is not None:
            ops[unit_id] = ["DIG"] if pos == target else [_step_toward(pos, target)]
            assigned = True

        if assigned:
            continue

        # 3.5. Place animals on built empty structures if we have them in inventory or shed
        # Check if this unit is already carrying an animal
        carrying_animal = None
        for anim in ("COW", "SHEEP", "GOOSE"):
            if unit_inventory.get(anim, 0) > 0:
                carrying_animal = anim
                break

        if carrying_animal is not None:
            matching_kind = "COOP" if carrying_animal == "GOOSE" else "PASTURE"
            empty_matching = [p for p in tasks["empty_structures"] if p[2] == matching_kind and p not in claimed]
            if empty_matching:
                target = min(empty_matching, key=lambda p: _manhattan(pos, (p[0], p[1])))
                claimed.add(target)
                if pos == (target[0], target[1]):
                    ops[unit_id] = ["PLACE", carrying_animal]
                else:
                    ops[unit_id] = [_step_toward(pos, (target[0], target[1]))]
                assigned = True

        if assigned:
            continue

        if tasks["empty_structures"]:
            available_animals = []
            for p in tasks["empty_structures"]:
                matching_animal = "GOOSE" if p[2] == "COOP" else ("COW" if shed.get("COW", 0) > 0 else ("SHEEP" if shed.get("SHEEP", 0) > 0 else None))
                if matching_animal and shed.get(matching_animal, 0) > 0:
                    available_animals.append((p, matching_animal))

            if available_animals:
                shed_tiles = _shed_tiles(half)
                if pos in shed_tiles:
                    p, matching_animal = available_animals[0]
                    ops[unit_id] = ["PICKUP", matching_animal, 1]
                    shed[matching_animal] -= 1
                    assigned = True
                else:
                    target_shed = min(shed_tiles, key=lambda s: _manhattan(pos, s))
                    ops[unit_id] = [_step_toward(pos, target_shed)]
                    assigned = True

        if assigned:
            continue

        # 3.6. Build structures (COOP / PASTURE)
        if can_build_coop or can_build_pasture:
            target = claim_nearest(tasks["empty_tiles"], pos)
            if target is not None:
                if pos == target:
                    if can_build_coop:
                        ops[unit_id] = ["BUILD_COOP"]
                        coops_count += 1
                        can_build_coop = (coops_count < COOP_TARGET)
                    else:
                        ops[unit_id] = ["BUILD_PASTURE"]
                        pastures_count += 1
                        can_build_pasture = (pastures_count < PASTURE_TARGET)
                else:
                    ops[unit_id] = [_step_toward(pos, target)]
                assigned = True

        if assigned:
            continue

        # 4. Care for fed animals / collect fertilizer.
        target = claim_nearest(tasks["animal_needs_care"], pos)
        if target is None:
            target = claim_nearest(tasks["animal_fert_ready"], pos)
            op_name = "COLLECT_FERTILIZER"
        else:
            op_name = "CARE"
        if target is not None:
            ops[unit_id] = [op_name] if pos == (target[0], target[1]) else [_step_toward(pos, (target[0], target[1]))]
            assigned = True

        if assigned:
            continue

        # 5. Plant empty tiles (only if we can afford / already hold a seed).
        if tasks["empty_tiles"]:
            crop = _pick_crop_to_plant(tasks["crop_counts"], seeds, money)
            if crop is not None:
                target = claim_nearest(tasks["empty_tiles"], pos)
                if target is not None:
                    if pos == target:
                        if seeds_left.get(crop, 0) > 0:
                            ops[unit_id] = ["PLANT", crop]
                            seeds_left[crop] -= 1
                            assigned = True
                        else:
                            alternative_crop = None
                            for alt_c in CROP_INFO:
                                if seeds_left.get(alt_c, 0) > 0:
                                    alternative_crop = alt_c
                                    break
                            if alternative_crop is not None:
                                ops[unit_id] = ["PLANT", alternative_crop]
                                seeds_left[alternative_crop] -= 1
                                assigned = True
                            else:
                                claimed.remove(target)
                    else:
                        ops[unit_id] = [_step_toward(pos, target)]
                        assigned = True

        if assigned:
            continue

        # 6. Fertilize (only the crops where it clearly pays for itself).
        fert_targets = [(x, y) for (x, y, _c) in tasks["needs_fertilize"]]
        target = claim_nearest(fert_targets, pos)
        if target is not None and money >= FERTILIZER_COST:
            ops[unit_id] = ["FERTILIZE"] if pos == (target[0], target[1]) else [_step_toward(pos, (target[0], target[1]))]
            assigned = True

        if assigned:
            continue

        # 7. Nothing to do - idle near the shed so we're central for next turn.
        ops[unit_id] = ["PASS"]

    return ops


def _market_orders(me, opp, private, market, unlocked, tasks, step, hands_count, hires_today):
    day = step // 24
    orders = []
    shed = private["shed"]
    prices = market["prices"]
    money = me["money"]

    # Count owned animals first
    owned_animals = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
    for row in me["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                if animal in owned_animals:
                    owned_animals[animal] += 1
    for animal in owned_animals:
        owned_animals[animal] += shed.get(animal, 0)
    # Count animals currently carried in unit inventories
    for inv in private.get("inventories", []):
        if inv:
            for animal in owned_animals:
                owned_animals[animal] += inv.get(animal, 0)
    total_fed_animals = owned_animals["COW"] + owned_animals["SHEEP"] + owned_animals["GOOSE"]

    shed_load = sum(shed.values())
    near_full = shed_load >= (100 - SHED_SAFETY_MARGIN)

    # --- 1. Sell what's already in the shed. ---
    for item, count in shed.items():
        if count <= 0 or item in ("GOOSE", "COW", "SHEEP"):
            continue  # don't accidentally sell live animals
        if item == "WHEAT" and total_fed_animals > 0:
            reserve = total_fed_animals * 2 + 5
            if count <= reserve:
                continue
            else:
                orders.append(["SELL", "WHEAT", count - reserve])
                continue
        if item == "FERTILIZER" and tasks["needs_fertilize"] and not near_full:
            continue  # don't sell fertilizer if we plan to use it to fertilize crops
        base = None
        if item in CROP_INFO:
            base = None  # crops aren't sold as seeds; produce items handled below
        product_bases = {c["product"]: c["base_price"] for c in ANIMAL_INFO.values()}
        product_bases["FERTILIZER"] = 100
        base = CROP_INFO.get(item, {}).get("base_price") or product_bases.get(item)

        if item in CORE_SELL_ALWAYS or base is None:
            orders.append(["SELL", item, count])
        else:
            floor = SELL_FLOOR_FRACTION.get(item, 0.5)
            if step >= 360:
                decay_factor = max(0.1, 1.0 - (step - 360) / (700 - 360))
                floor *= decay_factor

            # If we hold a lot of an item, we should be more willing to sell even at lower prices
            holding_excess = count > 5
            adjusted_floor = floor * 0.5 if holding_excess else floor
            price_ok = prices.get(item, base) >= adjusted_floor * base
            if price_ok or near_full or prices.get(item, base) >= 20: # never hold if we can get at least $20/unit
                orders.append(["SELL", item, count])

    # --- 2. Opponent-aware nudge: if the opponent is sitting on a lot of
    #     ripe tiles of something, sell ours of that item now even if it's
    #     a bit under our normal floor, since price is about to move anyway.
    opp_ripe_crops = {}
    for row in opp.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0:
                opp_ripe_crops[tile["crop"]] = opp_ripe_crops.get(tile["crop"], 0) + 1
    for crop, n in opp_ripe_crops.items():
        if crop in ("WHEAT", "FERTILIZER"):
            continue
        product = crop
        held = shed.get(product, 0)
        if n >= 3 and held > 0 and ["SELL", product, held] not in orders:
            orders.append(["SELL", product, held])

    # --- 3. Buy seeds we're about to need (only if we don't already hold one
    #     and we have empty tiles waiting). ---
    if tasks["empty_tiles"]:
        crop = _pick_crop_to_plant(tasks["crop_counts"], private["seeds"], money)
        if crop is not None and private["seeds"].get(crop, 0) == 0:
            cost = CROP_INFO[crop]["seed_cost"]
            if money - cost >= CASH_RESERVE:
                orders.append(["BUY_SEED", crop, 1])
                money -= cost

    # --- 4. Fertilizer restock for planned fertilizing. ---
    if tasks["needs_fertilize"] and shed.get("FERTILIZER", 0) == 0:
        if money - FERTILIZER_COST >= CASH_RESERVE:
            orders.append(["BUY_PRODUCT", "FERTILIZER", 1])
            money -= FERTILIZER_COST

    # --- 5. Dynamic Animal scaling and structure building purchase ---

    empty_coops = 0
    empty_pastures = 0
    for row in me["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                if tile.get("kind") == "COOP" and tile.get("animal") is None:
                    empty_coops += 1
                elif tile.get("kind") == "PASTURE" and tile.get("animal") is None:
                    empty_pastures += 1

    unlocked_quads = me["unlocked_quadrants"]
    if len(unlocked_quads) >= 4:
        pasture_limit = 7
    elif len(unlocked_quads) >= 3:
        pasture_limit = 6
    elif len(unlocked_quads) >= 2:
        pasture_limit = 3
    else:
        pasture_limit = 1

    if step < 500:
        if empty_pastures > 0:
            if owned_animals["COW"] < pasture_limit and money - 400 >= 500:
                orders.append(["BUY_ANIMAL", "COW", 1])
                money -= 400
                owned_animals["COW"] += 1
                empty_pastures -= 1
            elif owned_animals["SHEEP"] < min(5, pasture_limit) and money - 500 >= 500:
                orders.append(["BUY_ANIMAL", "SHEEP", 1])
                money -= 500
                owned_animals["SHEEP"] += 1
                empty_pastures -= 1

        if empty_coops > 0 and owned_animals["GOOSE"] < 1 and money - 300 >= 300:
            orders.append(["BUY_ANIMAL", "GOOSE", 1])
            money -= 300
            owned_animals["GOOSE"] += 1
            empty_coops -= 1

    # --- 5.5. Wheat buy/restock logic to prevent animal starvation ---
    wheat_in_shed = shed.get("WHEAT", 0)
    wheat_price = prices.get("WHEAT", 30)
    if total_fed_animals > 0 and wheat_in_shed < (total_fed_animals * 2 + 5):
        needed_wheat = (total_fed_animals * 2 + 5) - wheat_in_shed
        cost = needed_wheat * wheat_price
        if money - cost >= CASH_RESERVE:
            orders.append(["BUY_PRODUCT", "WHEAT", needed_wheat])
            money -= cost

    # --- 6. Hire hands while it's still cheap and there's a task backlog. ---
    actual_planting_backlog = min(len(tasks["empty_tiles"]), sum(private["seeds"].values()))
    pending = (
        len(tasks["needs_water"]) + len(tasks["harvest_ready"]) + len(tasks["weeds"])
        + len(tasks["animal_needs_feed"]) + actual_planting_backlog
    )
    fib = _fib_hire_cost(hires_today)
    if hands_count + hires_today < MAX_HANDS and pending > (1 + hands_count) and money - CASH_RESERVE >= fib:
        orders.append(["HIRE"])
        money -= fib
        hires_today += 1

    # --- 7. Land expansion once we have a healthy buffer over the purchase cost ---
    for quad in LAND_ORDER:
        if quad in unlocked:
            continue
        cost = LAND_COST[quad]
        if money - cost >= 1000:
            orders.append(["BUY_LAND"])
            money -= cost
        break  # only ever consider the next quadrant in order

    return orders[:MAX_MARKET_ORDERS]


def _fib_hire_cost(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def agent(obs):
    player = obs["player"]
    day = obs["day"]
    me = obs["farms"][player]
    opp = obs["farms"][1 - player]
    private = obs["private"]
    market = obs["market"]
    unlocked = set(me["unlocked_quadrants"])
    board = len(me["tiles"])
    half = board // 2

    if day != _STATE["day"]:
        _reset_for_new_day()
        _STATE["day"] = day

    # Build the unit list: farmer + hands, with stable ids for this day.
    units = [("farmer", tuple(me["farmer"]))]
    for i, hpos in enumerate(me.get("hands", [])):
        units.append((f"hand{i}", tuple(hpos)))

    # Calibrate movement direction mapping from last turn's outcome.
    for unit_id, pos in units:
        _calibrate_direction(unit_id, pos)

    tasks = _scan_farm(me, day, unlocked, half)

    opp_pressure = {}  # reserved hook for deeper opponent modeling later
    unit_ops = _assign_units(units, tasks, private, me, opp_pressure, half, obs["step"])

    hires_today = me.get("hires_today", 0)
    market_orders = _market_orders(
        me, opp, private, market, unlocked, tasks, obs["step"], len(me.get("hands", [])), hires_today
    )

    # Record intended moves for next turn's self-calibration.
    farmer_op = unit_ops.get("farmer", ["PASS"])
    hand_ops = [unit_ops.get(f"hand{i}", ["PASS"]) for i in range(len(me.get("hands", [])))]

    for unit_id, pos in units:
        op = unit_ops.get(unit_id, ["PASS"])
        _STATE["last_pos"][unit_id] = pos
        _STATE["last_dir"][unit_id] = op[0] if op and op[0] in DIRS else None

    return {
        "farmer": farmer_op,
        "hands": hand_ops,
        "market": market_orders,
    }
