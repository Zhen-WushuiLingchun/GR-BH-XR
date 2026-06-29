# Schwarzschild Shadow Validation

Phase: 1 CPU Kerr reference solver.

Purpose: verify that the Boyer-Lindquist exterior reference tracer recovers the
Schwarzschild critical impact parameter

```text
b_c = 3 sqrt(3) M
```

from `docs/equations.md` and `docs/validation_targets.md`.

## Command

```text
$env:PYTHONPATH='src'
python -m gr_bh_xr.validate_shadow --spin 0 --grid 129 --out outputs/phase1/schwarzschild_shadow.json
```

After installing the package, the same module can be run without setting
`PYTHONPATH`.

The generated JSON is intentionally written under `outputs/phase1/`, which is
ignored by Git. It records the expected and estimated critical impact parameter,
absolute/relative error, sample counts, and final capture/escape bracket.

Phase 1 uses a Boyer-Lindquist exterior reference solver. Capture is therefore
classified at `r <= r_+ + 0.3 M` by default, before the coordinate singularity
can dominate the Hamiltonian residual. A later Kerr-Schild solver may move this
boundary closer to or through the horizon.

## Acceptance

- Rays with `b < b_c` classify as `capture`.
- Rays with `b > b_c` classify as `escape`.
- The estimated `b_c` should be within `3e-2 M` for the default validation run.
- The implementation also records per-ray Hamiltonian, `E`, `L_z`, and Carter
  `Q` diagnostics; tighter tolerances may be added after the reference solver is
  stabilized.
