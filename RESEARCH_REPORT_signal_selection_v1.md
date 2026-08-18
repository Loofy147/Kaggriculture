# Signal Selection Study v1 — Causal Event-Point Comparison

## Objective
Compare candidate observation-derived signals against the same oracle-defined causal trace-validity harm at the perturbation event point.

Signals:
- reward_residual
- dynamics_residual
- trace_deviation
- objective_reachability
- combined model using all four

## Experimental design
- Four profiles: local, regime, structural, adversarial.
- Training seeds: 0–29 per profile.
- Held-out test seeds: 30–49 per profile.
- 120 training episodes, 80 test episodes.
- Evaluation point: exact perturbation start.
- Oracle: depth-3 rollout with beam width 2.
- Causal label: rollout optimality-gap increase >= 0.05, or a causal clean→perturbed obsolete flip.
- The oracle remains evaluation-only; no oracle fields enter the candidate signals.

## Primary pooled results

| Signal | AUROC | AUPRC | Brier | ECE | Δgap correlation | Δgap MSE |
|---|---:|---:|---:|---:|---:|---:|
| reward_residual | 0.500 | 0.200 | 0.2500 | 0.300 | — | 0.12525 |
| dynamics_residual | **0.672** | 0.406 | 0.2444 | 0.340 | **0.330** | 0.11715 |
| trace_deviation | 0.500 | 0.200 | 0.2500 | 0.300 | — | 0.12525 |
| objective_reachability | 0.553 | 0.218 | **0.2496** | **0.299** | 0.124 | 0.12410 |
| combined | 0.650 | **0.484** | 0.2443 | 0.340 | **0.364** | **0.11378** |

## Interpretation

### Experimentally supported (limited)
1. `dynamics_residual` is the strongest single discriminator in the current pooled event-point experiment.
2. `combined` produces the best AUPRC and lowest Δgap MSE in this experiment, but does not beat the single dynamics signal on AUROC.
3. `trace_deviation` is not informative at the exact event point in this world because many perturbations have not yet caused a positional divergence.
4. `reward_residual` is also not informative at the exact event point; its effect is delayed by execution.
5. `objective_reachability` has only weak discrimination here. Its value may appear later in the episode rather than at event onset.

### Important limitations
- The pooled target is imbalanced (20% positive in the held-out set) and heavily influenced by the regime profile.
- Some profiles have too few positive causal transitions for stable per-profile discrimination estimates.
- The label uses a shallow rollout oracle; it is stronger than one-step scoring but is still an approximation, not global optimality.
- Event-point evaluation tests onset discrimination, not detection delay.
- No learned meta-controller has been trained or evaluated in this study.

## Current conclusion
Do **not** select one signal as the final controller signal yet.

The current evidence supports a working hierarchy for the next experiment:

1. Dynamics residual as the primary fast anomaly signal.
2. Objective reachability as a slower, task-level signal.
3. Trace deviation as a state-consistency signal that should be evaluated after action execution, not at event onset.
4. Reward residual as execution-outcome feedback rather than a general change detector.

The next confirmatory study should use profile-balanced sampling, per-profile metrics, and temporal windows around the event to test whether these signals predict the actual transition from `repairable` to `obsolete`, including detection delay and false alarms.

## Epistemic status
- **ESTABLISHED:** experimental protocol and causal separation used here.
- **EXPERIMENTALLY_SUPPORTED (LIMITED):** dynamics residual is the best single event-point discriminator in this setup; combined model improves AUPRC and gap prediction error.
- **UNKNOWN:** whether these rankings generalize to other worlds, horizons, perturbation families, or unseen dynamics.
- **OPEN:** whether the signals can drive a robust continue/repair/switch/replan controller.
