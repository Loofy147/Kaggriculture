from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Sequence
import copy
import math
import random

Pos = Tuple[int, int]


class ActionType(str, Enum):
    MOVE = "MOVE"
    COLLECT = "COLLECT"
    WAIT = "WAIT"
    RESERVE = "RESERVE"


@dataclass(frozen=True)
class Action:
    kind: ActionType
    target: Optional[Pos] = None


@dataclass(frozen=True)
class Perturbation:
    kind: str
    start: int
    duration: int
    target: Optional[Pos] = None
    magnitude: float = 1.0
    observability: float = 1.0
    seed: int = 0

    @property
    def end(self) -> int:
        return self.start + max(1, self.duration)

    def active(self, step: int) -> bool:
        return self.start <= step < self.end


@dataclass
class WorldConfig:
    width: int = 9
    height: int = 9
    horizon: int = 80
    n_resources: int = 7
    n_opponents: int = 1
    resource_value: float = 10.0
    move_cost: float = 0.25
    wait_cost: float = 0.10
    collision_cost: float = 2.0
    failed_action_cost: float = 0.5
    depletion_value: float = 1.0
    opponent_strength: float = 0.65
    stochasticity: float = 0.05
    observation_radius: int = 5
    regime_move_cost_multiplier: float = 2.5
    regime_opponent_bonus: float = 0.25


@dataclass
class ResourceState:
    pos: Pos
    value: float
    available: bool = True
    owner: Optional[str] = None


@dataclass
class AgentTruth:
    name: str
    pos: Pos
    score: float = 0.0
    alive: bool = True


@dataclass
class WorldTruth:
    step: int
    regime: int
    agent: AgentTruth
    opponents: Dict[str, AgentTruth]
    resources: Dict[int, ResourceState]
    blocked: set[Pos]
    perturbations: List[Perturbation]
    goal_remaining: List[Pos]
    initial_goals: List[Pos] = field(default_factory=list)
    collected_goals: List[Pos] = field(default_factory=list)
    lost_goals: List[Pos] = field(default_factory=list)
    total_reward: float = 0.0


@dataclass
class Observation:
    step: int
    agent_pos: Pos
    visible_resources: Dict[int, ResourceState]
    visible_opponents: Dict[str, AgentTruth]
    blocked_visible: List[Pos]
    future_resource_pressure: bool
    resource_prediction_confidence: float
    opponent_vulnerability: float
    pressure_action: Optional[Dict[str, Any]]
    regime_signal: float
    trace_cursor: int


@dataclass
class StepResult:
    observation: Observation
    feedback: Dict[str, Any]
    truth: WorldTruth
    done: bool


@dataclass
class Scenario:
    scenario_id: str
    config: WorldConfig
    seed: int
    start: Pos
    resources: List[Pos]
    goal_order: List[Pos]
    perturbations: List[Perturbation]
    opponent_starts: Dict[str, Pos]


class ScenarioFactory:
    """Generates controlled worlds with reproducible seeds and perturbation families."""

    def __init__(self, config: WorldConfig):
        self.config = config

    def _sample_pos(self, rng: random.Random, used: set[Pos]) -> Pos:
        while True:
            p = (rng.randrange(self.config.width), rng.randrange(self.config.height))
            if p not in used:
                used.add(p)
                return p

    def make(self, seed: int, profile: str = "mixed") -> Scenario:
        rng = random.Random(seed)
        used: set[Pos] = set()
        start = self._sample_pos(rng, used)
        resources = [self._sample_pos(rng, used) for _ in range(self.config.n_resources)]
        goal_order = sorted(resources, key=lambda p: abs(p[0]-start[0]) + abs(p[1]-start[1]))
        opponent_starts = {
            f"opp_{i}": self._sample_pos(rng, used)
            for i in range(self.config.n_opponents)
        }

        perturbations: List[Perturbation] = []
        if profile in {"local", "mixed", "all"}:
            perturbations.append(Perturbation(
                kind="local_block",
                start=12,
                duration=5,
                target=goal_order[min(2, len(goal_order)-1)],
                magnitude=1.0,
                observability=0.9,
                seed=seed + 11,
            ))
        if profile in {"regime", "mixed", "all"}:
            perturbations.append(Perturbation(
                kind="regime_change",
                start=28,
                duration=self.config.horizon,
                target=None,
                magnitude=1.0,
                observability=0.65,
                seed=seed + 22,
            ))
        if profile in {"structural", "mixed", "all"}:
            perturbations.append(Perturbation(
                kind="resource_removed",
                start=40,
                duration=self.config.horizon,
                target=goal_order[-1],
                magnitude=1.0,
                observability=0.7,
                seed=seed + 33,
            ))
        if profile in {"adversarial", "mixed", "all"} and self.config.n_opponents:
            perturbations.append(Perturbation(
                kind="opponent_adaptation",
                start=22,
                duration=self.config.horizon,
                target=None,
                magnitude=self.config.opponent_strength,
                observability=0.5,
                seed=seed + 44,
            ))

        return Scenario(
            scenario_id=f"seed={seed}|profile={profile}",
            config=self.config,
            seed=seed,
            start=start,
            resources=resources,
            goal_order=goal_order,
            perturbations=perturbations,
            opponent_starts=opponent_starts,
        )


