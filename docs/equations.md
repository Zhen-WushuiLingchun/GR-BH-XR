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
color-LUT seed; it is not yet a full calibrated radiometric renderer. The Unity
disk path can consume this table together with a radial Page-Thorne LUT. The
color LUT stores color/chromaticity, while brightness remains a separate
physical channel:

```text
specific intensity weight: g^3
bolometric blackbody weight: g^4
baseline Unity LUT path: normalized F(r) times g^4
temperature lookup: T_obs = g T_scale [F(r) / max(F)]^(1/4)
```

The absolute disk temperature scale and luminosity normalization are display
parameters until an accretion rate, mass-to-SI conversion, and distance model
are selected.

Note that `max(F)`, the normalization stored alongside the LUT as
`fluxPeakShape`, is itself **not** dimensionless: it carries geometric
dimension `length^-2` and scales as `M^-2` at fixed `r/M`. The omitted
`Mdot / (4 pi)` factor is dimensionless in `G = c = 1`, so dropping it cannot
remove that dimension. Only the stored channels `F(r) / max(F)` and
`[F(r) / max(F)]^(1/4)` are dimensionless.

### Inverse Planck locus (project chromaticity heuristic)

Applying a redshift to a broadband RGB source needs an emitter temperature.
The project derives one from the source pixel's own chromaticity using the
dimensionless coordinate

```text
u = R / (R + B)          (linear sRGB, scale invariant, not gamma invariant)
s = log(T / T_min) / log(T_max / T_min)      in [0, 1]
T = T_min (T_max / T_min)^s
```

`u` decreases monotonically along the Planck locus and is inverted to `s`,
which is stored in the alpha channel of the disk color LUT (schema
`gr-bh-xr.task6.disk_color_lut.v2`). The observed color is then
`rgb * LUT(T g) / LUT(T)`, which is an exact identity at `g = 1` in exact
arithmetic because the same table is used in both directions.

This is a **project chromaticity heuristic, not a literature-derived spectral
fit**, and must be labelled as a `physics approximation` per
`docs/physical_scope.md`. It ignores the green channel and minimizes no
residual, so for an off-locus pixel the recovered temperature has no
goodness-of-fit meaning. It is also information-limited on the cold side:
below roughly `1.9e3 K` the clipped linear-sRGB blue channel is exactly zero,
`u` saturates at `1`, and no temperature can be recovered. The inversion drops
that plateau and saturates at its hottest member, so the recovered temperature
never falls below the published `alphaAnchorTemperatureK`.

## Kerr-Newman Audit Geometry

The native migration audit uses neutral photons in a sub-extremal
Kerr-Newman spacetime. The independent f64 oracle follows Eq. (2.1)-(2.2) of
`li2026kerrNewmanPolarizedTransfer` in the same `(-,+,+,+)` signature and
geometric units as the Kerr reference:

```text
Sigma = r^2 + a^2 cos^2(theta)
Delta = r^2 - 2 M r + a^2 + Q_charge^2
r_+/- = M +/- sqrt(M^2 - a^2 - Q_charge^2)
```

The ingoing Cartesian Kerr-Schild audit form is

```text
g_mu_nu = eta_mu_nu + 2 H l_mu l_nu
H = (M r^3 - Q_charge^2 r^2 / 2) / (r^4 + a^2 z^2)
g^mu_nu = eta^mu_nu - 2 H l^mu l^nu
```

where `r(x,y,z)` obeys the same oblate-spheroidal quartic as Kerr. Charge
changes `H` and `Delta`, not that spatial coordinate map. For a neutral photon,
the Hamiltonian and separation diagnostics remain

```text
H_null = 1/2 g^mu_nu p_mu p_nu = 0
E = -p_t
L_z = x p_y - y p_x
Q_Carter = p_theta^2 + cos^2(theta)
           [L_z^2 / sin^2(theta) - a^2 E^2]
```

`Q_charge` denotes the black-hole electric charge; `Q_Carter` denotes the
Carter separation constant. They must not be conflated. The current validator
does not implement charged-particle Lorentz force, polarization transport, or
maximal extension.

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

## Time-Dependent BBH Track

