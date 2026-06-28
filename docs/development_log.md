# Development Log

Use this log to keep academic and physics-facing context close to the code.
For large entries, create a separate `docs/YYYY-MM-DD-topic.md` note and link it
from here.

## Entry Template

### YYYY-MM-DD - Short title

- Goal:
- Changed files / components:
- Academic reason:
- Physical correspondence:
- Assumptions and conventions:
- Validation:
- References:
- Open issues / next steps:

## Log

### 2026-06-28 - Physics-auditable renderer roadmap

- Goal: Convert the project direction into a staged physics-auditable renderer
  plan.
- Changed files / components: `docs/plans/2026-06-28-physics-auditable-renderer.md`,
  `docs/physical_scope.md`, `docs/equations.md`, `docs/validation_targets.md`,
  `AGENTS.md`, `references/references.md`, and
  `references/source_notes/2026-06-28-physics-auditable-renderer-sources.md`.
- Academic reason: Prevent the project from becoming a visual-only black-hole
  shader by requiring transfer quantities, validation targets, and literature
  traceability.
- Physical correspondence: The core renderer is framed as a map from observer
  screen coordinates `(alpha, beta)` to capture state, disk crossing data,
  redshift, time delay, image order, optical depth, and observed intensity.
- Assumptions and conventions: First-year work targets single-Kerr physics and
  Quest PCVR/MR display. Full GRMHD, BBH numerical relativity, Quest-native
  GRRT, and direct neural image generation are deferred.
- Validation: Documentation-level validation only; no solver exists yet. The
  plan defines future checks for Hamiltonian drift, conserved quantities,
  Schwarzschild shadow radius, disk transfer, headset behavior, and benchmark
  comparisons.
- References: See `references/references.md` entries for RAPTOR, Odyssey, BHAC,
  AART, Davelaar VR work, Meta Quest documentation, Unity OpenXR Meta
  passthrough documentation, and Meta Depth API.
- Open issues / next steps: Choose the initial reference-solver language and
  data format, then implement Phase 1 CPU Kerr geodesic validation.

### 2026-06-28 - Repository documentation protocol

- Goal: Establish project documentation rules for agent work, literature
  tracking, development logs, and local-only paper drafts.
- Changed files / components: `AGENTS.md`, `references/references.md`,
  `docs/development_log.md`, `.gitignore`, and local `paper_draft/`.
- Academic reason: Keep implementation decisions traceable to literature,
  assumptions, and project-level scientific reasoning from the beginning.
- Physical correspondence: No physics model has been implemented yet; this
  entry only defines the protocol for documenting future model-to-visualization
  mappings.
- Assumptions and conventions: Literature entries belong in
  `references/references.md`; manuscript drafts remain local in `paper_draft/`.
- Validation: Confirm repository layout and Git ignore behavior after editing.
- References: None.
- Open issues / next steps: Add technology-stack-specific build, test, and
  validation instructions once the project architecture is chosen.
