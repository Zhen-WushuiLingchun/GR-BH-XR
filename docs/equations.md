# Equations And Conventions

This file records equations and conventions that implementation work must keep
traceable.

## Primary Sources

Each equation block below cites the primary analytic source it follows. BibTeX
keys resolve in `references/references.bib`; provenance notes are in
`references/source_notes/2026-06-29-foundational-analytic-references.md`.

- Kerr null geodesics and `(alpha, beta)` screen mapping: `bardeen1973kerrGeodesics`,
  `gralla2020nullGeodesicsKerr`.
- Carter constant and separability: `carter1968kerr`.
- ISCO and locally nonrotating frame: `bardeen1972rotatingBlackHoles`.
- Disk redshift / transfer function: `cunningham1975kerrDiskSpectrum`.
- Relativistic thin-disk flux profile: `page1974diskAccretionStructure`.
- Direct / secondary disk images: `luminet1979blackHoleImage`.
- Shadow / lensing ring / photon ring and higher-order image scaling:
  `gralla2019shadowsPhotonRings`, `gralla2020lensingKerr`.
- Blackbody color matching approximation: `wyman2013cieMatchingFits`.
- Horizon-penetrating Kerr geodesic motivation and future cross-checks:
  `bakun2024kerrHorizonPenetrating`.
- Simplified and polarized GRRT: `younsi2012grrt`, `bronzwaer2018raptor`,
  `bronzwaer2020raptorii`.

## Coordinate And Unit Conventions

Default conventions until superseded by a more detailed derivation:

- Geometric units: `G = c = 1`.
- Black-hole mass scale: `M = 1` in code-level validation unless documented
  otherwise.
- Observer screen coordinates: `(alpha, beta)`.
- Initial implementation target: Schwarzschild `a = 0`, then Kerr
  `0 < abs(a) < M`.
- Engineering coordinates near the horizon should prefer Kerr-Schild behavior;
  Boyer-Lindquist quantities may still be used for analytic checks and Carter
  constant validation.

## Null Geodesic Hamiltonian

Use a Hamiltonian form for ray integration:

```text
H(x, p) = 1/2 g^{mu nu}(x) p_mu p_nu = 0
```

Evolution:

```text
dx^mu / dlambda = partial H / partial p_mu
dp_mu / dlambda = - partial H / partial x^mu
```

The Phase 1 CPU reference solver evaluates `partial_r g^{mu nu}` and
`partial_theta g^{mu nu}` analytically for the Boyer-Lindquist inverse metric.
Finite differences are retained only as a derivative test oracle.

The Tier 2 near-horizon track uses Cartesian Kerr-Schild primitives as the
coordinate-regular foundation (`bakun2024kerrHorizonPenetrating` motivates the
horizon-penetrating geodesic target):

```text
g_{mu nu} = eta_{mu nu} + 2 H l_mu l_nu
g^{mu nu} = eta^{mu nu} - 2 H l^mu l^nu
H = M r^3 / (r^4 + a^2 z^2)
r^4 - (x^2 + y^2 + z^2 - a^2) r^2 - a^2 z^2 = 0
```

The implemented Cartesian spatial map follows the oblate spheroidal relation:

```text
x = (r cos phi - a sin phi) sin theta
y = (r sin phi + a cos phi) sin theta
z = r cos theta
```

`src/gr_bh_xr/metric_ks.py` currently validates the metric, inverse metric,
analytic Cartesian derivatives, Schwarzschild limit, and finite behavior at the
outer horizon. `src/gr_bh_xr/geodesic_ks.py` adds the first Hamiltonian tracer
seed and BL-to-KS canonical-state transform. It is still not a near-horizon
roaming solver; disk events, Carter-constant diagnostics, critical-curve
regression, observer worldlines, and transfer-map keyframes remain separate
Tier 2 gates.

Required tracked invariants (`Q` from `carter1968kerr`; screen mapping and
geodesic structure from `bardeen1973kerrGeodesics` and
`gralla2020nullGeodesicsKerr`):

```text
g^{mu nu} p_mu p_nu = 0
E = -p_t
L_z = p_phi
Q = Carter constant
```

Schwarzschild shadow validation:

```text
b_c = 3 sqrt(3) M
```

## Finite-Radius Observer Frames

The first Stage B observer-frame target is the Boyer-Lindquist ZAMO / LNRF
(`bardeen1972rotatingBlackHoles`) in the exterior domain. For the stationary
axisymmetric Kerr metric,

```text
omega = -g_tphi / g_phiphi
u_ZAMO^mu = alpha^-1 (1, 0, 0, omega)
alpha = sqrt(g_tphi^2 - g_tt g_phiphi) / sqrt(g_phiphi)
```

Equivalently, in standard Kerr notation,

```text
A = (r^2 + a^2)^2 - a^2 Delta sin^2(theta)
omega = 2 M a r / A
alpha = sqrt(Sigma Delta / A)
```