This section freezes the conventions used by the dynamic-spacetime oracle.
It follows `vincent2012geodesic3p1` and `bohn2015bbhAppearance`. Coordinates
are `x^mu = (t, x^i)`, momenta are covariant canonical components `p_mu`, the
signature is `(-,+,+,+)`, and `G = c = 1`.

### ADM reconstruction

The 3+1 line element is

```text
ds^2 = -alpha^2 dt^2
       + gamma_ij (dx^i + beta^i dt)(dx^j + beta^j dt).
```

With `beta_i = gamma_ij beta^j`, the four-metric and its inverse are

```text
g_00 = -alpha^2 + beta_i beta^i
g_0i = beta_i
g_ij = gamma_ij

g^00 = -1 / alpha^2
g^0i = beta^i / alpha^2
g^ij = gamma^ij - beta^i beta^j / alpha^2.
```

The future-directed null root used to initialize a covariant momentum is

```text
p_t = beta^i p_i - alpha sqrt(gamma^ij p_i p_j).
```

This is the negative-energy branch because the Eulerian photon energy is
`E_n = -p_mu n^mu > 0`, with `n^mu = alpha^-1 (1, -beta^i)`.

### Canonical dynamic Hamiltonian

The primary f64 oracle evolves the complete four-dimensional Hamilton system:

```text
H(t, x, p) = 1/2 g^mu_nu(t, x) p_mu p_nu = 0

dx^mu / dlambda = g^mu_nu p_nu
dp_mu / dlambda = -1/2 partial_mu(g^alpha_beta) p_alpha p_beta.
```

In particular,

```text
dp_t / dlambda = -1/2 partial_t(g^alpha_beta) p_alpha p_beta.
```

`p_t` is conserved only when `partial_t g^mu_nu = 0`. Likewise, `p_phi`
requires axial symmetry and the Kerr Carter constant requires separability.
None is a generic BBH invariant. Dynamic audit therefore uses the null
Hamiltonian, provider constraint residuals, interpolation convergence, and
analytic limiting cases. A renderer must not freeze `p_t` merely because the
stationary Kerr implementation did so.

### Analytic plane-GW gate

Before introducing a binary approximation, the dynamic solver is tested with
the transverse-traceless plane wave of `angelil2015gwOptics`, generalized to
an arbitrary propagation direction `k_hat` and polarization angle `psi`:

```text
g_mu_nu = eta_mu_nu + h_mu_nu
h_0mu = 0
h_ij = h cos[omega(k_hat dot x - t) + phase] e_ij(psi)

e_ij(psi) = cos(2 psi) (u_i u_j - v_i v_j)
          + sin(2 psi) (u_i v_j + v_i u_j),
u dot k_hat = v dot k_hat = u dot v = 0.
```

The implementation inverts this finite-amplitude metric exactly and evaluates
`partial_mu g^alpha beta` analytically. Its vacuum interpretation is asserted
only to first order in the physical strain `h`; the finite-amplitude inverse is
a numerically convenient extension, not an exact nonlinear plane-wave vacuum
solution.

For a ray followed to a fixed arrival plane, the first-order coordinate-time
delay is Angelil and Saha Eq. 14 evaluated along the unperturbed ray. The
numerical-minus-first-order residual must therefore scale as `O(h^2)`. This
gate also verifies that `h -> 0` is exactly Minkowski and that a dynamic wave
produces nonzero `Delta p_t` while preserving the null Hamiltonian.

Any display amplification is applied only after tracing:

```text
display_angular_displacement = visual_gain * physical_angular_displacement
```

`visual_gain` is metadata and must never modify the metric provider or its
physical audit buffers.

### Superposed boosted Kerr-Schild approximation

The first BBH provider follows Combi and Ressler Eq. 11. In global Cartesian
coordinates it adds two Lorentz-transformed single-hole Kerr-Schild
perturbations to one shared flat background:

```text
g_ab = eta_ab
     + [2 H Lambda^d_a l_d Lambda^c_b l_c]_(1)
     + [2 H Lambda^d_a l_d Lambda^c_b l_c]_(2).
```

For the first accepted slice each hole is nonspinning, so in its instantaneous
rest frame

