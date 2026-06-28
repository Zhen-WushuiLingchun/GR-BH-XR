# AGENTS.md

This file defines the working rules for agents and contributors in this
repository.

## Project Scope

GR-BH-XR is treated as an academic software project. Code, assets, notes, and
experiments should preserve the connection between implementation choices,
physics assumptions, and literature evidence.

The project should be designed as a **physics-auditable renderer**, not a
visual-only black-hole demo. Renderer output must remain traceable to physical
quantities such as escape/capture state, image order, disk crossing location,
redshift factor, time delay, optical depth, and observed intensity.

The first-year target is a single-Kerr PCVR/MR system: background lensing,
shadow, thin disk transfer function, redshift/Doppler terms,
time-delay-aware disk variability, direct/secondary/higher-order images, and
Quest 3 display through PCVR/MR overlay. BBH, full GRMHD, and neural surrogate
work are later-stage extensions.

## Repository Layout

- `references/`: Literature files, notes, and the central literature index.
- `references/pdfs/`: Original paper PDFs that are safe to keep in the
  repository.
- `references/pdfs/local_only/`: Local-only PDFs that must not be pushed, such
  as restricted-access or oversized files.
- `references/source_notes/`: Short source-review notes and literature-search
  notes.
- `references/references.md`: Required index for every paper or source added to
  `references/`.
- `docs/`: Development logs and technical notes explaining academic motivation,
  physical correspondence, assumptions, validation, and unresolved issues.
- `docs/plans/`: Dated implementation plans.
- `docs/physical_scope.md`: Current scope, claims, deferred work, and
  approximation labels.
- `docs/equations.md`: Equations, coordinates, units, and conventions that code
  must follow.
- `docs/validation_targets.md`: Stage gates and validation targets.
- `paper_draft/`: Local-only manuscript drafts. This directory must not be
  committed or pushed to GitHub.

## Literature Workflow

When a problem requires literature search or a paper is used to justify a
technical decision:

1. Put the source file, exported citation, or stable source note under
   `references/`.
2. If an original paper PDF is useful and safe to keep in the repository, put it
   under `references/pdfs/`. If the PDF is restricted, too large, or not safe to
   redistribute, put it under `references/pdfs/local_only/` and do not commit it.
3. Update `references/references.md` in the same change.
4. Keep each entry close to its source path and include:
   - citation key or short title;
   - file path, DOI, URL, arXiv ID, or other stable locator;
   - PDF path or local-only PDF status;
   - why the source was added;
   - a short content summary;
   - equations, physical assumptions, datasets, or implementation ideas relevant
     to this project;
   - open questions or limitations.
5. Record the search date and search terms when the source was found through a
   literature search.

Do not rely on an unindexed PDF or note. If it is useful enough to keep, it must
be findable from `references/references.md`. Do not commit paywalled,
license-unclear, or private PDFs unless redistribution is explicitly allowed.

## Development Log Workflow

Use `docs/development_log.md` for compact chronological entries. For larger
work, add a separate file under `docs/` and link it from the log.

Each meaningful development step should record:

- date;
- goal;
- changed files or components;
- academic reason for the change;
- physical correspondence, including units, frames, coordinates, constants, and
  approximations when relevant;
- validation performed, including tests, visual checks, equations checked, or
  comparisons with references;
- unresolved issues and next steps.

## Physics And Modeling Rules

- State the coordinate system, sign convention, units, and normalization before
  implementing physics logic.
- Default to geometric units (`G = c = 1`) and document any departure from that
  convention.
- Do not add a physics module without a documented validation path in
  `docs/validation_targets.md`.
- Keep numerical parameters traceable to a reference, derivation, or explicit
  project assumption.
- Distinguish visual approximation, pedagogical approximation, and physically
  validated behavior.
- When adding XR visualization behavior, document what physical quantity the
  visual element represents and what has been stylized for usability.
- Avoid silent changes to equations, constants, or coordinate conventions.

## Renderer Audit Requirements

Do not treat an RGB image as the only product of a renderer. A physics-facing
renderer stage should expose or record the relevant subset of:

- escape/capture mask;
- disk crossing or image order `m`;
- crossing position `(r_m, phi_m)`;
- redshift factor `g_m`;
- time delay `Delta t_m`;
- winding/orbit number `n_m`;
- optical depth `tau_m`;
- observed intensity `I_nu_o`;
- diagnostic residuals such as Hamiltonian or conserved-quantity drift.

If a prototype cannot expose these quantities, mark it as a visual prototype and
do not use it for academic claims.

## Stage Gates

- Before disk work: validate the Kerr/Schwarzschild null-geodesic solver.
- Before Quest work: produce a stable PC renderer output and define the headset
  validation checks.
- Before MR passthrough lensing claims: verify whether the chosen API exposes
  camera-frame pixels. Otherwise limit claims to overlay, depth occlusion, or
  approximate environment-texture lensing.
- Before simplified GRRT: document emission/absorption conventions and benchmark
  targets.
- Before GRMHD: use existing snapshots and GRRT post-processing; do not start by
  implementing a GRMHD solver.
- Before BBH: separate visual toys, time-dependent vacuum metrics,
  phenomenological accretion, and full NR/GRMHD/GRRT.
- Before neural acceleration: generate exact data first, then learn transfer
  functions or cached radiance fields. Do not use neural networks to directly
  generate final black-hole imagery without audit buffers.

## Paper Draft Policy

- Keep manuscript drafts in `paper_draft/`.
- `paper_draft/` is intentionally ignored by Git and must not be pushed to
  GitHub.
- If a draft contains a stable technical result that should be versioned, move a
  summarized and sanitized note into `docs/`; do not commit private draft text
  unless explicitly requested.

## Git And Change Hygiene

- Check `git status` before editing.
- Preserve user changes that are unrelated to the current task.
- Keep commits focused and explain academic or physics-facing changes in the
  commit message or development log.
- Do not commit secrets, credentials, private data, local environment files,
  generated build products, or large binary outputs unless the project has an
  explicit storage policy for them.
- Prefer reproducible scripts, documented parameters, and small testable changes.

## Validation Expectations

Before considering work complete, run the relevant checks available for the
current technology stack. If no stack-specific tests exist yet, at minimum
verify file organization, Git status, and documentation consistency.

For simulation or visualization changes, add or record at least one relevant
validation path, such as:

- equation or limiting-case check;
- comparison with a reference result;
- numerical sanity check;
- screenshot or interaction check for XR/frontend behavior;
- documented reason when validation is not yet possible.
