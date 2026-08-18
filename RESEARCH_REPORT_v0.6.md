# Trace Research Simulator — BOCPD Detector Evaluation v0.6

## Scope
BOCPD was added strictly as an **observation-only detector**. It does not control repair, trace switching, or replanning in this version.

## Critical implementation correction
The first BOCPD implementation incorrectly used the existing-run predictive likelihood for both:
- run continuation, and
- the new-run / change-point transition.

That made posterior change probability collapse to the constant hazard. The implementation was corrected so the change-point branch uses the **prior predictive distribution** while continuation branches use the corresponding run-length posterior predictive distributions.

This correction invalidates the earlier detector benchmark; only v0.6 results are retained as evidence.

## Leakage control
The detector input intentionally excludes:
- `Observation.regime_signal`
- perturbation metadata
- simulator truth
- oracle validity labels

The current scalar detector feature uses only post-action observable feedback (reward/execution status).

## Unit tests
17/17 tests pass.

The corrected detector responds strongly to an obvious synthetic mean shift:
- peak change probability after the shift ≈ 0.945 with hazard lambda=30.

## Detector benchmark
40 episodes per profile, threshold=0.45, hazard lambda=40.

| Profile | Detection rate | Mean delay (detected) | Mean false alarms | Mean peak CP |
|---|---:|---:|---:|---:|
| local | 0.425 | 5.24 | 0.50 | 0.604 |
| regime | 0.000 | — | 0.875 | 0.597 |
| structural | 0.300 | 10.25 | 0.725 | 0.653 |
| adversarial | 0.750 | 12.13 | 0.625 | 0.829 |

## Feature ablation
A 20-seed ablation showed that no single scalar observation channel detects all perturbation families.

Examples:
- `reward` detects some local/adversarial changes but misses regime change.
- `blocked_visible` is useful for structural changes.
- visible-resource/opponent counts are weak standalone detectors in the current world.
- status alone is sparse and delayed.

## Epistemic status
- ESTABLISHED: corrected BOCPD implementation is numerically functional and tested.
- EXPERIMENTALLY_SUPPORTED: BOCPD can detect some perturbation families from observable feedback in this simulator.
- EXPERIMENTALLY_SUPPORTED: no tested scalar feature is sufficient for all current perturbation families.
- CONTRADICTED: the assumption that a single reward-based BOCPD stream is an adequate general-purpose regime detector in this world.
- UNKNOWN: whether a multi-channel belief/state representation can reliably recover the oracle transition labels.
- OPEN: build multi-channel observation/state features; calibrate hazard and thresholds; evaluate detector timing against oracle event timelines; only then connect detection to repair/switch/replan.
