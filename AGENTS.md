# AGENTS.md

This file defines the working rules for agents and contributors in this
repository.

## Project Scope

GR-BH-XR is treated as an academic software project. Code, assets, notes, and
experiments should preserve the connection between implementation choices,
physics assumptions, and literature evidence.

## Repository Layout

- `references/`: Literature files, notes, and the central literature index.
- `references/references.md`: Required index for every paper or source added to
  `references/`.
- `docs/`: Development logs and technical notes explaining academic motivation,
  physical correspondence, assumptions, validation, and unresolved issues.
- `paper_draft/`: Local-only manuscript drafts. This directory must not be
  committed or pushed to GitHub.

## Literature Workflow

When a problem requires literature search or a paper is used to justify a
technical decision:

1. Put the source file, exported citation, or stable source note under
   `references/`.
2. Update `references/references.md` in the same change.
3. Keep each entry close to its source path and include:
   - citation key or short title;
   - file path, DOI, URL, arXiv ID, or other stable locator;
   - why the source was added;
   - a short content summary;
   - equations, physical assumptions, datasets, or implementation ideas relevant
     to this project;
   - open questions or limitations.
4. Record the search date and search terms when the source was found through a
   literature search.

Do not rely on an unindexed PDF or note. If it is useful enough to keep, it must
be findable from `references/references.md`.

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
- Keep numerical parameters traceable to a reference, derivation, or explicit
  project assumption.
- Distinguish visual approximation, pedagogical approximation, and physically
  validated behavior.
- When adding XR visualization behavior, document what physical quantity the
  visual element represents and what has been stylized for usability.
- Avoid silent changes to equations, constants, or coordinate conventions.

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
