# BBH Time-Indexed Transfer Keyframe Gate

## Scope

This gate turns independently accepted full-sky transfer frames into a
content-addressed time sequence for the selected BBH PCVR runtime.  It does not
generate the frames, solve the Einstein equations, or upgrade an approximate
metric to numerical relativity.  The first supported frame payload is
`gr-bh-xr.task5.full_sky_transfer_cubemap.v3` because it has fractional escape
coverage and coverage-premultiplied disk orders.

Static `gr-bh-xr.task7.roam_keyframes.v2` grids are intentionally rejected.
They index independent stationary observers in `(log r, theta)` and are not a
time-dependent spacetime sequence.

## Source Specification

The source JSON uses schema
`gr-bh-xr.bbh.time-indexed-transfer.source.v1`:

```json
{
  "schema": "gr-bh-xr.bbh.time-indexed-transfer.source.v1",
  "metricSource": {
    "providerSchema": "gr-bh-xr.bbh.adm-snapshot.v1",
    "evidenceLabel": "numerical_relativity",
    "sourceRevision": "producer-commit-or-dataset-id"
  },
  "coverage": {
    "expectedStartMetricTimeM": 0.0,
    "expectedEndMetricTimeM": 1000.0,
    "maxGapM": 1.0
  },
  "requiredBufferRoles": [
    "event",
    "escape_direction",
    "disk_order0_transfer",
    "disk_order0_redshift",
    "disk_order1_transfer",
    "disk_order1_redshift"
  ],
  "sequenceGateEvidence": "sequence_gate.json",
  "frames": [
    {
      "metricTimeM": 0.0,
      "directory": "frames/000000",
      "gateEvidence": "frame_gates/000000.json"
    },
    {
      "metricTimeM": 1.0,
      "directory": "frames/000001",
      "gateEvidence": "frame_gates/000001.json"
    }
  ]
}
```

Each frame gate has schema `gr-bh-xr.validation.transfer-frame.v1`; the
sequence gate has schema `gr-bh-xr.validation.transfer-sequence.v1`.  Both must
contain `"passed": true`.  The builder hashes the source specification, every
frame metadata file, every referenced raw buffer, and all gate evidence with
SHA-256.

Build and revalidate with:

```powershell
$env:PYTHONPATH='src'
python -m gr_bh_xr.transfer_keyframes `
  --spec outputs/task11/bbh_sequence_source.json `
  --out outputs/task11/bbh_transfer_keyframes.json
```

`--allow-incomplete` writes an auditable manifest with
`runtimeAssetReady=false`; without it the CLI exits nonzero.  Generated assets
remain under ignored `outputs/`.

## Interpolation Contract

- Metric times are finite and strictly increasing.  Playback outside the
  accepted interval fails; it never extrapolates.
- Event and failure codes are discrete.  A capture/escape or valid/invalid
  transition is not blended into a fabricated class.
- Escape directions use normalized linear interpolation only when both source
  samples are valid escapes.  Degenerate and nearly antipodal pairs fail.
- A disk order is interpolated only when that same true equatorial crossing
  order is valid in both frames.  Coverage is unpremultiplied before
  interpolating `r_m` and `g_m`; `(sin(phi_m), cos(phi_m))` is interpolated on
  the unit circle; the result is premultiplied again.
- Temporal interpolation does not certify that the frame cadence resolves the
  photon-ring or a rapidly changing apparent horizon.  `maxGapM` and the
  independent sequence gate carry that responsibility.

## Acceptance

`runtimeAssetReady=true` requires:

1. at least two layout-compatible v3 frames;
2. exact buffer byte counts and stable SHA-256 digests;
3. complete declared time endpoints and no gap above `maxGapM`;
4. passed independent evidence for every frame and the complete sequence;
5. no temporal extrapolation or cross-class interpolation.

The bounded `ET_2026_05` `0..1M` pilot remains pipeline evidence only.  It
does not yet satisfy a complete inspiral-merger-ringdown keyframe asset, so the
runtime-ready claim remains open until a production source specification and
its gates pass this contract.
