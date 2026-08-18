# Temporal Association Small v1

## Design
- 4 profiles; train seeds 0–3, held-out seeds 4–7 per profile.
- Window: event −3 through +8.
- Oracle: depth 3, beam 2; primary target is continuous causal Δ optimality gap.
- This avoids unstable binary detection labels when some profiles have few positives.

## Pooled signal association
- reward_residual: Pearson=-0.02260911477950741, Spearman=0.03293088687014912
- dynamics_residual: Pearson=-0.040474473009653664, Spearman=-0.011251480600506226
- trace_deviation: Pearson=-0.13971478929911618, Spearman=-0.2725291225293756
- objective_reachability: Pearson=0.039368933249042455, Spearman=0.07136399318709115

## Interpretation
- Continuous association is the primary result; binary detection is not trusted when positive counts are sparse.
- Any profile/time slice with near-zero outcome variance is treated as uninformative rather than scored as a failure.
- Oracle depth 3 remains an approximate evaluation target.