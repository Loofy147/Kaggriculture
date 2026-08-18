# Trace Research Simulator — Oracle / Validity Review v0.4

## Purpose
This round did not add a new agent architecture. It strengthened the experimental reference layer so that later claims about repair, trace invalidation, BOCPD, multi-trace selection, and replanning are grounded in explicit latent-state criteria.

## New instrumentation
- Full-information one-step oracle.
- Shallow rollout oracle (depth=3, beam=3) for delayed effects.
- `trace_score`, `oracle_score`, and `optimality_gap`.
- `trace_valid`, `trace_degraded_but_repairable`, and `trace_obsolete` labels.
- Event-conditioned causal comparison against a matched clean world with the same seed and fork state.

## Tests
9/9 tests pass.

## Important findings
### 1. Absolute trace invalidity is not synonymous with perturbation-caused invalidity
A trace can be suboptimal because of ordinary opponent/resource interactions even before the named perturbation begins. Therefore a raw `optimality_gap` cannot be interpreted as causal evidence.

### 2. Matched clean-vs-perturbed forks provide a causal signal
At event-aligned fork points, the one-step oracle showed:
- local: mean delta-gap ≈ +0.146 (95% CI ≈ ±0.098), with 8% causal switches to obsolete.
- regime: mean delta-gap ≈ +0.274 (95% CI ≈ ±0.033), but no obsolete switch under the current threshold.
- structural: ≈ 0 at the immediate fork.
- adversarial: ≈ 0 at the immediate fork.

These are simulator-specific observations, not general claims.

### 3. Delayed effects require a multi-step oracle
The depth-3 rollout preserved the regime effect (mean delta-gap ≈ +0.280) but still found essentially no immediate structural/adversarial obsolescence. This indicates that the current structural and adversarial perturbations do not create sufficiently direct decision-relevant consequences inside the current oracle horizon.

### 4. The oracle itself is now a research object
There are at least three distinct notions:
- immediate action optimality;
- short-horizon continuation optimality;
- long-horizon / full-task trace validity.

We must not collapse these into one `trace_obsolete` bit.

## Current epistemic status
- ESTABLISHED: the instrumentation separates latent truth from agent observation and supports matched counterfactual comparison.
- EXPERIMENTALLY_SUPPORTED: perturbation profiles can shift oracle gap differently at event-aligned forks.
- UNKNOWN: whether the current oracle is an adequate proxy for global optimality.
- OPEN: how to define a principled trace-validity criterion over long horizons.
- OPEN: how to construct structural and adversarial perturbations whose consequences are causally visible without hard-coding the expected result.

## Consequence for next architecture work
Do NOT add BOCPD yet as a permanent agent feature.

First construct a stronger oracle/evaluation layer with:
1. long-horizon counterfactual value;
2. explicit `trace_validity(t)` curve rather than a single Boolean;
3. a causal event timeline;
4. transition labels: local deviation / degraded trace / obsolete trace / objective change;
5. independent structural and adversarial world generators.

Only then should BOCPD be evaluated as a detector of the transition already defined by the oracle.
