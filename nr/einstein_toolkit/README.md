# Einstein Toolkit BBH Pilot

This directory defines a bounded, two-resolution numerical-relativity pipeline
pilot. It does not claim a production-quality merger waveform or an event
horizon. Runtime capture surfaces remain apparent horizons or documented
worldtubes.

## Pinned Producer

- Einstein Toolkit `ET_2026_05` (Hypatia, released 2026-07-10);
- release manifest commit and selected component commits are frozen in
  `release_lock.json`;
- the downloaded thorn list and `GetComponents` script are identified by
  SHA-256 so a later branch movement cannot silently change this pilot;
- evolution: `CottonmouthZ4c4m` on `CarpetX`;
- initial data: equal-mass, nonspinning `TwoPuncturesX` Bowen-York data;
- gauge: Cottonmouth moving-puncture defaults with `eta_beta=1/M`;
- units: geometric `G=c=M_total=1`.

The official release checkout is:

```bash
curl -fLO https://raw.githubusercontent.com/gridaphobe/CRL/ET_2026_05/GetComponents
chmod +x GetComponents
./GetComponents --shallow \
  https://bitbucket.org/einsteintoolkit/manifest/raw/ET_2026_05/einsteintoolkit.th
```

Before using any run for a claim, verify the two downloaded file hashes and the
component commits against `release_lock.json`.

The pinned checkout needs six small compatibility/audit patches. Their hashes
are part of the same lock, and the idempotent patch driver refuses a changed or
partly applicable patch set:

```bash
python3 /path/to/GR-BH-XR/nr/einstein_toolkit/apply_release_patches.py \
  --cactus-root /path/to/Cactus --check-only
python3 /path/to/GR-BH-XR/nr/einstein_toolkit/apply_release_patches.py \
  --cactus-root /path/to/Cactus
```

The tracked `optionlists/hypatia-release.cfg` is the optimized evidence build
(`-O3 -DNDEBUG`), not a debug executable. The release build must still retain
explicit runtime validation for interpolation requests; assertions compiled out
by `NDEBUG` are not accepted as interface checks. On the current Ubuntu 22.04
WSL host, ADIOS2 additionally needs a local linker alias from `libudev.so` to
the system `libudev.so.1`; this is a host bootstrap detail, not a vendored
library.

## Qualification Order

1. Build the pinned source tree.
2. Run the packaged `CottonmouthLinearWaveID`/`CottonmouthZ4c4m` linear-wave
   test. The observed release preflight is compared against the thorn's stored
   reference output and must report zero failures before BBH evidence is used.
3. Materialize two copies of `par/bbh_equal_mass.par`, changing only `$rho`
   from `1` to `2`.
4. Run both short pilots and retain Cactus stdout, ADM openPMD/HDF5 fields,
   constraint norms, apparent-horizon diagnostics, `Psi4` multipoles, and a
   GR-BH-XR ray summary for the same camera.  The accepted pilot ends at
   `1M`; an exploratory `2M` producer run became non-finite near `1.9M` and is
   retained only as rejected configuration evidence.
5. Create a spec JSON and pass it to `export_manifest.py`. The manifest is
   accepted only when the retained linear-wave preflight log passes and both
   resolutions contain all six evidence roles.

Materialize the preregistered pair with the checked helper so the two files can
differ only in the `$rho` assignment:

```powershell
python nr/einstein_toolkit/prepare_pilot.py `
  --template nr/einstein_toolkit/par/bbh_equal_mass.par `
  --out-dir outputs/tier2/nr/pilot_inputs
```

Generated parameter files and run products belong under ignored `outputs/`,
not in Git.

`convert_openpmd_adm.py` preserves every disconnected openPMD chunk as a
separate audited ADM patch.  It requires all ADM components on a source level
to have identical chunk geometry, requires that geometry to match across the
two selected times, and chooses a parent from the nearest coarser source level
whose patch contains the child center.  It never fills a sparse chunk union
with invented samples.

## Required Evidence

Each manifest run must name:

- `cactus_stdout`: complete producer log, including resolved parameters;
- `adm_snapshot`: lapse, contravariant shift, spatial metric, and extrinsic
  curvature volume output;
- `constraints`: Hamiltonian, momentum, and Z4 constraint norm history;
- `apparent_horizons`: two independent finder solutions and their coordinate
  centers.  PunctureTracker is not a producer requirement for the fixed-box
  pilot because the puncture coordinate point is not a regular exterior-field
  sample;
- `psi4`: producer multipole output, including extraction radius and time;
- `ray_summary`: GR-BH-XR event/direction/transfer comparison for one fixed
  camera.

The spec must additionally name `producer_preflight`, the raw retained output
of `CottonmouthZ4c4m/linear_wave_z4c`.  The manifest parser requires a positive
file-comparison count, the named test in the passed-test list, and zero failed
tests.

The two-resolution pilot is a pipeline and convergence gate. A full-NR merger
claim additionally requires a physically adequate domain, wave-zone
resolution, multiple extraction radii, converged merger/ringdown, mass/angular-
momentum balance, and independent horizon diagnostics. This bounded pilot does
not satisfy those production conditions.
