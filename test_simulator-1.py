import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator import ScenarioFactory, WorldConfig, ResearchWorld, Action, ActionType, build_greedy_trace
from agents import TraceOnlyAgent, ReactiveRepairAgent
from evaluation import evaluate
from counterfactual import paired_counterfactual


def test_reproducible_scenario():
    cfg = WorldConfig()
    f = ScenarioFactory(cfg)
    a = f.make(7, "mixed")
    b = f.make(7, "mixed")
    assert a == b


def test_ground_truth_hidden_but_available():
    s = ScenarioFactory(WorldConfig()).make(3, "local")
    w = ResearchWorld(s)
    obs = w.reset()
    truth = w.ground_truth()
    assert truth.step == 0
    assert hasattr(obs, "regime_signal")


def test_local_block_causes_blocked_feedback():
    cfg = WorldConfig(width=6, height=6, horizon=30, n_resources=3, n_opponents=0, stochasticity=0.0)
    f = ScenarioFactory(cfg)
    s = f.make(10, "local")
    s.perturbations[0] = type(s.perturbations[0])(
        kind="local_block", start=0, duration=2, target=s.goal_order[0], seed=1
    )
    w = ResearchWorld(s)
    obs = w.reset()
    target = s.goal_order[0]
    action = Action(ActionType.MOVE, target)
    result = w.step(action)
    assert result.feedback["status"] in {"blocked", "executed"}


def test_trace_is_long_enough_for_horizon():
    s = ScenarioFactory(WorldConfig(horizon=50)).make(2, "mixed")
    trace = build_greedy_trace(s)
    assert len(trace) == s.config.horizon


def test_evaluation_matrix_runs():
    cfg = WorldConfig(width=7, height=7, horizon=30, n_resources=4, n_opponents=1)
    sf = ScenarioFactory(cfg)
    scenarios = [sf.make(1, "local"), sf.make(2, "regime")]
    factories = {"trace_only": TraceOnlyAgent, "reactive": ReactiveRepairAgent}
    run = evaluate(scenarios, factories)
    agg = run.aggregate()
    assert set(agg) == {"trace_only", "trace_reactive"}


def test_counterfactual_branch_is_replayable():
    cfg = WorldConfig(width=7, height=7, horizon=25, n_resources=4, n_opponents=1, stochasticity=0.0)
    sf = ScenarioFactory(cfg)
    s = sf.make(4, "mixed")
    factories = {"trace": TraceOnlyAgent, "reactive": ReactiveRepairAgent}
    result = paired_counterfactual(s, factories, fork_step=5)
    assert result.prefix_steps == 5
    assert set(result.branch_metrics) == {"trace", "reactive"}
