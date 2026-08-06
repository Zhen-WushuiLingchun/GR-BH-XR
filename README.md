# GR-BH-XR

GR-BH-XR is planned as a physics-auditable XR renderer for black-hole lensing,
GRRT transfer functions, and later time-dependent binary-spacetime extensions.

## Project Conventions

See `AGENTS.md` for repository workflow rules.

- `references/`: literature files and notes.
- `references/pdfs/`: original literature PDFs safe to keep in Git.
- `references/pdfs/local_only/`: local-only PDFs, ignored by Git.
- `references/source_notes/`: short source notes and literature-search notes.
- `references/code_reviews/`: third-party code and shader-project review notes;
  these record design lessons but do not vendor source code.
- `references/references.md`: required index for all kept references.
- `docs/`: development logs and academic or physics-facing notes.
- `docs/current_status.md`: canonical runtime status and task-number crosswalk.
- `docs/plans/`: dated implementation plans.
- `docs/physical_scope.md`: current physics scope and claim boundaries.
- `docs/equations.md`: equations and conventions that implementation must
  follow.
- `docs/validation_targets.md`: validation gates for renderer stages.
- `paper_draft/`: local-only manuscript drafts, ignored by Git.
- `runtime/NPGS/`: pinned native NPGS fork submodule; see
  `docs/npgs_native_migration.md` before updating it.

The current renderer status, accepted claim boundaries, and native NPGS
migration gates are maintained in `docs/current_status.md`.

## Native Build

Clone with submodules, then use the fail-closed local bootstrap:

```powershell
git clone --recurse-submodules https://github.com/Zhen-WushuiLingchun/GR-BH-XR.git
.\tools\npgs\bootstrap.ps1 -BootstrapVcpkg
.\tools\npgs\build.ps1 -Configuration Release
```

The bootstrap fetches the complete fork and official NPGS history but does not
silently merge a new upstream revision. A changed official SHA must be reviewed
and recorded before the doctor gate is updated.

## License

GR-BH-XR and the integrated native NPGS distribution are licensed under
GPL-3.0-only. Original NPGS authorship and third-party notices are retained in
the submodule and `THIRD_PARTY_NOTICES.md`.
