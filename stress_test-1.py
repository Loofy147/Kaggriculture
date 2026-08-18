from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor

from trace_middleware import ExecutionFeedback, create_agent


def run_sequential(iterations: int = 100_000):
    trace = [{"action": "MOVE", "i": i} for i in range(128)]
    engine = create_agent(trace)
    rng = random.Random(7)
    holds = 0
    attacks = 0
    fallbacks = 0

    start = time.perf_counter()
    for i in range(iterations):
        obs = {
            "step": i % 128,
            "blocked": (i % 19 == 0),
            "future_resource_pressure": (i % 11 == 0),
            "resource_prediction_confidence": rng.random(),
            "opponent_vulnerability": rng.random() if i % 13 == 0 else 0.0,
            "pressure_action": {"action": "ATTACK", "i": i},
        }

        feedback = None
        if i % 37 == 0:
            feedback = ExecutionFeedback(
                partial=True,
                remainder={"action": "RETRY", "i": i},
            )

        result = engine.decide(obs, feedback)
        action = result.action.get("action")
        holds += action == "HOLD"
        attacks += action == "ATTACK"
        fallbacks += action == "PASS"

    elapsed = time.perf_counter() - start
    return {
        "iterations": iterations,
        "elapsed_s": elapsed,
        "decisions_per_s": iterations / elapsed,
        "holds": holds,
        "attacks": attacks,
        "fallbacks": fallbacks,
        "history": len(engine.memory.history),
        "pending_actions": len(engine.memory.pending_actions),
    }


def run_parallel_instances(workers: int = 16, jobs: int = 64, per_job: int = 2_000):
    def job(seed: int):
        rng = random.Random(seed)
        engine = create_agent([{"action": "MOVE", "seed": seed} for _ in range(8)])
        for i in range(per_job):
            engine.act({
                "step": i % 8,
                "blocked": rng.random() < 0.05,
                "future_resource_pressure": rng.random() < 0.08,
                "resource_prediction_confidence": rng.random(),
                "opponent_vulnerability": rng.random() if rng.random() < 0.08 else 0.0,
                "pressure_action": {"action": "PRESSURE", "seed": seed},
            })
        return len(engine.memory.history), len(engine.memory.pending_actions)

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        result = list(pool.map(job, range(jobs)))
    elapsed = time.perf_counter() - start
    total_decisions = jobs * per_job
    return {
        "jobs": jobs,
        "workers": workers,
        "decisions": total_decisions,
        "elapsed_s": elapsed,
        "aggregate_decisions_per_s": total_decisions / elapsed,
        "history_ok": all(h == 1000 for h, _ in result),
    }


if __name__ == "__main__":
    print("SEQUENTIAL")
    print(run_sequential())
    print("PARALLEL INDEPENDENT INSTANCES")
    print(run_parallel_instances())
