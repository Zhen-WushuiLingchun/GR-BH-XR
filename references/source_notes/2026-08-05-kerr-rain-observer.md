# Kerr Rain (Doran) Observer Frame - Source Note

Search date: 2026-08-05
Search terms: Doran new form of the Kerr solution free-fall observers;
Painleve-Gullstrand Kerr; river model of black holes; Kerr rain frame
constant theta.

## Why these sources were consulted

The horizon-crossing descent path needs a camera frame that stays regular
through the outer horizon. The static and ZAMO frames both fail before the
horizon (the static frame already fails at the ergosurface), so a free-fall
congruence is required. The two sources below are the ones the implementation
actually follows.

## Doran 2000 - New form of the Kerr solution

- BibTeX key: `doran2000newKerrForm`
- Stable locator: arXiv `gr-qc/9910099`; DOI `10.1103/PhysRevD.61.067503`
- Journal: Physical Review D 61, 067503 (2000)
- PDF path: not stored; open arXiv preprint available at the locator above.

Presents a form of the Kerr solution in which the time coordinate is the proper
time of a family of free-falling observers, generalizing the
Painleve-Gullstrand form of Schwarzschild to nonzero spin. The chart is
well-behaved at the horizon and is convenient for tetrad work.

The property this project relies on: the free-fall congruence dropped from rest
at infinity falls at **constant Boyer-Lindquist polar angle**. That is what
makes the four conditions used in `kerr_rain_velocity_ks` mutually consistent
rather than overdetermined. The underlying reason is visible in the Carter
polar potential

```text
Theta = Q - cos^2(theta) [ a^2 (1 - E^2) + L^2 / sin^2(theta) ]
```

With `E = 1` and `L = 0` both bracketed terms vanish identically, so
`Theta = Q` independent of `theta`. Setting `Q = 0` therefore makes
`dtheta/dtau = 0` an exact solution at *every* polar angle, not only at special
ones.

## Hamilton and Lisle 2008 - The river model of black holes

- BibTeX key: `hamiltonLisle2008riverModel`
- Stable locator: arXiv `gr-qc/0411060`; DOI `10.1119/1.2830526`
- Journal: American Journal of Physics 76(6), 519-532 (2008)
- PDF path: not stored; open arXiv preprint available at the locator above.

Interprets the Painleve-Gullstrand / Doran family as a "river" of space flowing
inward at the Newtonian escape velocity, reaching the speed of light at the
horizon and exceeding it inside. For Kerr the river both falls and twists.

Project use: this is the physical picture behind treating the rain observer as
the natural descent camera, and behind the expectation that the frame stays
regular through `r_+` while the ingoing chart carries the divergence. It is a
pedagogical/interpretive source, not the source of any equation implemented
here.

## What the implementation takes from these

`src/gr_bh_xr/observers.py`:

- `kerr_rain_velocity_ks` solves `u_t = -1`, `L_z = 0`, `dtheta/dtau = 0`,
  `u.u = -1` algebraically in Cartesian ingoing Kerr-Schild coordinates, taking
  the ingoing future-pointing root. The consistency of those four conditions is
  the Doran property above.
- `analytic_kerr_rain_velocity_ks` is the independent closed-form reference
  used by the gate, written in a form that stays regular at `Delta = 0`:

```text
s = sqrt(2 M r (r^2 + a^2)),   Sigma = r^2 + a^2 cos^2(theta)
u^r      = -s / Sigma
u^theta  = 0
u^phi_KS = -2 M a r / (Sigma (2 M r + s))
u^t_KS   = [ (r^2+a^2) ((r^2+a^2)^2 + 2 M r (r^2+a^2) + 4 M^2 r^2)
             / ((r^2+a^2)^2 + 2 M r s) - a^2 sin^2(theta) ] / Sigma
```

  The Schwarzschild limit of `u^t_KS` is `(1 + w + w^2)/(1 + w)` with
  `w = sqrt(2M/r)`, the standard ingoing Eddington-Finkelstein rain result, and
  `u^r -> -sqrt(2M/r)`.

## Limitations and open questions

- The rain tetrad is built algebraically at each point, not parallel
  transported along the worldline. Consecutive samples therefore differ from a
  transported frame by an unrecorded rotation.
- The frame is undefined on the symmetry axis, where the constraint system
  loses rank; the implementation refuses rather than returning a degraded
  frame.
- Interior validity is claimed only between the inner and outer horizons. The
  mass-inflation region below `r_-` is out of scope, and revisiting it would
  need its own indexed sources; none are claimed here.
