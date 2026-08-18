# Meta-Environment Observer Audit v1

## Purpose
This artifact audits not only experiment results but the correctness of our experimental responses: question definition, causal alignment, oracle validity, class support, leakage, and interpretation discipline.

## Global finding
Our strongest recurring failure mode was not implementation failure; it was **asking a measurement to answer a question it could not see**. Examples: one-step oracle for delayed effects, pooled metrics for heterogeneous profiles, and binary detection labels with too few positives.

## Experiment audit
### v0.3 stress / causal fork
- status: **EXPERIMENTALLY_SUPPORTED_LIMITED**
- decision: **do not claim architecture superiority**
- confidence: **medium**
- hidden confounds: event timing initially misaligned, observability had not yet been causal, magnitude initially partly nominal
- corrections: event-aligned forks, causal observability, parameter validity checks
- notes: Useful world stress test; not yet a definitive architecture comparison.

### v0.4 oracle / validity
- status: **EXPERIMENTALLY_SUPPORTED_LIMITED**
- decision: **use causal validity rather than raw invalidity**
- confidence: **medium**
- hidden confounds: absolute invalidity can precede perturbation, one-step oracle misses delayed effects
- corrections: matched clean-vs-perturbed worlds, rollout oracle
- notes: Oracle became an explicit research object.

### v0.5 validity curves
- status: **EXPERIMENTALLY_SUPPORTED_LIMITED**
- decision: **do not equate validity with global optimality**
- confidence: **medium**
- hidden confounds: structural/adversarial effects initially too weak
- corrections: stronger perturbations, horizon-dependent validity
- notes: Horizon dependence established in this simulator.

### v0.6 BOCPD
- status: **CONTRADICTED_SIMPLE_HYPOTHESIS**
- decision: **do not connect BOCPD to control yet**
- confidence: **high**
- hidden confounds: predictive branch bug made change probability collapse to hazard, single scalar signal insufficient
- corrections: prior-predictive change branch, feature ablation
- notes: The negative result is one of the stronger methodological findings.

### v0.7 belief + BOCPD
- status: **CONTRADICTED_SIMPLE_HYPOTHESIS**
- decision: **build richer state representation**
- confidence: **high**
- hidden confounds: current observable feature set insufficient, high false-alarm rates
- corrections: explicit belief layer
- notes: Combining shallow features did not solve detection.

### v0.8 dynamics
- status: **EXPERIMENTALLY_SUPPORTED_LIMITED**
- decision: **use dynamics as fast signal candidate only**
- confidence: **medium**
- hidden confounds: structural scenario weak, instantaneous residuals can be transient
- corrections: stronger structural event, persistent residuals
- notes: Profile-dependent signal heterogeneity became explicit.

### v0.9 reachability
- status: **PRELIMINARY_SUPPORT**
- decision: **do not call reachability calibrated/general yet**
- confidence: **medium-low**
- hidden confounds: clean objective could already be lost, regime has few eligible windows, accuracy could be imbalanced
- corrections: objective conditioning, Brier/calibration over accuracy
- notes: Promising but still setup-dependent.

### signal selection event-point v1
- status: **PRELIMINARY_SUPPORT**
- decision: **dynamics residual is a candidate, not final signal**
- confidence: **medium-low**
- hidden confounds: pooled target imbalance, profile dominance, shallow rollout approximation
- corrections: explicit limitations, per-profile follow-up requirement
- notes: Best single event-point discriminator in the tested pooled setup.

### temporal confirmatory v1
- status: **INCONCLUSIVE**
- decision: **no detector ranking claim**
- confidence: **low**
- hidden confounds: held-out local had zero positives, structural had near-zero positives, run timed out before completion
- corrections: switched to continuous temporal association on a reduced sample
- notes: The binary temporal protocol is underpowered for several profiles.

### temporal association small v1
- status: **INCONCLUSIVE**
- decision: **do not select a final signal from pooled correlation**
- confidence: **low**
- hidden confounds: very small per-profile n=4, pooled associations near zero due heterogeneity/sign cancellation
- corrections: continuous delta-gap target, profile/time slice inspection
- notes: This run is diagnostic, not confirmatory.

## Permanent future rules
- Never trust pooled metrics when profile heterogeneity is plausible; require per-profile results.
- Before running a large experiment, validate that the label has sufficient support in every intended evaluation slice.
- Treat the oracle as a model with assumptions; test oracle sensitivity to horizon/beam and report it.
- Keep latent truth strictly out of online features and detector inputs; audit leakage explicitly.
- Verify every parameter is causal before sweeping it; nominal knobs are prohibited from supporting claims.
- Separate event onset, delayed consequence, and task-level invalidity; do not use one label for all three.
- Use paired counterfactuals whenever comparing perturbation effects.
- Require train/test separation whenever a learned threshold, calibration model, or predictor is fitted.
- Report class prevalence and minimum positive/negative counts before AUROC/AUPRC claims.
- Do not use accuracy as primary evidence under imbalance; include Brier/ECE and prevalence-aware metrics.
- When an experiment times out, treat it as a harness finding, not as missing data to silently discard.
- Every new architecture claim must state whether it is implementation-correctness, empirical performance, or generalization.
- Maintain a hypothesis ledger: successful tests do not upgrade an open hypothesis unless a discriminating comparison was completed.
- Add a pre-flight audit before each expensive sweep and a post-run meta-audit before interpretation.

## Admission gates
### architecture_change_requires
- causal evidence or strong comparative evidence
- reproducible test
- no unresolved leakage/confound

### detector_admission_requires
- signal is available online
- held-out evaluation
- per-profile stability
- timing measured
- false alarms measured

### controller_admission_requires
- detector validated
- action effect validated
- paired counterfactual comparison against baseline
- safety/constraint checks

## Current research-state decision
- **Do not select a final controller signal yet.**
- Keep `dynamics_residual` as a candidate fast anomaly signal, not a validated detector.
- Keep `objective_reachability` as a candidate task-level signal, not a validated validity probability.
- Require a balanced, per-profile temporal study before connecting any signal to continue/repair/switch/replan.
- The simulator/harness itself is now a first-class research object and must be audited before expensive sweeps.