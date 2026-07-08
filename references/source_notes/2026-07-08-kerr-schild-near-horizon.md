# 2026-07-08 Kerr-Schild Near-Horizon Notes

## Search

- Search date: 2026-07-08
- Search terms:
  - `Kerr Geodesics horizon-penetrating Kerr coordinates`
  - `Kerr-Schild coordinates Kerr metric ingoing Cartesian H l_mu`

## Sources

### `bakun2024kerrHorizonPenetrating`

- Stable locator: https://arxiv.org/abs/2409.03722
- Added for: Stage A near-horizon solver planning.
- Project relevance: Documents why Boyer-Lindquist coordinates are ill-suited
  at horizons and gives a modern analytic treatment of Kerr geodesics in
  horizon-penetrating coordinates.
- Usage boundary: The current `metric_ks.py` module implements the Cartesian
  Kerr-Schild metric ansatz and derivative tests only. It does not yet implement
  the full horizon-crossing geodesic solver described in the Stage A plan.

## Engineering Notes

- Cartesian Kerr-Schild coordinates remove the Boyer-Lindquist horizon
  coordinate singularity and avoid the explicit polar-axis singular factors that
  complicated the earlier BL GPU prototype.
- Exterior-domain BL/Kerr validations remain authoritative until the
  Kerr-Schild tracer has its own CPU-vs-BL and critical-curve gates.
