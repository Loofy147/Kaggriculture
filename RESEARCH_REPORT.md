# Trace Research Simulator — v0.2 Experimental Report

Date: 2026-08-17

## Purpose

The simulator is now the central experimental apparatus for comparing Trace-driven architectures under controlled perturbations. It is explicitly designed to **falsify** the central hypothesis rather than assume that the architecture is beneficial.

## World model

The world contains:

- spatial state and movement cost
- collectible resources and resource depletion
- multiple competing agents
- local temporary blockages
- structural resource removal
- an explicit regime change that modifies movement cost and opponent strength
- adaptive opponent behavior
- stochastic partial execution
- partial observation radius
- deterministic scenario seeds

The simulator maintains full latent ground truth while exposing a limited observation to the agent.

## Experimental controls

Current controls:

1. `trace_only`
2. `trace_reactive`
3. `trace_change_aware`
4. `trace_opportunistic`

These are controls for hypothesis testing, not claims of optimality.

## Evaluation metrics

- total reward
- success rate, defined as collecting the agent's complete original goal set
- goals collected by the protagonist
- goals lost to competition
- catastrophic failures
- blocked and partial executions
- intervention frequency
- trace action match rate
- mean and maximum trace-position deviation
- recovery debt

## Initial findings

The first corrected aggregate run over 100 scenarios showed **zero full-success episodes for all four controls under the current mixed regime**. This is not evidence that the architecture fails generally; it is evidence that this particular environment configuration is currently highly competitive and should be decomposed by perturbation family before any architectural conclusion is made.

`trace_change_aware` produced a substantially better mean reward than `trace_only` in the mixed run, while still achieving zero full success. This is a useful signal but is **not evidence of superiority** because the comparison has not yet been subjected to matched paired counterfactual analysis, parameter sweeps, confidence intervals, or ablations.

`trace_opportunistic` performed substantially worse in the current environment, which is already valuable: the simulator can expose strategically plausible overlays as harmful under the implemented world dynamics.

## Counterfactual facility

`counterfactual.py` can fork an exact latent world state at a specified step and run alternative architectures from the same branch point. This is the basis for paired comparisons and local causal analysis.

## Current epistemic status

### ESTABLISHED

- Reproducible scenario generation.
- Full ground truth is preserved independently of partial observation.
- Multiple perturbation families can be combined.
- Regime change alters actual environment dynamics rather than only emitting a flag.
- Counterfactual branching is implemented.
- Automated evaluation and aggregation run successfully.

### EXPERIMENTALLY_SUPPORTED

- The simulator's six tests pass.
- The current control agents exhibit measurably different behavior under the same scenario population.
- Opportunistic intervention can impose a large cost in the current environment configuration.

### UNKNOWN / OPEN

- Whether Trace + reactive middleware outperforms trace-only in a calibrated environment.
- Whether BOCPD improves the repair/replan decision.
- Whether multiple traces outperform one trace.
- Whether hierarchical traces reduce recovery cost.
- Whether learned arbitration outperforms hand-designed arbitration.
- Whether gains persist under unseen seeds, regimes, and opponent policies.

## Next experimental layer

Before expanding the architecture, the simulator should receive:

1. parameter sweeps for opponent strength, observability, perturbation magnitude, and regime severity;
2. paired counterfactual experiments at matched branch points;
3. trace-validity ground truth and an explicit repair-vs-replan oracle;
4. separate benign, local-disturbance, regime-shift, structural-shift, and adversarial benchmark suites;
5. uncertainty intervals and statistical comparison procedures.
