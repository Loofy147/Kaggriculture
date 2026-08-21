
from kaggriculture_sovereign import TruthLayer, WorldStateEstimator, EconomicPlanner, market_price


def sample_obs():
    empty = [[None for _ in range(10)] for _ in range(10)]
    empty[0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "planted_day": 0,
        "watered_today": True,
        "consecutive_unwatered": 0,
        "yield_units": 2,
    }
    opp = [[None for _ in range(10)] for _ in range(10)]
    opp[1][1] = {
        "kind": "PLANT",
        "crop": "CARROT",
        "planted_day": 1,
        "watered_today": False,
        "consecutive_unwatered": 1,
        "yield_units": 1,
    }
    return {
        "step": 48,
        "day": 2,
        "hour": 0,
        "player": 0,
        "farms": [
            {"money": 2500, "farmer": [0, 0], "hands": [],
             "tiles": empty},
            {"money": 2500, "farmer": [1, 1], "hands": [],
             "tiles": opp},
        ],
        "private": {
            "shed": {"CARROT": 5, "MELON": 1},
            "seeds": {"CARROT": 3, "MELON": 2},
        },
        "market": {
            "prices": {"CARROT": 35, "MELON": 250},
            "inventory": {"CARROT": 10000, "MELON": 10000},
        },
        "town": {"unlocked_shops": ["PET_CAFE"]},
    }


def test_truth_parsing():
    t = TruthLayer()
    s = t.update(sample_obs())
    assert s.cash == 2500
    assert t.shed_load() == 6
    assert t.shed_capacity_remaining() == 94
    assert len(s.own_plants) == 1
    assert len(s.opponent_plants) == 1
    assert s.opponent_plants[0].crop == "CARROT"


def test_market_price_base():
    assert market_price("MELON", 10000) == 250


def test_forecast_and_planner():
    t = TruthLayer()
    t.update(sample_obs())
    est = WorldStateEstimator(t)
    f = est.forecast_market("MELON", horizon_steps=24, expected_net_market_flow=300, uncertainty=100)
    assert f.inventory_low <= f.inventory_mid <= f.inventory_high
    planner = EconomicPlanner(t, est)
    candidates = planner.best_sale_candidates()
    assert candidates
    assert candidates[0].quantity > 0
