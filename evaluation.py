from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Any, Optional, Sequence
import copy
import json
import statistics

from simulator import Scenario, ResearchWorld, Action, ActionType, build_greedy_trace


@dataclass
class EpisodeMetrics:
    scenario_id: str
    agent: str
    total_reward: float
    success: bool
    steps: int
    final_goals_remaining: int
    goals_collected: int
    goals_lost: int
    catastrophic_failures: int
    blocked_actions: int
    partial_actions: int
    intervention_steps: int
    regime_steps: int
    trace_action_match_rate: float
    max_trace_deviation: float
    recovery_debt: float
    mean_trace_position_deviation: float


@dataclass
class EvaluationRun:
    metrics: List[EpisodeMetrics]

    def aggregate(self) -> Dict[str, Dict[str, float]]:
        groups: Dict[str, List[EpisodeMetrics]] = {}
        for m in self.metrics:
            groups.setdefault(m.agent, []).append(m)
        out = {}
        numeric = [
            "total_reward", "steps", "final_goals_remaining", "goals_collected", "goals_lost", "catastrophic_failures",
            "blocked_actions", "partial_actions", "intervention_steps", "regime_steps",
            "trace_action_match_rate", "max_trace_deviation", "recovery_debt", "mean_trace_position_deviation"
        ]
        for agent, rows in groups.items():
            d = {k: statistics.mean(getattr(r, k) for r in rows) for k in numeric}
            d["success_rate"] = statistics.mean(float(r.success) for r in rows)
            out[agent] = d
        return out

    def save_json(self, path: str):
        payload = {"metrics": [asdict(m) for m in self.metrics], "aggregate": self.aggregate()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


def _dist(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def run_episode(scenario: Scenario, agent_factory: Callable[[List[Action]], Any]) -> EpisodeMetrics:
    world = ResearchWorld(scenario)
    trace = build_greedy_trace(scenario)
    agent = agent_factory(trace)
    agent.reset()
    obs = world.reset()
    matched = 0
    max_dev = 0
    deviation_sum = 0.0
    interventions = 0
    blocked = 0
    partial = 0
    catastrophe = 0
    recovery_debt = 0.0
    previous_goal_count = len(world.ground_truth().goal_remaining)
    feedback = None

    for _ in range(scenario.config.horizon):
        expected = trace[obs.step] if obs.step < len(trace) else Action(ActionType.WAIT)
        action = agent.act(obs, feedback)
        if action == expected:
            matched += 1
        if action != expected:
            interventions += 1
        truth_before = world.ground_truth()
        result = world.step(action)
        # Compare realized position against the position implied by the
        # reference trace after this transition.
        ref_pos = truth_before.agent.pos
        if expected.kind == ActionType.MOVE and expected.target is not None:
            ref_pos = world._step_toward(ref_pos, expected.target)
        deviation = _dist(result.truth.agent.pos, ref_pos)
        deviation_sum += deviation
        max_dev = max(max_dev, deviation)
        feedback = result.feedback
        if feedback["status"] == "blocked":
            blocked += 1
            recovery_debt += 1.0
        if feedback["partial"]:
            partial += 1
            recovery_debt += 0.5
        if feedback["status"] in {"blocked", "no_resource", "reserve_failed"}:
            catastrophe += 1 if feedback["status"] == "no_resource" else 0
        obs = result.observation
        if result.done:
            break
        # debt decays only when an intervention produces progress
        if feedback["executed"] and feedback["reward"] > 0:
            recovery_debt = max(0.0, recovery_debt - 0.1)
        previous_goal_count = len(result.truth.goal_remaining)

    truth = world.ground_truth()
    return EpisodeMetrics(
        scenario_id=scenario.scenario_id,
        agent=getattr(agent, "name", agent.__class__.__name__),
        total_reward=truth.total_reward,
        success=(len(truth.collected_goals) == len(truth.initial_goals)),
        goals_collected=len(truth.collected_goals),
        goals_lost=len(truth.lost_goals),
        steps=truth.step,
        final_goals_remaining=len(truth.goal_remaining),
        catastrophic_failures=catastrophe,
        blocked_actions=blocked,
        partial_actions=partial,
        intervention_steps=interventions,
        regime_steps=sum(1 for p in truth.perturbations if p.kind == "regime_change"),
        trace_action_match_rate=matched / max(1, truth.step),
        max_trace_deviation=max_dev,
        recovery_debt=recovery_debt,
        mean_trace_position_deviation=deviation_sum / max(1, truth.step),
    )


def evaluate(scenarios: Sequence[Scenario], factories: Dict[str, Callable[[List[Action]], Any]]) -> EvaluationRun:
    rows: List[EpisodeMetrics] = []
    for scenario in scenarios:
        for factory in factories.values():
            rows.append(run_episode(scenario, factory))
    return EvaluationRun(rows)
