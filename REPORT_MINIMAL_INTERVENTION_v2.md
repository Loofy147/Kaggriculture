# Comparative Benchmark v2 — Minimal Sufficient Intervention

## Purpose

This benchmark tests the current research hypothesis:

> A controller that preserves a reference Trace and applies the **smallest sufficient intervention** can improve robustness while avoiding the high intervention cost of aggressive replanning.

The benchmark is paired: every architecture sees the same scenario, seed, perturbation, and world dynamics.

## Metric correction

The prior Boolean `exact_success` metric was saturated and therefore excluded from ranking.

This version uses continuous task metrics:

- **Objective completion:** collected goals / initial goals.
- **Progress score:** `(collected - 0.75 * lost) / initial_goals`.
- **Reward**.
- **Catastrophe rate:** no-resource failures / steps.
- **Intervention rate/cost:** common action-deviation cost applied identically to every architecture.
- **Recovery debt** and trace deviation as secondary diagnostics.

The Meta Observer requires variance in completion/progress before treating them as discriminative metrics.

## Minimal-Intervention implementation

`MinimalInterventionAgent` is deliberately conservative:

1. Preserve the Trace when the reference action is feasible.
2. If the Trace is visibly blocked, apply a local detour.
3. Switch to another visible resource only after stronger evidence of failure (hard execution failure or high regime signal).
4. Otherwise hold the reference.

This is a representative implementation of the hypothesis, not a claim-equivalent reproduction of any published architecture.

## Experimental scale

- In-distribution: 30 seeds × 5 profiles = 150 scenarios.
- OOD: 15 seeds × 5 profiles = 75 scenarios.
- 10 architectures per paired scenario.

Profiles:

- local
- regime
- structural
- adversarial
- mixed

## Primary result

### In-distribution

| Architecture | Reward | Progress | Completion | Catastrophe rate | Intervention cost |
|---|---:|---:|---:|---:|---:|
| Trace-only | 8.457 | -0.113 | 0.361 | 0.0746 | 0.000 |
| Minimal intervention | 6.907 | -0.150 | 0.335 | 0.0794 | 0.0737 |
| Option switch | 8.579 | -0.119 | 0.357 | 0.0748 | 0.0607 |
| Simplex representative | 13.793 | -0.092 | 0.362 | 0.0153 | 1.0265 |
| Triggered replan | 8.366 | -0.187 | 0.305 | 0.0619 | 0.3772 |
| Replan | 17.964 | -0.081 | 0.368 | 0.0026 | 1.1801 |

The proposed Minimal-Intervention controller is **not on the Pareto frontier** in this configuration.

### Paired result vs Trace-only

Difference is defined as:

`Minimal Intervention - Trace-only`

- Reward: **-1.55**, 95% CI [-2.51, -0.59].
- Progress: **-0.0371**, 95% CI [-0.0557, -0.0186].
- Intervention cost: **+0.0737**, 95% CI [0.0607, 0.0866].
- Catastrophe rate: **+0.00489**, 95% CI [0.00285, 0.00693].

This is a **negative result** for the current formulation.

### OOD

Minimal intervention remains close to Trace-only in intervention rate, but its mean reward is lower:

- Minimal intervention reward: **-8.041**
- Trace-only reward: **-7.400**
- Paired reward difference: **-0.641**, 95% CI [-1.31, 0.026].

The OOD confidence interval crosses zero, so the reward degradation is not established as statistically different from Trace-only in this sample.

## Interpretation

The experiment does **not** support the claim that minimal local intervention is beneficial in the current simulator.

It does support a narrower statement:

> A conservative controller can keep intervention low, but low intervention alone does not imply better task performance.

This is important because it rejects a tempting but unjustified objective:

`minimize intervention` alone.

The controller needs a state-dependent constraint such as:

`minimize intervention cost subject to maintaining a target probability of objective success`.

## Current evidence status

### EXPERIMENTALLY_SUPPORTED

- The corrected objective metrics are non-saturated in the current benchmark.
- Paired evaluation is sensitive enough to detect meaningful differences among architectures.
- Aggressive replanning trades substantially higher intervention cost for lower catastrophe rates in this world.

### CONTRADICTED / REJECTED FOR CURRENT SETUP

- “Minimal intervention” as a standalone heuristic is better than Trace-only.
- “Keep intervention low” is sufficient as the optimization target.

### OPEN

- Whether a **validity-constrained** minimal intervention controller can dominate Trace-only.
- Whether objective reachability can define the constraint that minimal intervention needs.
- Whether the result survives new dynamics families and adversarial composition.

## Meta-Observer decision

The benchmark passes the current metric-health gate:

- objective-completion variance > 0
- progress-score variance > 0
- paired scenario identity preserved
- common intervention cost applied to every architecture
- OOD split uses unseen configuration family

Therefore these results are admissible as evidence, with the stated limitations.

## Next discriminating experiment

Do **not** tune MinimalInterventionAgent to improve its score.

Instead test the stronger hypothesis:

\[
\min_a C_{intervention}(a)
\quad\text{s.t.}\quad
\hat P(\text{objective success}\mid a,b_t)\ge \eta
\]

with the reachability model trained separately from evaluation seeds.

That experiment directly tests whether the previously observed Objective Reachability signal can convert the failed “minimal intervention” heuristic into a principled meta-controller.
