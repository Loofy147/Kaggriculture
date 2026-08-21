
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
