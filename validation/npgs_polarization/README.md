# NPGS Polarization Geometry Gate

Status: **camera basis and Walker-Penrose geometric transport passed on
2026-08-06; emission and polarized radiative transfer remain open**.

## Scope

This gate reuses NPGS as the production renderer and adds only the independent
evidence needed to prevent its polarization shader from validating itself.
Native raw schema v3 records the two camera-screen polarization covectors,
their Gram diagnostics, and their Walker-Penrose values. The f64 oracle then
integrates Li et al. Eq. 2.5 directly,

```text
df^mu/dlambda = -Gamma^mu_(nu rho) k^nu f^rho,
```

along the same serialized Kerr-Newman ray. The full reference scalar is
evaluated as `K=(A-iB)(r-i a cos(theta))` after an explicit Cartesian
Kerr-Schild to Boyer-Lindquist vector transformation.

The historical short Cartesian expression is retained only as a negative
control. It is not conserved: the formal sample has median/max relative drift
`4.86e-3 / 3.24e-1`. The replacement complete expression has maximum relative
drift `3.61e-8` under direct f64 parallel transport.

## Commands

```powershell
$env:PYTHONPATH='src'
.\tools\npgs\build.ps1 -Configuration Release -SkipDependencyInstall
.\tools\npgs\audit.ps1 `
  -Width 33 -Height 33 `
  -Out outputs/npgs/polarization_kn_a08_q03_i60_33_q2.bin `
  -Spin 0.8 -Charge 0.3 -InclinationDeg 60 `
  -RObsM 100 -FovDeg 40 -Quality 2
python -m gr_bh_xr.validate_npgs_polarization `
  --raw outputs/npgs/polarization_kn_a08_q03_i60_33_q2.bin `
  --samples 16 `
  --out outputs/npgs/polarization_kn_a08_q03_i60_33_q2.json `
  --h5 outputs/npgs/polarization_kn_a08_q03_i60_33_q2.h5
```

`tools/npgs/build.ps1` compiles GLSL before MSBuild. This is mandatory because
NPGS loads checked-in SPIR-V; compiling C++ alone can otherwise run a stale
physics shader. The compiler hash includes recursive `#include` contents, not
only entry-point source text or filesystem timestamps.

## Acceptance And Result

- all camera bases valid;
- basis norm and mutual-orthogonality error each `<5e-6`;
- native f32 versus independent f64 Walker-Penrose relative error median
  `<5e-6`, max `<1e-4`;
- direct-transport Walker-Penrose relative drift max `<1e-7`;
- transported basis norm and transversality drift max `<1e-8`;
- every selected native escape ray also escapes in the f64 oracle.

The formal 16-ray gate measured:

- 1089/1089 valid native camera bases;
- basis norm max error `2.3842e-7` and orthogonality max error `5.1201e-8`;
- 2178 native/reference scalar comparisons with median/p99/max relative error
  `1.4590e-7 / 1.0529e-6 / 6.8222e-6`;
- 16/16 f64 escapes, `abs(H)` max `1.1703e-10`;
- norm drift `2.5584e-10`, transversality `5.5037e-11`, and complete
  Walker-Penrose relative drift `3.6055e-8`.

## Claim Boundary

This result accepts geometric polarization transport for neutral rays in the
tested sub-extremal exterior Kerr-Newman configuration. It does **not** accept
NPGS's toroidal/radial magnetic-field proxy, polarized emissivity, absorption,
Faraday rotation/conversion, Stokes image normalization, Cauchy-horizon
continuation, or a comparison with ipole/RAPTOR II. Those require separate
polarized-GRRT gates.

Primary references are `li2026kerrNewmanPolarizedTransfer` for direct parallel
transport and the indexed ipole/RAPTOR II papers for later Stokes-transfer
validation.
