
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple
import math


PRODUCTS = [
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER"
]

CROPS = {
    "WHEAT":      {"seed": 10,  "first_yield_day": 2,  "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20,  "first_yield_day": 2,  "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50,  "first_yield_day": 8,  "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80,  "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE":  {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":    {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP":  {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

MARKET_I0 = 10_000
PRICE_FLOOR = 1

# Exact engine market specification copied from the inspected engine source.
MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base": 35,  "I0": MARKET_I0, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base": 60,  "I0": MARKET_I0, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base": 50,  "I0": MARKET_I0, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

HINGE_GAIN = 8.0


def _shape(func: str, x: float, T: Optional[float] = None) -> float:
    x = max(0.0, float(x))
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "log10":
        return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0:
            return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    raise ValueError(f"unknown market shape: {func}")


def market_price(item: str, inventory: float,
                 params: Mapping[str, Mapping[str, Any]] = MARKET_PARAMS) -> int:
    """Exact deterministic price function from the engine model."""
    p = params[item]
    base = float(p["base"])
    i0 = float(p["I0"])
    T = float(p["T"])
    if inventory < i0:
        f = p["below_func"]
        amp = float(p["below_target"]) * base / _shape(f, T, T)
        price = base + amp * _shape(f, i0 - inventory, T)
    else:
        f = p["above_func"]
        amp = float(p["above_target"]) * base / _shape(f, T, T)
        price = base - amp * _shape(f, inventory - i0, T)
    return max(PRICE_FLOOR, int(round(price)))


@dataclass(frozen=True)
class PlantTruth:
    x: int
    y: int
    crop: str
    planted_day: int
    yield_units: int
    watered_today: bool
    consecutive_unwatered: int

    @property
    def age_days(self) -> int:
        # Caller may override this with a supplied current day when needed.
        return 0


@dataclass
class TruthState:
    step: int = 0
    day: int = 0
    hour: int = 0
    player: int = 0

    cash: float = 0.0
    shed: Dict[str, int] = field(default_factory=dict)
    seeds: Dict[str, int] = field(default_factory=dict)
    farmer: Tuple[int, int] = (0, 0)
    hands: List[Tuple[int, int]] = field(default_factory=list)

    market_prices: Dict[str, int] = field(default_factory=dict)
    market_inventory: Dict[str, int] = field(default_factory=dict)
    unlocked_shops: List[str] = field(default_factory=list)

    farm_tiles: List[List[Any]] = field(default_factory=list)
    opponent_tiles: List[List[Any]] = field(default_factory=list)
    own_plants: List[PlantTruth] = field(default_factory=list)
    opponent_plants: List[PlantTruth] = field(default_factory=list)


class TruthLayer:
    """
    Engine-facing state decoder.

    Scope:
      * parse observations;
      * compute deterministic facts derivable from the observation;
      * never assign probabilities or opponent intentions.
    """

    BOARD_SIZE = 10
    SHED_CAPACITY = 100
    TURNS_PER_DAY = 24
    MAX_TURNS = 720
    MAX_MARKET_ORDERS = 10

    def __init__(self) -> None:
        self.state = TruthState()

    @staticmethod
    def _shed_load(shed: Mapping[str, int]) -> int:
        return sum(max(0, int(v)) for v in shed.values())

    @staticmethod
    def _parse_coord(value: Any) -> Tuple[int, int]:
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return int(value[0]), int(value[1])
        return (0, 0)

    def _parse_tiles(self, tiles: List[List[Any]], current_day: int) -> Tuple[List[List[Any]], List[PlantTruth]]:
        plants: List[PlantTruth] = []
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row):
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    plants.append(
                        PlantTruth(
                            x=x,
                            y=y,
                            crop=str(tile.get("crop")),
                            planted_day=int(tile.get("planted_day", current_day)),
                            yield_units=int(tile.get("yield_units", 0)),
                            watered_today=bool(tile.get("watered_today", False)),
                            consecutive_unwatered=int(tile.get("consecutive_unwatered", 0)),
                        )
                    )
        return [list(r) for r in tiles], plants

    def update(self, obs: Mapping[str, Any]) -> TruthState:
        player = int(obs["player"])
        farms = obs["farms"]
        own = farms[player]
        opp_id = 1 - player
        opp = farms[opp_id]

        step = int(obs.get("step", 0))
        day = int(obs.get("day", step // self.TURNS_PER_DAY))
        hour = int(obs.get("hour", step % self.TURNS_PER_DAY))

        own_tiles, own_plants = self._parse_tiles(own["tiles"], day)
        opp_tiles, opp_plants = self._parse_tiles(opp["tiles"], day)

        private = obs.get("private", {}) or {}
        market = obs.get("market", {}) or {}
        town = obs.get("town", {}) or {}

        self.state = TruthState(
            step=step,
            day=day,
            hour=hour,
            player=player,
            cash=float(own.get("money", 0.0)),
            shed={str(k): int(v) for k, v in (private.get("shed", {}) or {}).items()},
            seeds={str(k): int(v) for k, v in (private.get("seeds", {}) or {}).items()},
            farmer=self._parse_coord(own.get("farmer")),
            hands=[self._parse_coord(x) for x in own.get("hands", [])],
            market_prices={str(k): int(v) for k, v in (market.get("prices", {}) or {}).items()},
            market_inventory={str(k): int(v) for k, v in (market.get("inventory", {}) or {}).items()},
            unlocked_shops=[str(x) for x in town.get("unlocked_shops", [])],
            farm_tiles=own_tiles,
            opponent_tiles=opp_tiles,
            own_plants=own_plants,
            opponent_plants=opp_plants,
        )
        self._validate_invariants()
        return self.state

    def _validate_invariants(self) -> None:
        s = self.state
        if not (0 <= s.step <= self.MAX_TURNS):
            raise ValueError(f"invalid step: {s.step}")
        if self._shed_load(s.shed) > self.SHED_CAPACITY:
            raise ValueError("observed shed exceeds engine capacity")
        for pos in [s.farmer, *s.hands]:
            x, y = pos
            if not (0 <= x < self.BOARD_SIZE and 0 <= y < self.BOARD_SIZE):
                raise ValueError(f"invalid position: {pos}")

    def shed_load(self) -> int:
        return self._shed_load(self.state.shed)

    def shed_capacity_remaining(self) -> int:
        return max(0, self.SHED_CAPACITY - self.shed_load())

    def market_delta(self, product: str) -> int:
        return int(self.state.market_inventory.get(product, MARKET_I0) - MARKET_I0)

    def plant_age(self, plant: PlantTruth) -> int:
        return max(0, self.state.day - plant.planted_day)

    def crop_maturity(self, plant: PlantTruth) -> str:
        """Exact status classification, not an economic forecast."""
        crop = CROPS.get(plant.crop)
        if crop is None:
            return "UNKNOWN_CROP"
        age = self.plant_age(plant)
        if age < crop["first_yield_day"]:
            return "IMMATURE"
        if crop["ongoing"]:
            return "PRODUCING"
        if age >= crop["max_yield_day"]:
            return "MATURE"
        return "PRODUCING"


@dataclass(frozen=True)
class ProductionBound:
    product: str
    earliest_day: int
    latest_day: int
    min_units: int
    max_units: int


@dataclass(frozen=True)
class MarketForecast:
    product: str
    horizon_steps: int
    inventory_low: float
    inventory_mid: float
    inventory_high: float
    price_low: float
    price_mid: float
    price_high: float


@dataclass
class OpponentBelief:
    """
    Initially non-parametric: policy weights are explicit assumptions.
    They become empirical probabilities only after replay data updates them.
    """
    reliable_care: float = 0.80
    delayed_harvest: float = 0.10
    neglected: float = 0.10

    def normalized(self) -> "OpponentBelief":
        vals = [max(0.0, self.reliable_care), max(0.0, self.delayed_harvest), max(0.0, self.neglected)]
        total = sum(vals)
        if total <= 0:
            return OpponentBelief(1.0, 0.0, 0.0)
        return OpponentBelief(*(v / total for v in vals))


class WorldStateEstimator:
    """
    Predictive layer.

    It never changes engine truth. It produces bounds/forecasts separately.
    """

    def __init__(self, truth: TruthLayer) -> None:
        self.truth = truth
        self.opponent_beliefs: Dict[str, OpponentBelief] = {}

    def _belief_for(self, crop: str) -> OpponentBelief:
        return self.opponent_beliefs.get(crop, OpponentBelief()).normalized()

    def opponent_production_bounds(self, plant: PlantTruth) -> ProductionBound:
        crop = CROPS[plant.crop]
        current_day = self.truth.state.day
        age = self.truth.plant_age(plant)

        # Best/nominal and failure bounds are expressed as bounds, not certainty.
        earliest = current_day
        latest = current_day

        if age < crop["first_yield_day"]:
            earliest = plant.planted_day + crop["first_yield_day"]
            latest = plant.planted_day + crop["first_yield_day"] + 1
        elif crop["ongoing"]:
            earliest = current_day
            latest = current_day + crop["interval"]
        else:
            earliest = current_day
            latest = max(current_day, plant.planted_day + crop["max_yield_day"])

        min_units = max(0, plant.yield_units)
        max_units = crop["max_yield"]
        return ProductionBound(
            product=plant.crop,
            earliest_day=earliest,
            latest_day=latest,
            min_units=min_units,
            max_units=max_units,
        )

    def forecast_market(
        self,
        product: str,
        horizon_steps: int,
        expected_net_market_flow: float = 0.0,
        uncertainty: float = 0.0,
    ) -> MarketForecast:
        """
        inventory(t+h) = current inventory + expected net flow.
        Positive flow means more inventory (downward price pressure).
        """
        current = float(self.truth.state.market_inventory.get(product, MARKET_I0))
        mid = current + expected_net_market_flow
        spread = abs(float(uncertainty))

        low_inv = max(0.0, mid - spread)
        high_inv = max(0.0, mid + spread)

        prices = MARKET_PARAMS
        low_p = market_price(product, high_inv, prices)
        mid_p = market_price(product, mid, prices)
        high_p = market_price(product, low_inv, prices)

        return MarketForecast(
            product=product,
            horizon_steps=horizon_steps,
            inventory_low=low_inv,
            inventory_mid=mid,
            inventory_high=high_inv,
            price_low=float(low_p),
            price_mid=float(mid_p),
            price_high=float(high_p),
        )


@dataclass(frozen=True)
class EconomicAction:
    name: str
    product: Optional[str]
    quantity: float
    immediate_cash_delta: float
    expected_future_value: float
    opportunity_cost: float
    risk_penalty: float

    @property
    def score(self) -> float:
        return (
            self.immediate_cash_delta
            + self.expected_future_value
            - self.opportunity_cost
            - self.risk_penalty
        )


class EconomicPlanner:
    """
    Deterministic candidate evaluator.

    This first implementation deliberately does not choose farm routes.
    It evaluates economic actions using the Truth + Forecast layers.
    """

    def __init__(self, truth: TruthLayer, estimator: WorldStateEstimator) -> None:
        self.truth = truth
        self.estimator = estimator

    def sale_action(
        self,
        product: str,
        quantity: int,
        expected_price: Optional[float] = None,
        market_impact_cost: float = 0.0,
    ) -> EconomicAction:
        quantity = max(0, int(quantity))
        price = float(
            expected_price
            if expected_price is not None
            else self.truth.state.market_prices.get(product, market_price(
                product,
                self.truth.state.market_inventory.get(product, MARKET_I0),
            ))
        )
        cash = quantity * price
        return EconomicAction(
            name="SELL",
            product=product,
            quantity=quantity,
            immediate_cash_delta=cash,
            expected_future_value=0.0,
            opportunity_cost=0.0,
            risk_penalty=float(market_impact_cost),
        )

    def fertilizer_value(
        self,
        product: str,
        delta_yield: float,
        expected_price: float,
        fertilizer_cost: float,
        ap_opportunity_cost: float,
        market_impact_cost: float,
        discount_rate_per_day: float = 0.0,
        days_advanced: float = 0.0,
    ) -> float:
        """
        Time-adjusted fertilizer value:
          PV(delta cash) - fertilizer cost - AP opportunity cost - market impact.
        """
        gross = delta_yield * expected_price
        if discount_rate_per_day > 0.0:
            gross *= (1.0 + discount_rate_per_day) ** (-max(0.0, days_advanced))
        return gross - fertilizer_cost - ap_opportunity_cost - market_impact_cost

    def best_sale_candidates(self) -> List[EconomicAction]:
        candidates: List[EconomicAction] = []
        for product, qty in self.truth.state.shed.items():
            if qty <= 0 or product not in MARKET_PARAMS:
                continue
            current = float(self.truth.state.market_prices.get(
                product,
                market_price(product, self.truth.state.market_inventory.get(product, MARKET_I0)),
            ))
            candidates.append(self.sale_action(product, qty, expected_price=current))
        return sorted(candidates, key=lambda a: a.score, reverse=True)


class SpatialScheduler:
    """
    Multi-unit task routing and pathfinding engine.

    Responsibilities:
      - Scan farm state for task priorities.
      - Self-calibrate direction mappings (NORTH, SOUTH, EAST, WEST) based on movement observations.
      - Assign units (farmer + hands) using prioritized spatial assignment.
      - Route units towards shed access tiles when EOD or inventory demands.
    """

    DIRS = ("NORTH", "SOUTH", "EAST", "WEST")

    def __init__(self) -> None:
        self.dir_delta: Dict[str, Tuple[int, int]] = {
            "NORTH": (0, -1),
            "SOUTH": (0, 1),
            "EAST": (1, 0),
            "WEST": (-1, 0),
        }
        self.dir_calibrated: Dict[str, bool] = {d: False for d in self.DIRS}
        self.last_pos: Dict[str, Tuple[int, int]] = {}
        self.last_dir: Dict[str, Optional[str]] = {}

    def calibrate_direction(self, unit_id: str, cur_pos: Tuple[int, int]) -> None:
        prev_dir = self.last_dir.get(unit_id)
        prev_pos = self.last_pos.get(unit_id)
        if prev_dir is None or prev_pos is None:
            return
        dx = cur_pos[0] - prev_pos[0]
        dy = cur_pos[1] - prev_pos[1]
        if abs(dx) + abs(dy) != 1:
            return
        observed = (dx, dy)
        if observed != self.dir_delta.get(prev_dir):
            self.dir_delta[prev_dir] = observed
            self.dir_calibrated[prev_dir] = True

    def step_toward(self, cur: Tuple[int, int], target: Tuple[int, int]) -> Optional[str]:
        cx, cy = cur
        tx, ty = target
        dx, dy = tx - cx, ty - cy
        if dx == 0 and dy == 0:
            return None
        candidates = []
        if dx != 0:
            candidates.append(("EAST" if dx > 0 else "WEST", abs(dx)))
        if dy != 0:
            candidates.append(("SOUTH" if dy > 0 else "NORTH", abs(dy)))
        candidates.sort(key=lambda t: -t[1])
        wanted_name = candidates[0][0]
        wanted_delta = {"EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, 1), "NORTH": (0, -1)}[wanted_name]
        for name, delta in self.dir_delta.items():
            if delta == wanted_delta:
                return name
        return wanted_name

    @staticmethod
    def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _quadrant_of(x: int, y: int, half: int) -> str:
        if x < half and y < half:
            return "NW"
        if x >= half and y < half:
            return "NE"
        if x < half and y >= half:
            return "SW"
        return "SE"

    @staticmethod
    def shed_tiles(board_size: int = 10) -> List[Tuple[int, int]]:
        half = board_size // 2
        return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]

    def scan_farm(
        self,
        tiles: List[List[Any]],
        day: int,
        unlocked_quadrants: List[str],
        board_size: int = 10,
    ) -> Dict[str, Any]:
        half = board_size // 2
        shed_set = set(self.shed_tiles(board_size))
        unlocked_set = set(unlocked_quadrants)

        needs_water: List[Tuple[int, int]] = []
        harvest_ready: List[Tuple[int, int, str]] = []
        weeds: List[Tuple[int, int]] = []
        empty_tiles: List[Tuple[int, int]] = []
        needs_fertilize: List[Tuple[int, int, str]] = []
        empty_structures: List[Tuple[int, int, str]] = []
        animal_needs_feed: List[Tuple[int, int]] = []
        animal_needs_care: List[Tuple[int, int]] = []
        animal_fert_ready: List[Tuple[int, int]] = []
        animal_ready_harvest: List[Tuple[int, int]] = []
        crop_counts = {c: 0 for c in CROPS}

        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                if self._quadrant_of(x, y, half) not in unlocked_set:
                    continue
                tile = tiles[y][x]
                if tile is None:
                    if (x, y) not in shed_set:
                        empty_tiles.append((x, y))
                    continue
                if tile == "LOCKED":
                    continue
                kind = tile.get("kind") if isinstance(tile, dict) else None
                if kind == "WEED":
                    weeds.append((x, y))
                elif kind == "PLANT":
                    crop = str(tile.get("crop"))
                    if crop in crop_counts:
                        crop_counts[crop] += 1
                    planted_day = int(tile.get("planted_day", day))
                    age = day - planted_day
                    crop_info = CROPS.get(crop, {})
                    first_yield = crop_info.get("first_yield_day", 2)
                    max_yield_day = crop_info.get("max_yield_day", 4)

                    if not tile.get("watered_today", False):
                        needs_water.append((x, y))
                    if age >= first_yield and (tile.get("yield_units", 0) > 0 or age >= max_yield_day):
                        harvest_ready.append((x, y, crop))
                    elif (
                        crop in ("MELON", "TOMATO", "STRAWBERRY", "CARROT")
                        and tile.get("fertilized_until_day", -1) < day
                        and age < max_yield_day
                    ):
                        needs_fertilize.append((x, y, crop))
                elif kind in ("COOP", "PASTURE"):
                    if tile.get("animal") is None:
                        empty_structures.append((x, y, str(kind)))
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

    def schedule(
        self,
        truth_state: TruthState,
        tasks: Dict[str, Any],
        inventories: Optional[List[Dict[str, int]]] = None,
    ) -> Dict[str, List[Any]]:
        """
        Assigns actions for 'farmer' and each 'handX'.
        """
        units: List[Tuple[str, Tuple[int, int]]] = [("farmer", truth_state.farmer)]
        for i, hpos in enumerate(truth_state.hands):
            units.append((f"hand{i}", hpos))

        for uid, pos in units:
            self.calibrate_direction(uid, pos)

        ops: Dict[str, List[Any]] = {}
        claimed: set = set()

        seeds_left = dict(truth_state.seeds)
        shed = dict(truth_state.shed)
        money = truth_state.cash
        invs = inventories or [{}] * len(units)

        def claim_nearest(pos_list: List[Tuple[int, int]], unit_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
            avail = [p for p in pos_list if p not in claimed]
            if not avail:
                return None
            best = min(avail, key=lambda p: (self._manhattan(unit_pos, p), p[1], p[0]))
            claimed.add(best)
            return best

        s_tiles = self.shed_tiles(TruthLayer.BOARD_SIZE)

        for unit_idx, (unit_id, pos) in enumerate(units):
            assigned = False
            u_inv = invs[unit_idx] if unit_idx < len(invs) else {}

            # 1. Animal Feed
            feed_target = claim_nearest(tasks["animal_needs_feed"], pos)
            if feed_target is not None:
                if u_inv.get("WHEAT", 0) > 0:
                    if pos == feed_target:
                        ops[unit_id] = ["FEED"]
                        u_inv["WHEAT"] -= 1
                    else:
                        dir_cmd = self.step_toward(pos, feed_target)
                        ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                    assigned = True
                else:
                    claimed.remove(feed_target)
                    if shed.get("WHEAT", 0) > 0:
                        if pos in s_tiles:
                            qty = min(5, shed["WHEAT"])
                            ops[unit_id] = ["PICKUP", "WHEAT", qty]
                            shed["WHEAT"] -= qty
                            assigned = True
                        else:
                            target_s = min(s_tiles, key=lambda s: self._manhattan(pos, s))
                            dir_cmd = self.step_toward(pos, target_s)
                            ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                            assigned = True

            if assigned:
                continue

            # 2. Water plants
            water_target = claim_nearest(tasks["needs_water"], pos)
            if water_target is not None:
                if pos == water_target:
                    ops[unit_id] = ["WATER"]
                else:
                    dir_cmd = self.step_toward(pos, water_target)
                    ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                assigned = True

            if assigned:
                continue

            # 3. Harvest crops / animal products
            crop_targets = [(x, y) for (x, y, _c) in tasks["harvest_ready"]]
            h_target = claim_nearest(crop_targets, pos)
            if h_target is None:
                h_target = claim_nearest(tasks["animal_ready_harvest"], pos)
            if h_target is not None:
                if pos == h_target:
                    ops[unit_id] = ["HARVEST"]
                else:
                    dir_cmd = self.step_toward(pos, h_target)
                    ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                assigned = True

            if assigned:
                continue

            # 4. Weeds
            weed_target = claim_nearest(tasks["weeds"], pos)
            if weed_target is not None:
                if pos == weed_target:
                    ops[unit_id] = ["DIG"]
                else:
                    dir_cmd = self.step_toward(pos, weed_target)
                    ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                assigned = True

            if assigned:
                continue

            # 5. Plant crops if seed available
            if tasks["empty_tiles"]:
                avail_crops = [c for c, count in seeds_left.items() if count > 0]
                if avail_crops:
                    crop_to_plant = avail_crops[0]
                    p_target = claim_nearest(tasks["empty_tiles"], pos)
                    if p_target is not None:
                        if pos == p_target:
                            ops[unit_id] = ["PLANT", crop_to_plant]
                            seeds_left[crop_to_plant] -= 1
                        else:
                            dir_cmd = self.step_toward(pos, p_target)
                            ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                        assigned = True

            if assigned:
                continue

            # 6. EOD Return to shed or PASS
            if truth_state.hour >= 20:
                if pos not in s_tiles:
                    target_s = min(s_tiles, key=lambda s: self._manhattan(pos, s))
                    dir_cmd = self.step_toward(pos, target_s)
                    ops[unit_id] = [dir_cmd] if dir_cmd else ["PASS"]
                    assigned = True

            if not assigned:
                ops[unit_id] = ["PASS"]

            # Record last positions and directions for calibration
            op = ops[unit_id]
            self.last_pos[unit_id] = pos
            self.last_dir[unit_id] = op[0] if op and op[0] in self.DIRS else None

        return ops


class OpponentPolicyModel:
    """
    Tracks opponent observed state across turns and updates opponent beliefs.
    """
    def __init__(self) -> None:
        self.prev_opponent_plants: Dict[Tuple[int, int], PlantTruth] = {}
        self.watered_count: int = 0
        self.total_observed: int = 0

    def update(self, current_opponent_plants: List[PlantTruth]) -> OpponentBelief:
        current_dict = {(p.x, p.y): p for p in current_opponent_plants}
        for pos, plant in current_dict.items():
            if pos in self.prev_opponent_plants:
                self.total_observed += 1
                if plant.watered_today:
                    self.watered_count += 1
        self.prev_opponent_plants = current_dict

        if self.total_observed == 0:
            return OpponentBelief()

        water_ratio = self.watered_count / self.total_observed
        reliable = max(0.1, min(0.95, water_ratio))
        neglected = max(0.05, 1.0 - reliable)
        return OpponentBelief(reliable_care=reliable, delayed_harvest=0.05, neglected=neglected).normalized()


class ActionArbiter:
    """
    Final decision arbiter and action matrix builder.
    Combines unit operations and market orders while enforcing engine invariants.
    """
    MAX_MARKET_ORDERS = 10

    @staticmethod
    def total_owned_animals(farm_tiles: List[List[Any]], shed: Dict[str, int]) -> int:
        count = 0
        for row in farm_tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                    if tile.get("animal") is not None:
                        count += 1
        for anim in ("GOOSE", "COW", "SHEEP"):
            count += shed.get(anim, 0)
        return count

    def arbitrate(
        self,
        truth_state: TruthState,
        unit_ops: Dict[str, List[Any]],
        raw_market_orders: List[List[Any]],
    ) -> Dict[str, Any]:
        farmer_op = unit_ops.get("farmer", ["PASS"])
        hand_ops = [unit_ops.get(f"hand{i}", ["PASS"]) for i in range(len(truth_state.hands))]

        owned_animals = self.total_owned_animals(truth_state.farm_tiles, truth_state.shed)
        min_wheat_reserve = owned_animals * 2 + 5

        valid_market_orders = []
        for order in raw_market_orders:
            if not isinstance(order, (list, tuple)) or not order:
                continue
            op_type = order[0]
            if op_type == "SELL" and len(order) >= 3 and order[1] == "WHEAT":
                qty = int(order[2])
                current_wheat = truth_state.shed.get("WHEAT", 0)
                available = max(0, current_wheat - min_wheat_reserve)
                if available <= 0:
                    continue
                qty = min(qty, available)
                valid_market_orders.append(["SELL", "WHEAT", qty])
            else:
                valid_market_orders.append(list(order))

        sliced_orders = valid_market_orders[:self.MAX_MARKET_ORDERS]

        return {
            "farmer": farmer_op,
            "hands": hand_ops,
            "market": sliced_orders,
        }


class KaggricultureSovereignNode:
    """
    Main global singleton node orchestrating Perception, Macro-Economics, Spatial Routing, and Safety Arbitration.
    """

    def __init__(self) -> None:
        self.truth = TruthLayer()
        self.estimator = WorldStateEstimator(self.truth)
        self.planner = EconomicPlanner(self.truth, self.estimator)
        self.scheduler = SpatialScheduler()
        self.opp_model = OpponentPolicyModel()
        self.arbiter = ActionArbiter()

    def _generate_market_orders(self, truth_state: TruthState, tasks: Dict[str, Any]) -> List[List[Any]]:
        orders = []
        shed = truth_state.shed
        prices = truth_state.market_prices
        money = truth_state.cash

        # 1. Sale candidates from EconomicPlanner
        sale_candidates = self.planner.best_sale_candidates()
        for cand in sale_candidates:
            if cand.product and cand.quantity > 0:
                orders.append(["SELL", cand.product, int(cand.quantity)])

        # 2. Buy seeds if empty tiles exist and no seeds available
        if tasks.get("empty_tiles"):
            has_seeds = sum(truth_state.seeds.values()) > 0
            if not has_seeds and money >= 10:
                orders.append(["BUY_SEED", "WHEAT", 1])
                money -= 10

        # 3. Restock wheat for animals if needed
        owned_animals = self.arbiter.total_owned_animals(truth_state.farm_tiles, shed)
        if owned_animals > 0:
            req_wheat = owned_animals * 2 + 5
            curr_wheat = shed.get("WHEAT", 0)
            if curr_wheat < req_wheat:
                needed = req_wheat - curr_wheat
                w_price = prices.get("WHEAT", 25)
                if money >= needed * w_price + 150:
                    orders.append(["BUY_PRODUCT", "WHEAT", needed])
                    money -= needed * w_price

        return orders

    def act(self, obs: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            truth_state = self.truth.update(obs)
            self.opp_model.update(truth_state.opponent_plants)

            unlocked = ["NW"]  # NW default, or read from obs
            farms = obs.get("farms", [])
            p_idx = int(obs.get("player", 0))
            if p_idx < len(farms):
                unlocked = farms[p_idx].get("unlocked_quadrants", ["NW"])

            tasks = self.scheduler.scan_farm(
                truth_state.farm_tiles,
                truth_state.day,
                unlocked,
                TruthLayer.BOARD_SIZE,
            )

            inventories = (obs.get("private", {}) or {}).get("inventories", [])
            unit_ops = self.scheduler.schedule(truth_state, tasks, inventories)
            raw_market = self._generate_market_orders(truth_state, tasks)

            return self.arbiter.arbitrate(truth_state, unit_ops, raw_market)
        except Exception:
            # Graceful degradation safe fallback
            hands = []
            farms = obs.get("farms", [])
            p_idx = int(obs.get("player", 0))
            if p_idx < len(farms):
                hands = [["PASS"]] * len(farms[p_idx].get("hands", []))
            return {
                "farmer": ["PASS"],
                "hands": hands,
                "market": [],
            }


_SOVEREIGN_NODE = KaggricultureSovereignNode()


def agent(obs: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Kaggle competition agent entry point.
    """
    return _SOVEREIGN_NODE.act(obs)
