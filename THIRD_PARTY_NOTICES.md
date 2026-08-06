# Third-Party Notices

## NPGS

- Upstream: https://github.com/baopinshui/NPGS
- Project fork: https://github.com/Zhen-WushuiLingchun/NPGS
- Reviewed official upstream commit:
  `a039e6417b28d53cbd413ee8f6d64543e755aa3e`
- Initial pinned integration-fork commit:
  `d39c7d78d34273c683bf558fdff3364b5a547d28`
- Repository path: `runtime/NPGS` (Git submodule)
- License observed in the upstream repository: GNU General Public License,
  version 3 (`GPL-3.0-only`).

NPGS retains its original Git history and authorship. GR-BH-XR changes are made
on a separate fork branch and are not presented as upstream work. The presence
of a renderer feature in NPGS is not, by itself, evidence that the feature has
passed GR-BH-XR's physics-validation gates.

The initial integration commits add reproducible dependency/build wiring,
generated shader runtime assets, fail-closed startup handling, deterministic
launch controls, and benchmark instrumentation. They do not convert upstream
feature claims into independently validated GR-BH-XR results.

The NPGS dependency manifest brings additional libraries with their own
licenses. Binary distributions must include the notices produced by the
dependency/package tooling as well as this file. No Unity/NPGS combined binary
is distributed during the migration period.