```text
H_A = M_A / R_A,
l_a dX^a = dT + X_i dX^i / R_A.
```

The global-to-hole spatial coordinates and covector Jacobian use the
instantaneous Lorentz boost of Combi-Ressler Eqs. 8-10. Following the source,
explicit acceleration terms are omitted from that Jacobian to avoid the
accelerated-coordinate pathology at large radius. Time dependence still
enters through the hole positions, velocities, and changing boost direction.

The first orbit is equal-mass and circular at fixed coordinate separation:

```text
Omega^2 = M_total / separation^3,
s_1 = +(separation/2) (cos Omega t, sin Omega t, 0),
s_2 = -s_1.
```

This Newtonian fixed orbit is a controlled entry slice, not the paper's full
4PN inspiral and not a merger model. The provider uses explicit excision
worldtubes only as runtime validity surfaces; they are not event horizons.

The next trajectory slice adds leading-quadrupole adiabatic radiation
reaction for a nonspinning quasi-circular binary, following
`peters1964grMotionTwoPointMasses`. With `eta=m1 m2/M^2`:

```text
dr/dt = -(64/5) eta M^3 / r^3,
r(t)^4 = r0^4 - (256/5) eta M^3 (t-t0),
Omega^2 = M/r^3,
phi(t)-phi0 = [r0^(5/2)-r(t)^(5/2)] / [32 eta M^(5/2)].
```

The implementation fails closed at a declared minimum separation. This is a
PN entry and timing oracle, not a claim that the full 4PN trajectory in
Combi-Ressler has already been implemented.

The independent 3+1 audit uses

```text
K_ij = [-partial_t gamma_ij + D_i beta_j + D_j beta_i] / (2 alpha),
H_constraint = R + K^2 - K_ij K^ij,
M^i_constraint = D_j (K^ij - gamma^ij K).
```

The superposition does not solve these constraints exactly. Their residuals
are scientific output measuring approximation quality, not numerical noise to
hide or renormalize away.

### Independent 3+1 cross-check

For validation, decompose the photon momentum in the Eulerian frame as

```text
p^mu = E_n (n^mu + V^mu),
n_mu V^mu = 0,
gamma_ij V^i V^j = 1.
```

Using the extrinsic-curvature convention
`K_ij = -1/2 Lie_n(gamma_ij)`, Vincent et al. give

```text
dx^i / dt = alpha V^i - beta^i
dE_n / dt = E_n alpha
             [K_ij V^i V^j - V^i partial_i ln(alpha)].
```

Bohn et al. instead evolve the normalized covariant direction

```text
Pi_i = p_i / (alpha p^0)
     = p_i / sqrt(gamma^jk p_j p_k),
Pi^i = gamma^ij Pi_j,

dx^i / dt = alpha Pi^i - beta^i,

dPi_i / dt = -partial_i alpha
              + (partial_j alpha Pi^j
                 - alpha K_jk Pi^j Pi^k) Pi_i
              + partial_i beta^k Pi_k
              - alpha/2 partial_i gamma^jk Pi_j Pi_k,

d ln(alpha p^0) / dt = -partial_i alpha Pi^i
                        + alpha K_ij Pi^i Pi^j.
```

The canonical and normalized-momentum forms must agree on events, redshift,
and escape direction in their common validity domain. The normalized form is a
cross-check and possible GPU optimization, not a replacement oracle.

### Dynamic redshift and horizons

The frequency measured by an observer with four-velocity `u^mu` is

```text
nu = -p_mu u^mu.
```

Thus the transfer factor from emitter to receiver is

```text
g = nu_rec / nu_emit
  = (-p_mu u_rec^mu) / (-p_mu u_emit^mu),
1 + z = 1 / g.
```

This definition remains valid without stationarity. It must use the photon
momentum and observer/emitter states at their respective intersection events;
a single conserved energy at infinity is not available in a generic BBH.

Runtime capture may use a versioned apparent-horizon surface or an explicit
excision worldtube supplied by the metric producer. An event horizon is
future-global and may only be reconstructed offline. Any superposed
Kerr-Schild or PN-to-remnant BBH provider is labelled
`physics_approximation`; real-time evaluation of that provider is not a
real-time solution of the Einstein equations.
