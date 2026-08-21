from kaggriculture_sovereign import (
    TruthLayer,
    WorldStateEstimator,
    EconomicPlanner,
    SpatialScheduler,
    OpponentPolicyModel,
    ActionArbiter,
    KaggricultureSovereignNode,
    agent,
    market_price,
)


def sample_obs():
    empty = [[None for _ in range(10)] for _ in range(10)]
    empty[0][0] = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "planted_day": 0,
        "watered_today": False,
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
            {"money": 2500, "farmer": [0, 0], "hands": [[1, 0]], "unlocked_quadrants": ["NW"], "tiles": empty},
            {"money": 2500, "farmer": [1, 1], "hands": [], "unlocked_quadrants": ["NW"], "tiles": opp},
        ],
        "private": {
            "shed": {"CARROT": 5, "MELON": 1, "WHEAT": 10},
            "seeds": {"CARROT": 3, "MELON": 2},
            "inventories": [{}, {}],
        },
        "market": {
            "prices": {"CARROT": 35, "MELON": 250, "WHEAT": 25},
            "inventory": {"CARROT": 10000, "MELON": 10000, "WHEAT": 10000},
        },
        "town": {"unlocked_shops": ["PET_CAFE"]},
    }


def test_truth_parsing():
    t = TruthLayer()
    s = t.update(sample_obs())
    assert s.cash == 2500
    assert t.shed_load() == 16
    assert t.shed_capacity_remaining() == 84
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


def test_spatial_scheduler():
    t = TruthLayer()
    s = t.update(sample_obs())
    sched = SpatialScheduler()
    tasks = sched.scan_farm(s.farm_tiles, s.day, ["NW"], 10)
    assert len(tasks["needs_water"]) == 1
    assert len(tasks["harvest_ready"]) == 1
    ops = sched.schedule(s, tasks)
    assert "farmer" in ops
    assert ops["farmer"] == ["WATER"]


def test_opponent_policy_model():
    t = TruthLayer()
    s = t.update(sample_obs())
    opp_model = OpponentPolicyModel()
    belief = opp_model.update(s.opponent_plants)
    assert abs((belief.reliable_care + belief.delayed_harvest + belief.neglected) - 1.0) < 1e-6


def test_action_arbiter():
    t = TruthLayer()
    s = t.update(sample_obs())
    arbiter = ActionArbiter()
    raw_orders = [["SELL", "WHEAT", 100]] + [["BUY_SEED", "CARROT", 1]] * 15
    res = arbiter.arbitrate(s, {"farmer": ["PASS"]}, raw_orders)
    assert len(res["market"]) == 10
    # Wheat reserve = 0*2 + 5 = 5 -> max available sell = 10 - 5 = 5
    assert res["market"][0] == ["SELL", "WHEAT", 5]


def test_sovereign_node():
    obs = sample_obs()
    res = agent(obs)
    assert "farmer" in res
    assert "hands" in res
    assert "market" in res
    assert len(res["market"]) <= 10
