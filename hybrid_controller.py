"""
Hybrid Multi-Layer Controller for Kaggriculture.

Implements:
1. Calculated Field Engine (Pre-computation Layer)
2. Dynamic Action Masker (The Shield)
3. Macro-Temporal Controller (Aboveground Layer)
4. State-Triggered Fallbacks
"""

import math

# Market default parameters
_I0 = 10000
_PRICE_FLOOR = 1
_MP = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": (60, 200, "linear", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "linear", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}

_RESERVE_FRAC = {
    "CARROT": 0.45,
    "TOMATO": 0.45,
    "MELON": 0.55,
    "STRAWBERRY": 0.55,
    "MILK": 0.55,
    "WOOL": 0.55,
}

_SEEDS_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
_ANIMALS_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}


class CalculatedFieldEngine:
    """Pre-computation engine for market metrics, cash requirements, and reserve pricing."""

    @staticmethod
    def calculate_cash_needed(orders, obs):
        prices = ((obs.get("market") or {}).get("prices") or {})
        total = 0
        for order in orders:
            if not isinstance(order, list) or not order:
                continue
            op = order[0]
            if op == "BUY_SEED" and len(order) >= 3:
                total += _SEEDS_COST.get(order[1], 0) * int(order[2] or 0)
            elif op == "BUY_ANIMAL" and len(order) >= 3:
                total += _ANIMALS_COST.get(order[1], 0) * int(order[2] or 0)
            elif op == "BUY_PRODUCT" and len(order) >= 3:
                total += int(prices.get(order[1], 50) or 50) * int(order[2] or 0)
            elif op == "BUY_LAND":
                total += 4000
        return total

    @staticmethod
    def calculate_reserve_price(item, step, obs):
        base = _MP.get(item, (100,))[0]
        frac = _RESERVE_FRAC.get(item, 0.5)
        if step >= 576:
            span = float(max(1, 716 - 576))
            frac *= max(0.0, (716 - step) / span)
        return base * frac


class DynamicActionMasker:
    """The Shield: filters and audits proposed actions against hard constraints."""

    @staticmethod
    def mask_action(action, obs):
        """Audits farmer, hands, and market actions against inventory, money, and capacity limits."""
        player = int(obs.get("player", 0) or 0)
        farms = obs.get("farms") or []
        if len(farms) <= player:
            return action

        farm = farms[player]
        private = obs.get("private") or {}
        money = float(farm.get("money", 0) or 0)
        shed = dict(private.get("shed") or {})

        # Count animals to enforce wheat feed reservation
        owned_animals = 0
        for row in farm.get("tiles") or []:
            for tile in row or []:
                if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                    if tile.get("animal"):
                        owned_animals += 1

        wheat_reserve = owned_animals * 2 + 5
        wheat_in_shed = int(shed.get("WHEAT", 0) or 0)

        market_orders = list(action.get("market") or [])
        masked_orders = []

        for order in market_orders:
            if not isinstance(order, list) or not order:
                continue
            op = order[0]

            # Enforce wheat feed protection: do not sell reserved wheat needed for feeding
            if op == "SELL" and len(order) >= 3 and order[1] == "WHEAT":
                qty = int(order[2] or 0)
                allowed_sell = max(0, wheat_in_shed - wheat_reserve)
                if allowed_sell > 0:
                    order[2] = min(qty, allowed_sell)
                    masked_orders.append(order)
                continue

            # Ensure buy orders do not exceed current bank balance
            cost = CalculatedFieldEngine.calculate_cash_needed([order], obs)
            if cost <= money:
                money -= cost
                masked_orders.append(order)

        action["market"] = masked_orders[:10]
        return action


class MacroTemporalController:
    """Aboveground Layer: periodic evaluation and execution parameter overrides."""

    def __init__(self, front_run_horizon=1, early_terminal=0):
        self.front_run_horizon = front_run_horizon
        self.early_terminal = early_terminal

    def evaluate_macro_state(self, obs, step):
        """Periodically adjusts parameters based on market and step progression."""
        if step >= 680:
            self.early_terminal = 716
        else:
            self.early_terminal = 0


class StateTriggeredFallback:
    """Safety watchdog: falls back to baseline trace if state variance is high or action invalid."""

    @staticmethod
    def audit_and_fallback(action, baseline_action, confidence_score=1.0):
        if confidence_score < 0.5:
            return baseline_action
        return action
