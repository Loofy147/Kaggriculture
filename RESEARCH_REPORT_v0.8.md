# Trace Research Simulator v0.8 — Dynamics / Prediction Layer

## Purpose
Added an observation-only `OnlineDynamicsModel` that estimates short-term consequences of actions and trace execution from information available to the agent. It explicitly separates:

- instantaneous residuals;
- online action-conditioned reward residuals;
- resource-visibility changes;
- opponent relative motion;
- opponent pressure relative to the current trace target;
- persistence/decay of surprise signals.

The simulator oracle remains outside the agent-facing dynamics layer.

## Verification
23/23 tests pass.

## Important simulator correction
The `structural_block` perturbation now changes both local geometry and availability of its targeted resource. This makes structural perturbation causal to the future objective rather than merely geometric.

## Experiments
- Profiles: local, regime, structural, adversarial
- Seeds: 20/profile
- Horizon: 60
- Detector: corrected Gaussian BOCPD, detector parameters held fixed across channels
- Channels: instantaneous residuals, opponent-target pressure, persistent residuals, fused score
- Separate matched clean-vs-perturbed causal analysis

## Findings
### Dynamics representation contains useful signal, but it is heterogeneous
`reward_residual` is the strongest signal for regime changes. `opponent_target_pressure` can detect adversarial/structural-like situations in the current world, but its matched causal deltas are not consistently positive, so its current interpretation is not yet trustworthy as a causal indicator.

The persistent representation reduces some false alarms for `reward_residual` and gives modest detection of adversarial/regime/structural effects, but does not turn the system into a robust general-purpose detector.

### Current BOCPD results
Representative results from 20 seeds/profile:

- Local: reward residual detection 60%, false alarms 35%; opponent-target pressure 70% / 5%.
- Regime: reward residual 10% / 85%; fused 5% / 5%; persistent reward 0% / 30%.
- Structural: reward residual 50% / 75%; opponent-target pressure 60% / 20%; persistent reward 20% / 20%.
- Adversarial: reward residual 35% / 75%; opponent-target pressure 35% / 10%; persistent reward 20% / 15%; fused 20% / 0%.

These are **detector benchmark observations**, not claims that one feature is inherently superior. The same channel can be useful for one profile and misleading for another.

## Causal validity warning
The matched clean-vs-perturbed analysis shows weak/zero short-window causal deltas for structural events because the structural change can remain latent until the agent reaches the affected objective. This is evidence for a longer-horizon validity concept, not evidence that structural perturbation has no effect.

Similarly, the current opponent-target pressure signal can be non-causal because opponent placement and movement interact with partial observability. It must not yet be treated as an opponent-state estimator.

## Epistemic status
- ESTABLISHED: dynamics model uses only agent-visible observation, action, feedback, and trace target; it does not read simulator truth.
- EXPERIMENTALLY_SUPPORTED: 23/23 tests; dynamics residuals expose heterogeneous profile-dependent signals.
- EXPERIMENTALLY_SUPPORTED: persistence transforms reduce some noise but do not solve general detection.
- CONTRADICTED: the assumption that one fused residual stream will be a broadly reliable BOCPD input.
- OPEN: richer agent-accessible prediction targets and longer-horizon trace-validity signals.
- OPEN: calibrated opponent-dynamics representation rather than proximity heuristics.

## Next discriminating experiment
Do not put any detector into the policy yet. Build two explicit predictive targets:

1. **Trace outcome prediction:** expected next-step progress/cost under the reference action.
2. **Objective reachability prediction:** probability that the current trace target remains attainable/rewarding within horizon H.

Then evaluate their residuals against clean-vs-perturbed counterfactuals at multiple horizons before selecting any detector or meta-controller.
