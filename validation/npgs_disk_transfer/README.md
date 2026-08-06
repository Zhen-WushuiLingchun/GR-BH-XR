# NPGS Native Disk-Transfer Gate

This gate checks the disk records emitted by the native NPGS runtime against
the existing CPU f64 Kerr reference. NPGS remains the production renderer. The
Python code only replays sampled native launch states; it is not a second disk
renderer and does not reconstruct the native camera.

## Accepted Scope

The first gate is deliberately limited to:

- Kerr with `Q_charge=0`, `a/M=0.9`;
- a static observer at `r_obs=100M`, inclination `60 deg`;
- native quality `2`, a `65 x 65` audit framebuffer, and `40 deg` field of view;
- a circular neutral thin disk over `[r_ISCO, 30M]`;
- the first two true equatorial crossings, preserving crossing order even when
  a crossing falls outside the emitting annulus.

Each valid slot records `r_m`, `sin(phi_m)`, `cos(phi_m)`, `g_m`,
`Delta t_m`, true crossing order, validity, and failure flags. `phi_m` and
`Delta t_m` are Boyer-Lindquist quantities.

The native redshift is the finite-observer ratio

```text
g_m = nu_observer_local / nu_emitter
    = 1 / [u^t (E_native - Omega L_native)]
```

because the static camera tetrad normalizes the local launch frequency to one.
It must not be compared directly with the older asymptotic-observer helper
`E/[u^t(E-Omega L)]`.

## Reproducible Commands

Build the native fork, capture through the Unicode-safe wrapper, and replay the
native states:

```powershell
.\tools\npgs\build.ps1 -Configuration Release -SkipDependencyInstall
.\tools\npgs\audit.ps1 `
  -Width 65 -Height 65 `
  -Out outputs/npgs/audit_disk_kerr_a09_i60_65_q2.bin `
  -Spin 0.9 -Charge 0 -InclinationDeg 60 `
  -RObsM 100 -FovDeg 40 -Quality 2 `
  -DiskRInM 2.320883 -DiskROutM 30
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_npgs_disk_transfer `
  --raw outputs/npgs/audit_disk_kerr_a09_i60_65_q2.bin `
  --samples 257 `
  --out outputs/npgs/npgs_disk_transfer_kerr_a09_i60_q2.json `
  --h5 outputs/npgs/npgs_disk_transfer_kerr_a09_i60_q2.h5
```

NPGS currently accepts the audit output path through a narrow native string.
`audit.ps1` therefore writes to an ASCII-only local path, validates the raw
length and metadata sidecar, and only then copies both files to the requested
workspace path. This prevents a failed Unicode-path write from leaving stale
evidence behind.

## Acceptance And Evidence

The gate requires native quality at least `2`, zero CPU replay failures, zero
crossing-presence/validity/flag/order mismatch, and:

| Quantity | Threshold | Measured max | Measured RMS |
| --- | ---: | ---: | ---: |
| `r_m` | `< 0.03M` | `0.0199722M` | `0.0021690M` |
| `phi_m` | `< 5e-4 rad` | `3.4780e-4 rad` | `4.6696e-5 rad` |
| `Delta t_m` | `< 0.03M` | `0.0207713M` | `0.0021562M` |
| `g_m` | `< 5e-4` | `2.0221e-4` | `2.9652e-5` |

The formal replay selected 318 rays, including every native second crossing.
Native, CPU, and compared valid counts were all `[142, 41]` for `m=0/1`.

The first redshift comparison exposed an audit-layer error: reconstructing
`L_y` from separately interpolated crossing position and momentum does not
preserve that bilinear Killing invariant. The native shader now evaluates
`E` and `L_y` from the exact initial canonical state. This is a scientific
definition correction, not a tolerance relaxation.

NPGS dynamically switches ingoing/outgoing Kerr-Schild charts. The CPU replay
uses one ingoing chart, so past-directed captured camera rays become
cancellation-conditioned at the future-horizon boundary. The disk validator
stops those reference rays `0.01M` outside `r_+`; every compared disk crossing
occurs before that guard. The reported CPU `max|H|=2.95e-4` is therefore a
horizon-chart diagnostic, not disk-field error or horizon-penetration evidence.

## Open Gates

This result does not accept charged Kerr-Newman disk emitters, Page-Thorne
emissivity inside NPGS, Walker-Penrose polarization, jet/volume emission,
Cauchy-horizon continuation, or native OpenXR. Those remain separate gates.

