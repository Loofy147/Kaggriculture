# Comparative Architecture Benchmark v1

## Purpose

This benchmark converts the research simulator into a comparative testbed for several **architecture families** relevant to the current project. The implementations in this repository are **representative baselines**, not faithful reimplementations of every cited paper. Claims about those papers are limited to the architectural principles used to define the baseline.

## Baseline families

| Baseline | Role in this benchmark | Evidence family |
|---|---|---|
| `trace_only` | Reference trajectory execution with no reactive intervention | Project baseline |
| `trace_reactive` | Local reactive repair | Reactive plan repair / execution monitoring |
| `behavior_tree` | Hierarchical/reactive selector | Behavior Trees emphasize modularity, hierarchy, feedback, and task switching. |
| `plan_monitor_repair` | Detect execution failure then construct a local replacement action | Reactive plan repair |
| `simplex_representative` | Advanced controller + monitor-triggered reversionary controller | Simplex / Runtime Assurance |
| `option_switch` | State-dependent switching among temporally extended behaviors | Options / temporal abstraction |
| `validity_aware_prototype` | Project hypothesis: continue vs intervene based on online evidence | Experimental prototype; not literature baseline |

Relevant evidence includes Behavior Trees as a modular/hierarchical/feedback architecture, reactive plan-repair strategies for execution failures, Simplex Runtime Assurance with an advanced controller, trusted/reversionary controller and runtime monitor, and the options framework for temporally extended policies. See source references below.

## Protocol

- Same world instance and scenario ID for every baseline.
- No baseline receives oracle fields.
- In-distribution suite: 40 seeds × 5 profiles = 200 scenarios.
- OOD suite: 20 unseen seeds × 5 profiles = 100 scenarios, with changed world geometry and dynamics parameters.
- Every scenario is replayed independently for every baseline.
- Deterministic replay is checked by hashing the complete row sequence.
- Per-profile results are retained; pooled averages are not treated as sufficient evidence.

## Important interpretation constraint

The exact-success metric is currently **saturated at zero** in this environment. That makes it non-discriminative and it must not be used to claim one architecture is better than another. Completion/fractional objective metrics remain usable, subject to variance and calibration checks.

Similarly, reward-retention ratios are not reported when the reward changes sign; the benchmark uses signed delta and symmetric change instead.

## Current results

The first 40-seed in-distribution run shows a strong trade-off rather than a single winner:

- `trace_only`: highest stability and zero intervention, but high failure exposure.
- `simplex_representative`: substantially fewer `no_resource`/catastrophic events and higher reward in the current in-distribution suite, at the cost of very high intervention/switch activity. This is **not a safety guarantee** because the implementation does not have a verified reversionary controller or verified decision module.
- `validity_aware_prototype`: reduces blocked actions and catastrophic events compared with Trace-only, but at very high intervention cost and lower goal collection.
- `trace_reactive` and `behavior_tree` behave similarly in the current world, suggesting this simulator does not yet strongly distinguish these reactive architectures.
- `plan_monitor_repair` underperforms in the current world, indicating that immediate local replanning can be harmful under these dynamics.

These are **benchmark observations**, not generalized claims.

## Meta-observer gates

The benchmark must reject or qualify a result when:

1. Exact success is saturated or has insufficient variance.
2. A profile has insufficient positive/negative event support for the requested metric.
3. Scenario IDs differ across compared agents.
4. Observation schema contains oracle validity or future-optimality labels.
5. Replay is nondeterministic when the protocol requires deterministic replay.
6. A metric is ill-conditioned (e.g. ratio with denominator near zero or sign-changing reward).
7. A pooled metric masks substantial profile heterogeneity.

## Design consequence

The benchmark therefore evaluates not merely `mean reward`, but a vector of outcomes:

\[
(
R,
\text{completion},
\text{catastrophic failures},
\text{interventions},
\text{switches},
\text{recovery debt},
\text{trace deviation}
)
\]

This exposes the central research trade-off:

\[
\boxed{\text{reference stability}\;\leftrightarrow\;\text{reactivity}\;\leftrightarrow\;\text{risk/control authority}}
\]

The next hypothesis should therefore not be “our architecture wins.” It should be whether a **validity-aware controller can dominate the existing Pareto frontier by selecting the minimum sufficient intervention**.

## Research classification

- Architecture families in the benchmark: **ESTABLISHED PRIOR ART / REPRESENTATIVE BASELINES**.
- Current simulator comparison: **EXPERIMENTALLY_SUPPORTED, ENVIRONMENT-BOUND**.
- Validity-aware controller: **HYPOTHESIS / EARLY PROTOTYPE**.
- Generalization beyond this world family: **OPEN**.
- Safety claims about the Simplex representative: **NOT ESTABLISHED**.

## Sources

- Behavior Trees survey: https://www.annualreviews.org/content/journals/10.1146/annurev-control-042920-095314
- Reactive plan repair example: https://www.sciencedirect.com/science/article/abs/pii/S0094576520302940
- Simplex / Runtime Assurance: https://ntrs.nasa.gov/citations/20240007986
- Black-Box Simplex Architecture: https://arxiv.org/abs/2102.12981
- Options / temporal abstraction: https://www.sciencedirect.com/science/article/pii/S0004370299000521
- MAXQ hierarchical RL: https://arxiv.org/abs/cs/9905014
- Procgen generalization benchmark: https://proceedings.mlr.press/v119/cobbe20a.html
