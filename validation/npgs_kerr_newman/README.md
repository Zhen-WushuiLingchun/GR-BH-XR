# Native NPGS Kerr-Newman Gate

Status: **passed for neutral, sub-extremal exterior rays on 2026-08-06**.

This gate does not replace NPGS. NPGS remains the native renderer and emits
the exact raw-v2 canonical states consumed by its GLSL kernel. The Python f64
module is a deliberately small independent oracle used to prevent the native
shader from validating itself.

## Physics Scope

- signature `(-,+,+,+)`, geometric units `G=c=1`;
- neutral null geodesics in sub-extremal Kerr-Newman;
- Boyer-Lindquist metric from `li2026kerrNewmanPolarizedTransfer`, Eq. 2.1-2.2;
- ingoing Cartesian Kerr-Schild audit metric with
  `H=(M r^3-Q_charge^2 r^2/2)/(r^4+a^2 z^2)`;
- event class, escaped direction, and `H/E/L_z/Q_Carter` diagnostics.

It does not validate charged particles, Walker-Penrose polarization, disk/jet
emission, Cauchy-horizon continuation, or NPGS maximal-extension rendering.

## Commands

Run NPGS from `runtime/NPGS/NPGS` after a Release build:

```powershell
& ..\x64\Release\NPGS.exe --width 33 --height 33 `
  --audit-out "<repo>\outputs\npgs\audit_kn_a06_q05_i60_33_q2.bin" `
  --spin 0.6 --charge 0.5 --inclination-deg 60 --r-obs 100 `
  --fov-deg 16 --quality 2
```

Then run the independent replay from the repository root:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_npgs_kerr_newman `
  --raw outputs/npgs/audit_kn_a06_q05_i60_33_q2.bin `
  --samples 257 --critical-band-pixels 1 --horizon-eps-m 0.02 `
  --out outputs/npgs/npgs_kn_crosscheck_a06_q05_i60_257.json `
  --h5 outputs/npgs/npgs_kn_crosscheck_a06_q05_i60_257.h5
```

The Reissner-Nordstrom limit uses `--spin 0 --charge 0.6` and 129 replay
samples. Generated raw, JSON, and HDF5 evidence stays under ignored
`outputs/npgs/`.

## Acceptance

- native quality `>=2`;
- zero native failures outside the recorded critical boundary;
- zero CPU invalid events in that stable region;
- stable event agreement `>=0.98`;
- escaped-direction median `<1e-4 rad`;
- escaped-direction RMS `<5e-4 rad`;
- all raw errors and boundary masks remain persisted, including the maximum.

## Results

| Case | Native full grid | Replay | Stable agreement | Direction median/RMS/max |
| --- | --- | ---: | ---: | --- |
| `a/M=0.6, Q/M=0.5` | 101 capture, 988 escape, 0 invalid | 257 | 1.0 | `1.43e-5 / 2.99e-5 / 1.15e-4 rad` |
| `a=0, Q/M=0.6` | 97 capture, 992 escape, 0 invalid | 129 | 1.0 | `1.62e-5 / 4.07e-5 / 1.42e-4 rad` |

The generic KN escaped-ray CPU residual maxima were `abs(H)=2.08e-7` and
`Q_Carter` drift `3.72e-8`. The RN escaped residual maxima were
`abs(H)=1.96e-7` and `Q_Carter` drift `4.10e-9`.

## Capture-Surface Interpretation

NPGS ray tracing uses a negative affine step. Replaying the same camera ray
with positive affine parameter negates the covector, producing a past-directed
ray in the ingoing chart. Its canonical covector is cancellation-conditioned
at the future horizon. The CPU exterior gate therefore terminates at
`r_+ + 0.02M`; capture residuals are recorded separately and are not evidence
of horizon penetration. This is an event-classification convention, not a
change to the KN metric or the native renderer.
