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
measured hit-band center = 0.011622782606623652 rad
relative error = 6.56e-3
event counts = object_hit 18, escape 63
```

This is a finite-size source-band check, not an exact point-source equality.
The gate verifies that the finite-distance KS sphere target converges to the
standard weak-field point-mass lens scale.
