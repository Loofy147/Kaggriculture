# Trace Research Simulator v0.7 — Multi-Channel Belief + BOCPD

## Purpose
Added an observation-only State/Belief layer in front of BOCPD. The layer derives levels, deltas, EMA and volatility from observable resources/opponents/blocked cells/execution feedback. Simulator truth and `regime_signal` are excluded.

## Verification
20/20 tests pass.

## Benchmark design
- Profiles: local, regime, structural, adversarial
- Seeds: 20/profile
- Detector: corrected Gaussian BOCPD
- Single-channel and simple fused-channel ablations

## Key findings
The belief representation is structurally cleaner, but the current feature set does **not** yet make BOCPD a reliable general-purpose detector. Simple fusion produced high false-alarm rates and weak detection: local 45% detection / 55% false alarms; regime 15% / 75%; structural 5% / 85%; adversarial 5% / 70%.

Single-channel ablation confirms that no current observable channel is sufficient across all profiles. Some channels detect local/structural events better, while regime and adversarial changes remain poorly represented under the neutral WAIT sensing protocol.

## Epistemic status
- ESTABLISHED: belief layer does not read simulator truth and preserves finite/resettable state.
- EXPERIMENTALLY_SUPPORTED: 20/20 tests; no single current observation channel is generally adequate.
- CONTRADICTED: the hypothesis that merely combining the current low-level observable channels will make BOCPD broadly reliable.
- OPEN: design a richer state representation that captures causal consequences of regime and adversarial changes without leaking hidden truth.

## Next discriminating experiment
Do not tune BOCPD yet. First expand the observation/state model with causal, agent-accessible quantities that differ under the relevant hypotheses (e.g. opportunity/reward forecasts, resource contention dynamics, opponent relative motion/acceleration, trace-prediction residuals), then repeat the same detector evaluation with pre-registered false-alarm/delay thresholds.
