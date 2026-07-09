# Source Notes: Finite-Distance Weak-Field Lensing Anchor

Search/use date: 2026-07-08.

Purpose: add a standard weak-field lensing reference for the Task 3
finite-distance sphere-target gate. This note supports the validation formula

```text
theta_E^2 = 4 M D_LS / (D_L D_S),    D_S = D_L + D_LS
```

in geometric units (`G = c = 1`) for an aligned point-mass lens.

## Sources Checked

| Source | Locator | Use |
| --- | --- | --- |
| Schneider, Ehlers, Falco 1992, *Gravitational Lenses* | https://doi.org/10.1007/978-3-662-03758-4 | Standard monograph for lens equation, point-mass lens, and Einstein angle conventions. |
| NASA ADS entry for the monograph | https://ui.adsabs.harvard.edu/abs/1992grle.book.....S/abstract | Stable bibliographic locator / bibcode. |
| Springer book page | https://link.springer.com/book/10.1007/978-3-662-03758-4 | Confirms title, authors, publisher, DOI, and chapter structure including lens-equation derivation. |
| Keeton & Petters 2005, PRD 72, 104006 | https://doi.org/10.1103/PhysRevD.72.104006 | Second-order Schwarzschild bending term used to interpret the percent-level offset from the first-order Einstein angle. |

No PDF was added. The Springer book is copyrighted; personal copies belong in
`references/pdfs/local_only/` only.

## Project Use

- Task 3 uses the formula only as a weak-field limiting anchor.
- The formal numerical run uses a far-field configuration
  `D_L = 10000M`, `D_LS = 5000M` so the one-line thin-lens approximation is a
  percent-level check of the Kerr-Schild sphere-target event path.
- The nearer `D_L = 200M`, `D_LS = 100M` configuration is useful for finite
  object demos but is not weak enough for a strict first-order Einstein-angle
  pass/fail threshold.

## Current Numerical Anchor

Post-review update (2026-07-09): the first implementation relied on a direct
`|x-c|-R` event. With `max_step = 50M`, a ray could enter and exit the `10M`
diameter target within one DOP853 step, leaving both step endpoints outside
the sphere and silently missing the event. The CPU tracer now records the
closest-approach event, checks whether the closest point lies inside the
sphere, and bisects dense output back to the front surface. The WGSL comparison
path similarly checks the closest point on each RK4 segment.

Command:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_ks_finite_lens --out outputs/tier2/ks_finite_lens_weak_field.json
```

Result:

```text
D_L = 10000M
D_LS = 5000M
target radius = 5M
samples = 81
theta_E = 0.011547005383792516 rad
measured hit-band center = 0.011695993464709488 rad
relative offset from first-order theta_E = 1.290e-2
second-order Schwarzschild prediction = 0.011694267539429537 rad
relative residual vs second-order prediction = 1.49e-4
event counts = object_hit 33, escape 48
```

The leading correction follows the standard Schwarzschild expansion

```text
alpha_hat = 4M / b + 15 pi M^2 / (4 b^2)
theta ~= theta_E * (1 + 15 pi M / (32 b_E)),    b_E = D_L theta_E
```

so the percent-level first-order offset is physical, not a failure of the KS
tracer. A distance-scaled check at `D_L = 40000M`, `D_LS = 20000M` gives a
first-order offset `6.414e-3`, second-order prediction `6.377e-3`, and
second-order residual `3.73e-5`, matching the expected factor-of-two scaling.

This is a finite-size source-band check, not an exact point-source equality.
The gate verifies that the finite-distance KS sphere target converges to the
standard weak-field point-mass lens scale and that the observed leading
correction has the expected second-order Schwarzschild coefficient.
