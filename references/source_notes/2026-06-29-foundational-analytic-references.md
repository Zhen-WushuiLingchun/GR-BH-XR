# Source Notes: Foundational Analytic Kerr / Lensing / Disk References

Search/use date: 2026-06-29.

Purpose: close the Phase 0 gap in which the project indexed many GRRT/GRMHD
codes and real-time shaders but none of the primary analytic literature behind
the equations written in `docs/equations.md` and the vocabulary in
`docs/physical_scope.md`. These notes record provenance only; they do not
replace reading the papers before implementing the Phase 1 solver.

## Equation-To-Source Map

| Equation / concept in repo | Primary source | BibTeX key |
| --- | --- | --- |
| Carter constant `Q`, geodesic separability | Carter 1968 | `carter1968kerr` |
| `r_ISCO(a)`, locally nonrotating frame | Bardeen, Press, Teukolsky 1972 | `bardeen1972rotatingBlackHoles` |
| `(alpha, beta)` screen impact parameters, Kerr null geodesics | Bardeen 1973 | `bardeen1973kerrGeodesics` |
| Disk redshift factor `g`, transfer function | Cunningham 1975 | `cunningham1975kerrDiskSpectrum` |
| Direct / secondary thin-disk images | Luminet 1979 | `luminet1979blackHoleImage` |
| Shadow / critical curve / lensing ring / photon ring | Gralla, Holz, Wald 2019 | `gralla2019shadowsPhotonRings` |
| Higher-order image demagnification / rotation / time delay | Gralla & Lupsasca 2020 (lensing) | `gralla2020lensingKerr` |
| Closed-form Kerr null geodesics (cross-check) | Gralla & Lupsasca 2020 (geodesics) | `gralla2020nullGeodesicsKerr` |

## Open arXiv PDFs Added (2026-06-29)

All are open arXiv downloads stored under `references/pdfs/`.

| File | Source URL | Journal ref |
| --- | --- | --- |
| `references/pdfs/2019-gralla-holz-wald-shadows-photon-lensing-rings.pdf` | https://arxiv.org/pdf/1906.00873 | Phys. Rev. D 100, 024018 (2019) |
| `references/pdfs/2020-gralla-lupsasca-lensing-by-kerr.pdf` | https://arxiv.org/pdf/1910.12873 | Phys. Rev. D 101, 044031 (2020) |
| `references/pdfs/2020-gralla-lupsasca-null-geodesics-kerr.pdf` | https://arxiv.org/pdf/1910.12881 | Phys. Rev. D 101, 044032 (2020) |
| `references/pdfs/2016-odyssey-gpu-kerr-grrt.pdf` | https://arxiv.org/pdf/1601.02063 | ApJ 820, 105 (2016) |

The Odyssey PDF was added in this pass to correct an earlier index note that an
open original PDF was not confirmed; the arXiv version is open.

## Metadata-Only Classics (No Open-Access PDF)

These predate arXiv and have no redistributable open PDF. They are indexed by
DOI / ADS bibcode only. A personal copy may be placed in the ignored
`references/pdfs/local_only/` directory; it must not be committed.

| Source | Locator |
| --- | --- |
| Carter 1968, Phys. Rev. 174, 1559 | doi:10.1103/PhysRev.174.1559 |
| Bardeen, Press, Teukolsky 1972, ApJ 178, 347 | doi:10.1086/151796 |
| Bardeen 1973, Black Holes (Les Houches 1972), pp. 215-239 | Gordon and Breach |
| Cunningham 1975, ApJ 202, 788 | doi:10.1086/154033 |
| Luminet 1979, A&A 75, 228 | ADS 1979A&A....75..228L |

## Verification Performed

- All four arXiv identifiers were confirmed against arXiv abstract pages before
  download; titles, authors, and journal references match the BibTeX entries.
- The two Gralla & Lupsasca papers were disambiguated: `1910.12873` is "Lensing
  by Kerr Black Holes" (PRD 101, 044031) and `1910.12881` is "Null Geodesics of
  the Kerr Exterior" (PRD 101, 044032).
- Each downloaded file was checked to begin with a `%PDF` header.

## Boundary Notes

- These analytic papers define equations, conserved quantities, and validation
  targets; they are the provenance layer the GRRT/GRMHD codes and shaders do not
  provide.
- They do not change the first-year Kerr scope or the deferred GRMHD/BBH/neural
  work.