class ResearchWorld:
    """Discrete world exposing partial observations while retaining full ground truth."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.rng = random.Random(scenario.seed)
        self.truth: Optional[WorldTruth] = None
        self.reset()

    def reset(self) -> Observation:
        cfg = self.scenario.config
        resources = {
            i: ResourceState(pos=p, value=cfg.resource_value)
            for i, p in enumerate(self.scenario.resources)
        }
        self.truth = WorldTruth(
            step=0,
            regime=0,
            agent=AgentTruth("agent", self.scenario.start),
            opponents={
                name: AgentTruth(name, pos)
                for name, pos in self.scenario.opponent_starts.items()
            },
            resources=resources,
            blocked=set(),
            perturbations=copy.deepcopy(self.scenario.perturbations),
            goal_remaining=list(self.scenario.goal_order),
            initial_goals=list(self.scenario.goal_order),
        )
        return self.observe()

    def _active(self, kind: str) -> List[Perturbation]:
        assert self.truth
        return [p for p in self.truth.perturbations if p.kind == kind and p.active(self.truth.step)]

    def _update_truth_effects(self) -> None:
        assert self.truth
        self.truth.blocked.clear()
        for p in self._active("local_block"):
            if p.target is not None:
                self.truth.blocked.add(p.target)
        for p in self._active("resource_removed"):
            if p.target is not None:
                for r in self.truth.resources.values():
                    if r.pos == p.target:
                        r.available = False
                        r.value = self.scenario.config.depletion_value
        self.truth.regime = 1 if self._active("regime_change") else 0

    def _opponent_policy(self, opponent: AgentTruth) -> Action:
        assert self.truth
        # Baseline opponents drift toward nearest available resource.
        candidates = [r.pos for r in self.truth.resources.values() if r.available]
        if not candidates:
            return Action(ActionType.WAIT)
        if self._active("opponent_adaptation"):
            # Adaptive opponent becomes more aggressive: target the resource
            # nearest to the main agent rather than its own nearest one.
            target = min(candidates, key=lambda p: abs(p[0]-self.truth.agent.pos[0]) + abs(p[1]-self.truth.agent.pos[1]))
        else:
            target = min(candidates, key=lambda p: abs(p[0]-opponent.pos[0]) + abs(p[1]-opponent.pos[1]))
        return Action(ActionType.MOVE, target)

    @staticmethod
    def _step_toward(src: Pos, target: Pos) -> Pos:
        x, y = src
        tx, ty = target
        if x < tx: return (x+1, y)
        if x > tx: return (x-1, y)
        if y < ty: return (x, y+1)
        if y > ty: return (x, y-1)
        return src

    def step(self, action: Action) -> StepResult:
        assert self.truth
        cfg = self.scenario.config
        self._update_truth_effects()
        t = self.truth
        prev_pos = t.agent.pos
        executed = True
        status = "executed"
        reward = 0.0
        remainder = None

        if action.kind == ActionType.MOVE and action.target is not None:
            desired = self._step_toward(t.agent.pos, action.target)
            if desired in t.blocked:
                executed = False
                status = "blocked"
                reward -= cfg.collision_cost
                remainder = {"kind": ActionType.MOVE.value, "target": action.target}
            else:
                t.agent.pos = desired
                move_cost = cfg.move_cost * (cfg.regime_move_cost_multiplier if self._active("regime_change") else 1.0)
                reward -= move_cost

        elif action.kind == ActionType.COLLECT:
            found = None
            for rid, r in t.resources.items():
                if r.pos == t.agent.pos and r.available:
                    found = rid
                    break
            if found is None:
                executed = False
                status = "no_resource"
                reward -= cfg.failed_action_cost
            else:
                r = t.resources[found]
                # Partial execution models a generic execution disturbance.
                if self.rng.random() < cfg.stochasticity:
                    r.value *= 0.5
                    reward += r.value
                    r.available = False
                    status = "partial"
                    remainder = {"kind": ActionType.COLLECT.value, "target": t.agent.pos}
                else:
                    reward += r.value
                    r.available = False
                if t.agent.pos in t.goal_remaining:
                    t.goal_remaining.remove(t.agent.pos)
                    if t.agent.pos not in t.collected_goals:
                        t.collected_goals.append(t.agent.pos)

        elif action.kind == ActionType.RESERVE and action.target is not None:
            # Reservation is successful only if resource remains free.
            for r in t.resources.values():
                if r.pos == action.target and r.available and r.owner is None:
                    r.owner = "agent"
                    reward += 0.1
                    break
            else:
                executed = False
                status = "reserve_failed"
                reward -= cfg.failed_action_cost

        else:
            reward -= cfg.wait_cost

        # Opponents act after the protagonist. They can capture resources.
        for name, opp in t.opponents.items():
            opp_action = self._opponent_policy(opp)
            if opp_action.kind == ActionType.MOVE and opp_action.target is not None:
                opp.pos = self._step_toward(opp.pos, opp_action.target)
                for r in t.resources.values():
                    if r.available and r.pos == opp.pos:
                        strength = min(1.0, self.scenario.config.opponent_strength + (cfg.regime_opponent_bonus if self._active("regime_change") else 0.0))
                        if self.rng.random() < strength:
                            r.available = False
                            r.value = self.scenario.config.depletion_value
                            if r.pos in t.goal_remaining:
                                t.goal_remaining.remove(r.pos)
                                if r.pos not in t.lost_goals:
                                    t.lost_goals.append(r.pos)
        t.agent.score += reward
        t.total_reward += reward
        t.step += 1
        done = t.step >= cfg.horizon

        self._update_truth_effects()
        obs = self.observe()
        feedback = {
            "accepted": True,
            "executed": executed,
            "partial": status == "partial",
            "status": status,
            "remainder": remainder,
            "reward": reward,
            "prev_pos": prev_pos,
            "new_pos": t.agent.pos,
        }
        return StepResult(obs, feedback, copy.deepcopy(t), done)

    def observe(self) -> Observation:
        assert self.truth
        t = self.truth
        # Partial observability is controlled by perturbation observability.
        radius = self.scenario.config.observation_radius
        visible_resources = {}
        for rid, r in t.resources.items():
            if r.available and abs(r.pos[0]-t.agent.pos[0]) + abs(r.pos[1]-t.agent.pos[1]) <= radius:
                visible_resources[rid] = copy.deepcopy(r)
        visible_opponents = {
            name: copy.deepcopy(o)
            for name, o in t.opponents.items()
            if abs(o.pos[0]-t.agent.pos[0]) + abs(o.pos[1]-t.agent.pos[1]) <= radius
        }
        blocked_visible = [
            p for p in t.blocked
            if abs(p[0]-t.agent.pos[0]) + abs(p[1]-t.agent.pos[1]) <= radius
        ]

        future_pressure = any(
            abs(r.pos[0]-t.agent.pos[0]) + abs(r.pos[1]-t.agent.pos[1]) <= 3
            for r in visible_resources.values()
        )
        confidence = 0.75 if future_pressure else 0.25
        if self._active("regime_change"):
            confidence *= 0.65

        vulnerability = 0.0
        pressure_action = None
        if visible_opponents:
            nearest = min(
                visible_opponents.values(),
                key=lambda o: abs(o.pos[0]-t.agent.pos[0]) + abs(o.pos[1]-t.agent.pos[1])
            )
            distance = abs(nearest.pos[0]-t.agent.pos[0]) + abs(nearest.pos[1]-t.agent.pos[1])
            vulnerability = max(0.0, min(1.0, 1.0 - distance / (self.scenario.config.width + self.scenario.config.height)))
            pressure_action = {"kind": ActionType.RESERVE.value, "target": nearest.pos}

        regime_signal = 0.8 if self._active("regime_change") else 0.1
        return Observation(
            step=t.step,
            agent_pos=t.agent.pos,
            visible_resources=visible_resources,
            visible_opponents=visible_opponents,
            blocked_visible=blocked_visible,
            future_resource_pressure=future_pressure,
            resource_prediction_confidence=confidence,
            opponent_vulnerability=vulnerability,
            pressure_action=pressure_action,
            regime_signal=regime_signal,
            trace_cursor=min(t.step, len(self.scenario.goal_order)-1),
        )

    def ground_truth(self) -> WorldTruth:
        assert self.truth
        return copy.deepcopy(self.truth)


def build_greedy_trace(scenario: Scenario) -> List[Action]:
    """Reference trace: move to each goal in order, then collect."""
    actions: List[Action] = []
    pos = scenario.start
    for target in scenario.goal_order:
        while pos != target:
            pos = ResearchWorld._step_toward(pos, target)
            actions.append(Action(ActionType.MOVE, target))
        actions.append(Action(ActionType.COLLECT, target))
    while len(actions) < scenario.config.horizon:
        actions.append(Action(ActionType.WAIT))
    return actions[:scenario.config.horizon]


def action_from_dict(d: Dict[str, Any]) -> Action:
    return Action(ActionType(d["kind"] if "kind" in d else d["action"]), tuple(d["target"]) if d.get("target") is not None else None)
