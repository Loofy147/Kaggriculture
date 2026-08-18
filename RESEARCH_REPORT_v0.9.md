# Trace Research Simulator v0.9 — Trace Outcome & Objective Reachability

## Scope
This release adds two explicit predictive targets:

1. **Trace outcome prediction:** short-horizon progress/cost/reward under the reference action.
2. **Objective reachability prediction:** probability that a selected trace objective remains attainable within horizon H.

The simulator oracle is used only for evaluation labels. Online predictors see observation, feedback, and the selected objective target only.

## Components
- `OnlineTracePredictor`: simple online observation-only outcome predictor.
- `predict_reachability`: transparent geometric/probabilistic reachability baseline.
- `ReachabilityModel`: small offline supervised model over agent-visible features, evaluated on held-out seeds.
- `oracle_reachability`: full-information evaluation label; never exposed to the agent.
- `matched_target_evaluation`: clean-vs-perturbed evaluation around event windows, using the next objective still present in the clean reference world.

## Important correction
Earlier reachability evaluation sometimes used a trace target that was already lost in the clean world before the event. That conflated pre-existing baseline degradation with causal event impact. v0.9 conditions event-window evaluation on the next clean reference objective still remaining.

## Tests
13 prediction/oracle/dynamics/validity tests pass in the current regression suite slice.

## Initial findings
The transparent reachability heuristic is directionally useful but systematically underestimates longer-horizon attainability in several profiles. Its error grows with horizon, showing that geometric reachability is not enough to model opponent/resource dynamics.

An offline logistic reachability model trained on seeds 100–109 and evaluated on held-out seeds 110–119 gives promising classification metrics in the current toy world, but **accuracy is not sufficient evidence** because target attainability can be imbalanced. Brier skill and calibration are therefore tracked against a constant-probability baseline.

The adversarial profile is the hardest current held-out profile among those with adequate samples; this is consistent with the need for richer opponent dynamics. The regime profile has very few eligible evaluation windows after conditioning on a clean objective, so it is **not adequate for generalization claims** and needs a redesigned regime scenario or a different objective definition.

## Epistemic status
- EXPERIMENTALLY_SUPPORTED: explicit outcome/reachability targets can be computed without exposing simulator truth to the online predictor.
- EXPERIMENTALLY_SUPPORTED: objective conditioning removes an important source of causal confounding seen in v0.8.
- EXPERIMENTALLY_SUPPORTED: simple geometric reachability is insufficient for longer horizons.
- OPEN: whether learned reachability provides reliable calibrated probabilities under unseen regimes/perturbations.
- OPEN: whether reachability residuals outperform generic reward residuals as a change/validity signal.
- OPEN: robust definition of objective reachability under regime changes where the original objective itself may become obsolete.

## Next discriminating experiment
Use the reachability model only as a predictor, not a controller. Compare its held-out probability forecasts with reward-residual and trace-validity signals using paired clean-vs-perturbed windows. Separately redesign the regime profile so enough clean objectives survive until the regime transition, allowing a valid causal comparison.
