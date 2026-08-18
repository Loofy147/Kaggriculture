# Trace Research Simulator — v0.3 Experimental Review

## Status

This revision upgrades the simulator from a baseline benchmark into a parameterized stress-test harness.

The key methodological correction was to ensure that experimental controls actually affect the world:

- `observability` now changes what perturbation-related signals reach the agent.
- observation noise uses an independent RNG stream from world dynamics.
- `magnitude` now changes local-block footprint, regime cost severity, and adaptive-opponent pressure where applicable.
- a `TriggeredReplanAgent` was added so replanning can be compared as a conditional intervention rather than as an always-on policy.

## Experiments executed

### Exploratory factor sweep

- 12 deterministic seeds per cell.
- Profiles: local, regime, structural, adversarial.
- Factors:
  - disturbance magnitude: 0.25, 0.75, 1.25, 1.75
  - observability: 0.2, 0.5, 0.8, 1.0
  - opponent strength: 0.1, 0.4, 0.7, 0.9
  - regime movement multiplier: 1.0, 1.75, 2.5, 3.5
- Agents:
  - trace_only
  - trace_reactive
  - trace_change_aware
  - trace_triggered_replan
  - trace_replan

Total: 4 profiles × 4 factors × 4 levels × 12 seeds × 5 agents = 3,840 episodes.

### Paired causal fork

50 seeds per profile, with branch points chosen to precede the corresponding perturbation:

- local: step 10
- regime: step 27
- structural: step 39
- adversarial: step 21
- mixed: step 21

Comparisons:

- reactive vs trace-only
- change-aware vs reactive
- triggered-replan vs change-aware

## Important findings

### 1. Local disturbance

At the causal fork, `trace_reactive` improved mean reward over `trace_only` by approximately +0.35 reward units (95% CI about ±0.22) across 50 paired seeds.

`trace_triggered_replan` was worse than `trace_change_aware` in this setting (mean delta approximately -1.05), although the confidence interval is wide. This is consistent with the hypothesis that premature replanning can be more costly than local repair.

### 2. Regime change

`trace_change_aware` substantially outperformed `trace_only` in the factor sweep as regime severity increased. In the paired causal fork, `trace_triggered_replan` was better than `trace_change_aware` by approximately +0.63 reward units (95% CI about ±0.14).

This is an initial empirical signal supporting a conditional policy of:

    local deviation -> repair
    regime transition -> replan

It is not yet a general theorem.

### 3. Structural change

The current structural perturbation removes a resource. Replanning improves reward in full-episode comparisons, but the conditional causal effect at the selected fork was small (+0.03 mean reward for triggered-replan over change-aware).

This suggests the present structural scenario is not yet sufficiently diagnostic. A stronger structural benchmark should change dependencies/feasibility rather than merely remove one resource.

### 4. Adversarial change

The present adversarial benchmark mainly changes opponent targeting. Triggered replanning produced a positive reward delta over change-aware, but this should not yet be interpreted as opponent-modeling evidence because no explicit opponent model exists.

### 5. Always-on replanning is not an apples-to-apples conclusion

`trace_replan` often scores strongly because it is effectively a continuously active alternative policy, selecting visible resources instead of following the reference trace. It is useful as a competitive baseline, but it is not equivalent to "replan only when needed".

Therefore the more scientifically relevant comparison is:

    trace_only
        vs
    repair
        vs
    change-aware repair
        vs
    triggered replan

with always-on replanning retained as an upper/competitive baseline.

## Methodological discoveries

### Observation/dynamics coupling was removed

Observation noise previously shared the same RNG stream as environment dynamics. That creates a confound: changing sensing behavior could change the future world trajectory. The streams are now independent.

### Parameter validity is now checked

A sweep parameter is only considered evidence-bearing if it changes a causal mechanism in the simulator. The previous `magnitude` sweep failed this requirement; it is no longer treated as evidence for the old results.

### Counterfactual branch points must be event-aligned

A fork after the relevant perturbation can yield zero treatment effect even when the agents differ earlier. Forks are now selected just before the perturbation family being tested.

## Current epistemic status

### ESTABLISHED BY TESTING

- simulator tests: 6/6 pass.
- reproducible scenarios.
- independent observation RNG.
- parameterized perturbation severity and observability.
- full latent ground truth.
- causal branch/replay mechanism.
- multiple agent controls can be compared under identical scenario seeds.

### EXPERIMENTALLY_SUPPORTED — PRELIMINARY

- local repair can outperform trace-only under local block disturbances.
- premature triggered replanning can be worse than local repair in local-disturbance settings.
- change-aware behavior can improve performance under the current regime-change model.
- triggered replanning can improve over change-aware behavior after regime changes.

### UNKNOWN

- whether these effects persist under broader dynamics.
- whether BOCPD improves the repair/replan gate.
- whether multi-trace selection improves over triggered replanning.
- whether hierarchical trace representations improve recovery.
- whether learned arbitration improves over the current hand-designed controls.

## Next environment upgrades before architectural expansion

1. Add an explicit `trace_validity` oracle to the ground truth.
2. Add a latent `optimal_action` / counterfactual planner oracle for diagnostic evaluation.
3. Replace single-resource structural failure with graph/dependency changes.
4. Add opponent policies with distinct adaptation classes rather than one adaptive heuristic.
5. Add a true belief-state/observation model instead of masking only selected signals.
6. Add bootstrap/permutation statistics and paired effect sizes to the evaluator.
7. Run a confirmation sweep only after the diagnostic environment is validated.

## Central research hypothesis

The simulator now supports direct testing of the following conditional-control hypothesis:

    H:
    choose among {continue, repair, switch-trace, replan}
    using evidence about deviation type and regime state,
    rather than committing to one response globally.

The present results make this hypothesis more plausible, but do not establish it as a general result.
