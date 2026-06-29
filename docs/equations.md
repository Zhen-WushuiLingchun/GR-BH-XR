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
- Direct / secondary disk images: `luminet1979blackHoleImage`.
- Shadow / lensing ring / photon ring and higher-order image scaling:
  `gralla2019shadowsPhotonRings`, `gralla2020lensingKerr`.
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
