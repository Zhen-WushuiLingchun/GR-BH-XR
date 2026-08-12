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

## Native NPGS Preflight

NPGS repeats the security- and runtime-critical subset of this validation before
any frame is eligible for Vulkan upload.  The native loader checks the manifest
schema, `runtimeAssetReady`, source provenance, independent gate schemas and
pass state, cubemap layout, strict time coverage, exact byte counts, and every
SHA-256 digest.  Python remains the schema authority and additionally rebuilds
the buffer inventory from each v3 metadata file; the native check is a second
fail-closed boundary, not an independent physics certification.

From the NPGS data-root working directory (`runtime/NPGS/NPGS` in a source
checkout), run:

```powershell
NPGS.exe --validate-transfer-keyframes <manifest.json>
```

The 2026-08-12 Release smoke used a two-frame synthetic v3 fixture.  It selected
the midpoint bracket `(left=0, right=1, alpha=0.5)` and exited `0`.  Flipping one
byte in the first event buffer made the same executable exit `3` with
`frame buffer event SHA-256 changed`.  The fixture proves native contract
enforcement only; it is not a production BBH transfer sequence.

NPGS currently performs pre-main data initialization, so validation commands
must use the NPGS data root as their working directory.  Launching from an
arbitrary directory can fail before command-line dispatch because unrelated
stellar catalog assets are then unresolved.

## Native Vulkan Residency And Interpolation

The NPGS integration now consumes an accepted manifest through a bounded
two-frame Vulkan resident set. Each physical slot contains the six required
v3 cubemaps. The event texture is point sampled; continuous physical buffers
use their declared float formats and linear spatial sampling. A bracket change
waits for in-flight GPU work before replacing an image and rewriting the A/B
descriptors, so no submitted frame can sample a destroyed resource. This is a
correctness-first double buffer; asynchronous uploads are not yet claimed.

Temporal interpolation occurs per texel in dedicated transfer shader variants,
before visual shading. It uses the same fail-closed event, normalized escape
direction, coverage-unpremultiplied disk, circular azimuth, and same-order
rules specified above. A metric-time request outside the accepted sequence
exits with an error rather than clamping or extrapolating.

Build the deterministic fixture and run the Release smoke with:

```powershell
$env:PYTHONPATH='src'
python validation/bbh_transfer_keyframes/scripts/build_native_playback_fixture.py `
  --out-dir outputs/task11/native_playback_fixture

cd runtime/NPGS/NPGS
NPGS.exe --windowed --width 64 --height 64 `
  --transfer-keyframes <absolute-path-to-manifest.json> `
  --transfer-time-M 0.5 --transfer-keyframe-smoke
```

The repository wrapper generates the fixture, checks all residency/swap
markers, and verifies out-of-range rejection in one command:

```powershell
pwsh -NoProfile -File `
  validation/bbh_transfer_keyframes/scripts/run_native_playback_smoke.ps1
```

The accepted 2026-08-12 smoke emitted:

```text
NPGS_TRANSFER_RESIDENT slot=0 frame=0 bytes=4992
NPGS_TRANSFER_RESIDENT slot=1 frame=1 bytes=4992
NPGS_TRANSFER_RESIDENT slot=0 frame=2 bytes=4992
NPGS_TRANSFER_PLAYBACK_OK left=1 right=2 alpha=0.5 resident_frames=2 resident_bytes=9984
```

The fixture is intentionally not a BBH result. It has three frames so the
smoke must replace slot 0 while retaining frame 1 (`0/1 -> 1/2`) without ever
holding more than two frames. Its first interval is a compact interpolation
probe with escape direction `+X -> +Y`, disk radius `6M -> 10M`, redshift
`0.8 -> 1.2`, coverage `0.5 -> 1.0`, and azimuth `+179 -> -179 deg`. That
midpoint must produce the normalized diagonal direction, `r=8M`, `g=1`,
coverage `0.75`, and an azimuth close to the `pi` branch rather than zero. The
smoke proves native upload/binding/render execution and slot replacement; the
Python contract supplies the exact midpoint value oracle. A production merger
sequence remains separate evidence.

### Exact Vulkan readback gate

The spatial probe fixture varies event class, escape direction, coverage,
disk radius, circular azimuth, and redshift over every face and texel. The
native fragment shader calls the same `TransferEvaluatePhysicalSample` used by
the visual path and writes its physical values to an SSBO. Run the complete
fixture/native/Python comparison with:

```powershell
pwsh -NoProfile -File `
  validation/bbh_transfer_keyframes/scripts/run_native_playback_probe.ps1
```

The accepted 8x8-per-face run produced 384 records. It had zero texel, event,
escape-validity, disk-validity, or non-finite mismatches; maximum escape
direction error was `7.5981e-8 rad`; maximum disk physical difference was
`1.0455e-6`. During development the probe found that invalid disk interpolation
returned before initializing its output, producing random values and one NaN.
The shared GLSL evaluator now zero-initializes invalid outputs, so visual and
audit paths retain the same deterministic fail-closed semantics.

### Real-size residency and swap benchmark

Run the current synchronous two-slot path at display-relevant cubemap sizes:

```powershell
$env:PYTHONPATH='src'
python validation/bbh_transfer_keyframes/scripts/benchmark_native_playback_residency.py `
  --out-dir outputs/task11/native_residency_benchmark `
  --face-sizes 256 512 1024 --iterations 3
```

The accepted RTX 5080 Laptop GPU result was:

| Face size | Frame bytes | Two-slot residency | Replacement upload p95 |
| ---: | ---: | ---: | ---: |
| 256 | 20,447,232 | 39 MiB | 33.34 ms |
| 512 | 81,788,928 | 156 MiB | 113.50 ms |
| 1024 | 327,155,712 | 624 MiB | 442.02 ms |

All byte counts, slot transitions, and final brackets matched their manifests,
but every replacement exceeded the 9/11 ms physics budgets for 90/72 Hz.
These timings measure synchronous resource creation/upload and are not render
GPU timestamps. They reject frame-loop replacement; production playback must
prefetch or asynchronously stage and fence-retire future frames.
