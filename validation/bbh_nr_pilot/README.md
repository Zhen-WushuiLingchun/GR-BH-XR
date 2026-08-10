# BBH Numerical-Relativity Pilot Gate

## Claim Boundary

The gate accepts `bounded_two_resolution_nr_pipeline_pilot`, not a converged
astrophysical BBH merger. It proves that a pinned Einstein Toolkit evolution can
produce the ADM volumes and diagnostics consumed by the GR-BH-XR ray tracer.
The accepted producer envelope is `0 <= t <= 1M`.  A longer `2M` exploratory
run developed non-finite geometry near `1.9M`; shortening the bounded plumbing
pilot is an explicit failed-configuration response, not a merger-stability
claim.

## Preregistered Checks

- pinned `ET_2026_05` manifest and full component revisions;
- linear-wave preflight passes before TwoPuncturesX is used;
- exactly two runs differ only in spatial resolution;
- Hamiltonian/momentum/Z4 constraint histories are present and the finer run
  must not show a larger late-time L2 norm outside a documented transient;
- both individual apparent horizons are found and their coordinate-center
  tracks remain finite.  The bounded fixed-box pilot intentionally does not
  use PunctureTracker as a producer gate: the puncture coordinate point can
  contain a non-finite shift on the coarse grid even while the two enclosing
  horizons and exterior fields remain regular;
- `Psi4` sample times and extraction radius agree with the producer log;
- the same camera is traced through frozen slices of both ADM datasets,
  preserving event and escape-direction differences rather than forcing them
  to match the approximate superposed metric; disk emission/transfer and a
  full dynamic light cone are outside this bounded pilot gate;
- all evidence files and parameter files are SHA-256 pinned.

The producer linear-wave log is a mandatory top-level manifest artifact.  A
README statement or a previously observed terminal summary cannot substitute
for that hashed log.

If any required evidence is absent, `export_manifest.py` fails closed. A
waveform-only file cannot satisfy the ADM role.

## Commands

```powershell
$env:PYTHONPATH='src'
python nr/einstein_toolkit/export_manifest.py `
  --spec outputs/tier2/nr/pilot_spec.json `
  --out outputs/tier2/nr/pilot_manifest.json
python -m pytest -q tests/test_nr_pilot_manifest.py tests/test_nr_snapshot.py
```

## Accepted 2026-08-10 Pilot

The pinned `ET_2026_05` optimized Release executable has SHA-256
`e02354d1c344d7e3470a57c0772a304056ddcb4b82e6543a66d93be45d723b60`.
The retained `linear_wave_z4c` preflight compared `36` files, reported `15`
last-digit-only tolerance differences, and reported `0` failures.

The two `0 <= t <= 1M` producer runs differ only by `$rho=1/2`.  Their final
global, puncture-unmasked L2 diagnostics were:

| resolution | Hamiltonian | momentum | Z4 |
|---|---:|---:|---:|
| low | `1.35153e-3` | `3.45595e-2` | `1.08793e-3` |
| high | `4.33590e-4` | `1.37615e-3` | `8.13649e-6` |
| high/low | `0.320814` | `0.0398197` | `0.00747885` |

Both runs found apparent horizons `1` and `2`; the low/high worst retained
expansion residuals were `2.01e-9` and `9.34e-9`.  Both emitted `25` finite
`Psi4` modes.  These diagnostics establish pipeline operation, not a converged
waveform.

The openPMD converter stores disconnected CarpetX chunks as independent schema
patches.  The low/high snapshots contain `20/144` patches and every patch stores
`alpha`, `beta^i`, `gamma_ij`, and `K_ij` at `t=0,1M`; the finest spacings are
`0.03125M/0.015625M`.  Treating each source AMR level as one dense bounding box
was rejected because it would fill real gaps between distributed chunks.

The formal `7x7`, two-time frozen-slice ray gate uses f64 fixed-step RK4 with
`h=0.05M`.  It resolved all `98` low/high pairs, produced no invalid or budget
events, and obtained event agreement `1.0`.  Across `88` escaped pairs, the
direction error median/RMS/max was
`3.334e-3/1.548e-2/1.184e-1 rad`.  The long tail is retained rather than hidden;
this coarse one-orbit plumbing pilot is not a production optical asset.  The
low/high worst Hamiltonian residuals were `7.37e-3/5.02e-3`.

A `3x3` sensitivity run at `h=0.025M` kept event agreement `1.0` and changed the
direction median/RMS from `3.203e-3/5.206e-3` to
`3.237e-3/5.226e-3 rad`, while reducing the Hamiltonian residual.  Thus the
reported two-resolution direction difference is not set by the selected RK4
step.  DOP853 at `rtol=1e-8` was also attempted, but resolving derivative kinks
of the trilinear ADM interpolant exceeded `3600 s` without producing an
artifact; it is recorded as a rejected execution strategy, not a physics gate.

The accepted generated manifest is
`outputs/tier2/nr/evidence_v4/pilot_manifest_v4.json` and remains ignored along
with the large HDF5/BP5 evidence.  Synthetic schema tests are not NR evidence.
