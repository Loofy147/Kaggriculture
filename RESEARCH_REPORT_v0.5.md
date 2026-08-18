# Trace Research Simulator — Validity Curves v0.5

## Purpose
Established an explicit long-horizon trace-validity curve and a matched clean-vs-perturbed decision-landscape comparison before adding BOCPD.

## Tests
12/12 unit/integration tests passed.

## Definitions
- `trace_value(H)`: value of continuing the reference trace for horizon H.
- `best_value(H)`: shallow beam-search full-information continuation value.
- `gap(H) = best_value(H) - trace_value(H)`.
- `valid`: gap <= 0.5; `degraded`: 0.5 < gap < 2.0; `obsolete`: gap >= 2.0. These thresholds are engineering test thresholds, not established facts.
- `objective_changed`: decision-landscape proxy: best first action changes or the causal gap changes by >0.5. This is NOT a proof that the formal objective function changed.

## Smoke-sweep results

### local
- H=1: mean_gap=0.251, obsolete_rate=0.017, degraded_rate=0.006, repairable_rate=0.983, action_change_rate=0.606
- H=3: mean_gap=0.467, obsolete_rate=0.028, degraded_rate=0.289, repairable_rate=0.972, action_change_rate=0.622
- H=5: mean_gap=0.569, obsolete_rate=0.033, degraded_rate=0.450, repairable_rate=0.967, action_change_rate=0.622

### regime
- H=1: mean_gap=0.212, obsolete_rate=0.006, degraded_rate=0.083, repairable_rate=0.994, action_change_rate=0.600
- H=3: mean_gap=0.463, obsolete_rate=0.006, degraded_rate=0.361, repairable_rate=0.994, action_change_rate=0.617
- H=5: mean_gap=0.598, obsolete_rate=0.072, degraded_rate=0.400, repairable_rate=0.928, action_change_rate=0.617

### structural
- H=1: mean_gap=0.210, obsolete_rate=0.006, degraded_rate=0.017, repairable_rate=0.994, action_change_rate=0.600
- H=3: mean_gap=0.457, obsolete_rate=0.033, degraded_rate=0.289, repairable_rate=0.967, action_change_rate=0.617
- H=5: mean_gap=0.588, obsolete_rate=0.039, degraded_rate=0.433, repairable_rate=0.961, action_change_rate=0.617

### adversarial
- H=1: mean_gap=0.234, obsolete_rate=0.006, degraded_rate=0.083, repairable_rate=0.994, action_change_rate=0.622
- H=3: mean_gap=0.494, obsolete_rate=0.006, degraded_rate=0.378, repairable_rate=0.994, action_change_rate=0.639
- H=5: mean_gap=0.656, obsolete_rate=0.028, degraded_rate=0.461, repairable_rate=0.972, action_change_rate=0.639

## Causal event-aligned results

### local
- H=1: mean_delta_gap=0.125, validity_change_rate=0.100, objective_change_rate=0.100, max_delta_gap=1.900
- H=3: mean_delta_gap=0.410, validity_change_rate=0.200, objective_change_rate=0.200, max_delta_gap=3.000
- H=5: mean_delta_gap=0.370, validity_change_rate=0.250, objective_change_rate=0.300, max_delta_gap=3.300

### regime
- H=1: mean_delta_gap=0.113, validity_change_rate=0.300, objective_change_rate=0.000, max_delta_gap=0.375
- H=3: mean_delta_gap=0.375, validity_change_rate=0.300, objective_change_rate=0.400, max_delta_gap=1.125
- H=5: mean_delta_gap=0.675, validity_change_rate=0.000, objective_change_rate=0.500, max_delta_gap=1.500

### structural
- H=1: mean_delta_gap=0.000, validity_change_rate=0.000, objective_change_rate=0.000, max_delta_gap=0.000
- H=3: mean_delta_gap=0.000, validity_change_rate=0.000, objective_change_rate=0.000, max_delta_gap=0.000
- H=5: mean_delta_gap=0.000, validity_change_rate=0.000, objective_change_rate=0.000, max_delta_gap=0.000

### adversarial
- H=1: mean_delta_gap=0.012, validity_change_rate=0.050, objective_change_rate=0.100, max_delta_gap=0.200
- H=3: mean_delta_gap=-0.090, validity_change_rate=0.150, objective_change_rate=0.200, max_delta_gap=0.450
- H=5: mean_delta_gap=-0.387, validity_change_rate=0.300, objective_change_rate=0.450, max_delta_gap=0.600

## Epistemic status
- ESTABLISHED: validity curves and matched clean-vs-perturbed measurements are now implemented and tested.
- EXPERIMENTALLY_SUPPORTED: the trace gap is horizon-dependent and different perturbation profiles alter the decision landscape differently in this simulator.
- UNKNOWN: whether these validity labels predict actual optimal replanning decisions outside this simulator.
- OPEN: calibrate thresholds; add full-task oracle; define objective-change independently of action switching; then evaluate BOCPD as a detector.
