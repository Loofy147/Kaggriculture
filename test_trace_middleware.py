import copy
import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor

from trace_middleware import (
    Action,
    AgentMemory,
    AnticipatoryResourceOverlay,
    BaseOverlay,
    CollisionRepairOverlay,
    ExecutionFeedback,
    Intent,
    OverlayProposal,
    PriorityArbiter,
    ProposalKind,
    ReactivePipeline,
    TracePolicy,
    create_agent,
)


def test_trace_baseline_and_fallback():
    trace = [{"action": "A"}, {"action": "B"}]
    engine = ReactivePipeline(TracePolicy(trace), PriorityArbiter())
    assert engine.act({"step": 0}) == {"action": "A"}
    assert engine.act({"step": 1}) == {"action": "B"}
    assert engine.act({"step": 2}) == {"action": "PASS"}


def test_hard_constraint_beats_strategic_priority():
    trace = [{"action": "TRACE"}, {"action": "NEXT"}]
    engine = create_agent(trace)
    obs = {
        "step": 0,
        "future_resource_pressure": True,
        "resource_prediction_confidence": 1.0,
        "opponent_vulnerability": 1.0,
        "pressure_action": {"action": "ATTACK"},
        "blocked": True,
    }
    result = engine.decide(obs)
    assert result.action == {"action": "HOLD"}
    assert result.winning_source == "CollisionRepair"


def test_strategic_priority_resolves_without_hard_constraint():
    trace = [{"action": "TRACE"}, {"action": "NEXT"}]
    engine = create_agent(trace)
    obs = {
        "step": 0,
        "future_resource_pressure": True,
        "resource_prediction_confidence": 1.0,
        "opponent_vulnerability": 1.0,
        "pressure_action": {"action": "ATTACK"},
    }
    result = engine.decide(obs)
    assert result.action == {"action": "ATTACK"}
    assert result.winning_source == "AdversarialPressure"


def test_overlay_exception_isolated():
    class ExplodingOverlay(BaseOverlay):
        def __init__(self):
            super().__init__("explode", 99999)

        def propose(self, obs, intent, memory):
            raise RuntimeError("boom")

    logging.getLogger().setLevel(logging.CRITICAL)
    engine = ReactivePipeline(TracePolicy([{"action": "SAFE"}]), PriorityArbiter())
    engine.add_overlay(ExplodingOverlay())
    assert engine.act({"step": 0}) == {"action": "SAFE"}


def test_failed_overlay_cannot_mutate_intent():
    class MutateThenExplode(BaseOverlay):
        def __init__(self):
            super().__init__("mutate-explode", 10)

        def propose(self, obs, intent, memory):
            intent.action["action"] = "CORRUPTED"
            raise RuntimeError("boom")

    engine = ReactivePipeline(TracePolicy([{"action": "SAFE"}]), PriorityArbiter())
    engine.add_overlay(MutateThenExplode())
    assert engine.act({"step": 0}) == {"action": "SAFE"}


def test_execution_remainder_is_queued():
    engine = ReactivePipeline(TracePolicy([{"action": "A"}]), PriorityArbiter())
    feedback = ExecutionFeedback(
        accepted=True,
        executed=True,
        partial=True,
        remainder={"action": "REMAINDER", "qty": 3},
    )
    engine.act({"step": 0}, feedback=feedback)
    assert engine.memory.pending_actions == [{"action": "REMAINDER", "qty": 3}]


def test_history_is_bounded():
    engine = ReactivePipeline(
        TracePolicy([]), PriorityArbiter(), history_limit=7
    )
    for i in range(100):
        engine.act({"step": i})
    assert len(engine.memory.history) == 7
    assert engine.memory.history[0]["step"] == 93


def test_action_isolation_from_return_value():
    trace_action = {"action": "MOVE", "payload": {"x": 1}}
    engine = ReactivePipeline(TracePolicy([trace_action]), PriorityArbiter())
    output = engine.act({"step": 0})
    output["payload"]["x"] = 999
    assert engine.base_policy.trace[0]["payload"]["x"] == 1


def test_instances_are_state_isolated():
    e1 = create_agent([{"action": "A"}])
    e2 = create_agent([{"action": "B"}])
    e1.act({"step": 0})
    e1.act({"step": 1})
    e2.act({"step": 0})
    assert e1.memory.step == 1
    assert e2.memory.step == 0
    assert e1.memory.history is not e2.memory.history


def test_same_priority_uses_stable_order():
    class ProposalOverlay(BaseOverlay):
        def __init__(self, name, action):
            super().__init__(name, 50)
            self._action = action

        def propose(self, obs, intent, memory):
            return OverlayProposal(
                overlay=self.name,
                kind=ProposalKind.REPLACE,
                action={"action": self._action},
                priority=self.priority,
                confidence=1.0,
            )

    engine = ReactivePipeline(TracePolicy([{"action": "BASE"}]), PriorityArbiter())
    engine.add_overlay(ProposalOverlay("first", "FIRST"))
    engine.add_overlay(ProposalOverlay("second", "SECOND"))
    # reverse=True applies stable sorting semantics for equal keys.
    # The earlier equal-key element must remain first.
    assert engine.act({"step": 0}) == {"action": "FIRST"}


def test_randomized_safety_invariant():
    rng = random.Random(42)
    for _ in range(250):
        trace = [{"action": f"T{i}"} for i in range(3)]
        engine = create_agent(trace)
        step = rng.randrange(0, 3)
        blocked = bool(rng.randrange(2))
        vulnerability = rng.random()
        pressure = {"action": "PRESSURE", "token": rng.randrange(10)}
        obs = {
            "step": step,
            "blocked": blocked,
            "future_resource_pressure": bool(rng.randrange(2)),
            "resource_prediction_confidence": rng.random(),
            "opponent_vulnerability": vulnerability,
            "pressure_action": pressure,
        }
        result = engine.decide(obs)
        if blocked:
            assert result.action == {"action": "HOLD"}
        assert isinstance(result.action, dict)


def test_multithreaded_instance_is_not_shared_across_engines():
    # This stress test deliberately uses one independent engine per worker.
    # It validates instance-local state, not concurrent mutation safety of one engine.
    def run(i):
        engine = create_agent([{"action": i}])
        for j in range(30):
            engine.act({"step": 0, "blocked": (j % 7 == 0)})
        return engine.memory.step, len(engine.memory.history)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(run, range(64)))
    assert all(step == 0 for step, _ in results)
    assert all(hist == 30 for _, hist in results)


# Intentionally omitted: concurrent calls against ONE engine instance.
# The architecture is instance-local, not lock-protected. A dedicated lock
# or actor model would be required if one engine is shared between threads.

