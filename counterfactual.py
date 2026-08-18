from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence

from simulator import Action, ResearchWorld, Scenario, build_greedy_trace


@dataclass
class ForkResult:
    prefix_steps: int
    branch_metrics: Dict[str, Any]


def snapshot_world(world: ResearchWorld):
    return copy.deepcopy(world)


def snapshot_agent(agent):
    return copy.deepcopy(agent)


def run_branch(world: ResearchWorld, agent: Any, horizon: int) -> Dict[str, Any]:
    feedback = None
    for _ in range(horizon):
        obs = world.observe()
        action = agent.act(obs, feedback)
        result = world.step(action)
        feedback = result.feedback
        if result.done:
            break
    truth = world.ground_truth()
    return {
        "steps": truth.step,
        "reward": truth.total_reward,
        "collected_goals": len(truth.collected_goals),
        "lost_goals": len(truth.lost_goals),
        "success": len(truth.collected_goals) == len(truth.initial_goals),
    }


def paired_counterfactual(
    scenario: Scenario,
    agent_factories: Dict[str, Callable[[List[Action]], Any]],
    fork_step: int,
) -> ForkResult:
    """Run a common prefix and then fork exact world state for each agent.

    This makes the environment latent state identical at the branch point.
    It is not a claim of common random numbers after branching; branches are
    independent replay trajectories from the same state snapshot.
    """
    base_world = ResearchWorld(scenario)
    trace = build_greedy_trace(scenario)
    base_agents = {name: factory(trace) for name, factory in agent_factories.items()}
    for a in base_agents.values():
        a.reset()

    feedbacks = {name: None for name in base_agents}
    for _ in range(fork_step):
        obs = base_world.observe()
        # Prefix actions are deliberately all from TraceOnly-equivalent behavior
        # so the branch point state is architecture-independent.
        base_action = trace[obs.step]
        result = base_world.step(base_action)
        if result.done:
            break

    world_snapshot = snapshot_world(base_world)
    results = {}
    for name, factory in agent_factories.items():
        agent = factory(trace)
        agent.reset()
        # Advance agent's internal cursor to align with the fork point.
        for _ in range(fork_step):
            agent.act(world_snapshot.observe(), feedbacks[name])
        branch_world = snapshot_world(world_snapshot)
        results[name] = run_branch(branch_world, agent, scenario.config.horizon - fork_step)

    return ForkResult(prefix_steps=fork_step, branch_metrics=results)