The spatial triad used for the current exterior BL check is

```text
e_r^mu     = (0, 1 / sqrt(g_rr), 0, 0)
e_theta^mu = (0, 0, 1 / sqrt(g_thetatheta), 0)
e_phi^mu   = (0, 0, 0, 1 / sqrt(g_phiphi))
```

with `g_mu nu e_(a)^mu e_(b)^nu = eta_(a)(b)`.  Static-observer frames remain
available only where `g_tt < 0`; inside the ergoregion the static tetrad is
not physical while the ZAMO frame remains valid outside the horizon.

Near the outer horizon, the ZAMO probe is recorded as a coordinate-domain
check rather than a formal pass/fail horizon gate:

```text
omega -> Omega_H = a / (2 M r_+)
alpha proportional to sqrt(r - r_+)
```

The BL tetrad may be pushed into ingoing Cartesian Kerr-Schild coordinates by
the exterior Jacobian `partial x_KS^mu / partial x_BL^nu`; the pushed tetrad is
used only as a chart-transformed observer basis. A transported worldline tetrad
and any claim inside the BL horizon remain separate Stage B work.

## Thin Disk Surface Transfer

Initial optically thick thin-disk surface (`r_ISCO(a)` from
`bardeen1972rotatingBlackHoles`; redshift/transfer function from
`cunningham1975kerrDiskSpectrum`; direct/secondary image structure from
`luminet1979blackHoleImage`):

```text
theta = pi / 2
r_in = r_ISCO(a)
r_out = R_out
```

For each screen coordinate and disk-crossing/image order:

```text
T_m(alpha, beta) = (r_m, phi_m, g_m, Delta t_m, n_m)
```

Keplerian disk angular velocity:

```text
Omega_pm = +/- 1 / (r^(3/2) +/- a)
u_em^mu = u^t (1, 0, 0, Omega)
```

Redshift factor:

```text
g = (u^mu p_mu)_obs / (u^mu p_mu)_em
```

Observed intensity:

```text
I_nu_o(alpha, beta, t_o)
  = sum_m g_m^3 I_nu_e(r_m, phi_m, t_o - Delta t_m, nu_o / g_m)
```

Bolometric approximation:

```text
I_o approx sum_m g_m^4 I_e
```

The first physically stronger disk color seed uses a Page-Thorne-style
zero-torque flux shape before it replaces the Unity power-law visual proxy
(`page1974diskAccretionStructure`):

```text
F(r) proportional to -Omega_,r / (E - Omega L_z)^2
                  * integral from r_in to r of (E - Omega L_z) L_z,r dr
r_in = r_ISCO
F(r <= r_in) = 0
T_eff(r) proportional to F(r)^(1/4)
```

For nonzero Kerr spin, the CPU validation layer also implements the equivalent
Page-Thorne root/log closed form in `x = sqrt(r/M)` using the three roots of
`x^3 - 3 x + 2 a = 0`; this is the analytic gate for the numerical radial
integral.

The current CPU helper stores only the dimensionless shape: the accretion-rate,
mass-to-SI scaling, and overall luminosity normalization remain display-asset
parameters rather than validation constants.

Observed blackbody color follows the invariant-intensity redshift convention:

```text
T_obs = g T_emit
I_nu_o = g^3 I_nu_e(nu_o / g)
```

CPU asset generation approximates the CIE 1931 2-degree color matching curves
with the analytic Wyman-Sloan-Shirley fits (`wyman2013cieMatchingFits`), then
maps the integrated XYZ chromaticity to max-normalized linear sRGB. This is a
color-LUT seed; it is not yet a full calibrated radiometric renderer. The LUT
stores color/chromaticity, while brightness remains a separate physical channel:

```text
specific intensity weight: g^3
bolometric blackbody weight: g^4
display brightness proxy: F(r) times selected g^p weight
```

## Simplified GRRT

Invariant intensity:

```text
Ical_nu = I_nu / nu^3
```

Scalar transfer equation for the first GRRT stage:

```text
dIcal_nu / dlambda = Jcal_nu - Acal_nu Ical_nu
```

Initial emission/absorption models may use analytic RIAF or torus fields:

```text
j_nu = j_nu(rho, T_e, B, nu)
alpha_nu = alpha_nu(rho, T_e, B, nu)
```

Polarization is deferred until scalar intensity is validated:

```text
S = (I, Q, U, V)^T
```

## Time-Dependent BBH Later Track

For later time-dependent metrics, use a documented 3+1 form:

```text
ds^2 = -alpha^2 dt^2
       + gamma_ij (dx^i + beta^i dt)(dx^j + beta^j dt)
```

The null condition can be expressed as:

```text
p_t = beta^i p_i - alpha sqrt(gamma^{ij} p_i p_j)
```

The sign convention and Hamiltonian choice must be re-derived before this track
is implemented.
