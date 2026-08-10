"""Verify and apply the pinned GR-BH-XR patches to an ET checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Final


PATCH_TARGETS: Final[dict[str, tuple[str, str | None]]] = {
    "ahfinderdirect-final-expansion-diagnostic.patch": (
        "repos/SpacetimeX",
        "AHFinderDirect",
    ),
    "ahfinderdirect-metric-diagnostic.patch": (
        "repos/SpacetimeX",
        "AHFinderDirect",
    ),
    "ahfinderx-gcc-std-qualification.patch": ("repos/SpacetimeX", None),
    "carpetx-driver-interpolate-per-call-order.patch": (
        "repos/CarpetX",
        "CarpetX",
    ),
    "multipole-carpetx-prolongation-none.patch": (
        "repos/einsteinanalysis",
        None,
    ),
    "sphericalsurface-lazy-reduction-handles.patch": (
        "repos/cactusnumerical",
        "SphericalSurface",
    ),
}


def _git_apply_command(
    patch: Path, *, directory: str | None, reverse: bool = False, check: bool = False
) -> list[str]:
    command = ["git", "apply"]
    if reverse:
        command.append("--reverse")
    if check:
        command.append("--check")
    if directory is not None:
        command.append(f"--directory={directory}")
    command.append(str(patch))
    return command


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf8",
        errors="replace",
    )


def apply_release_patches(cactus_root: Path | str, *, check_only: bool = False) -> dict:
    root = Path(cactus_root).resolve()
    script_dir = Path(__file__).resolve().parent
    patches_dir = script_dir / "patches"
    lock = json.loads((script_dir / "release_lock.json").read_text(encoding="utf8"))
    locked_hashes = lock["local_patches"]
    if set(locked_hashes) != set(PATCH_TARGETS):
        raise RuntimeError("release_lock.json and PATCH_TARGETS name different patches")

    results: list[dict] = []
    for name, (repository_relative, directory) in PATCH_TARGETS.items():
        patch = patches_dir / name
        actual_hash = hashlib.sha256(patch.read_bytes()).hexdigest()
        if actual_hash != locked_hashes[name]:
            raise RuntimeError(f"Pinned patch hash mismatch: {name}")
        repository = root / repository_relative
        if not (repository / ".git").exists():
            raise RuntimeError(f"Missing ET component repository: {repository}")

        reverse_check = _run(
            _git_apply_command(patch, directory=directory, reverse=True, check=True),
            cwd=repository,
        )
        if reverse_check.returncode == 0:
            status = "already_applied"
        else:
            forward_check = _run(
                _git_apply_command(patch, directory=directory, check=True),
                cwd=repository,
            )
            if forward_check.returncode != 0:
                detail = forward_check.stderr.strip() or forward_check.stdout.strip()
                raise RuntimeError(f"Patch does not apply cleanly: {name}: {detail}")
            if check_only:
                status = "applicable"
            else:
                applied = _run(
                    _git_apply_command(patch, directory=directory), cwd=repository
                )
                if applied.returncode != 0:
                    detail = applied.stderr.strip() or applied.stdout.strip()
                    raise RuntimeError(f"Patch application failed: {name}: {detail}")
                status = "applied"
        results.append(
            {
                "name": name,
                "sha256": actual_hash,
                "repository": str(repository),
                "directory": directory,
                "status": status,
            }
        )
    return {
        "schema": "gr-bh-xr.et-release-patches.v1",
        "et_release": lock["et_release"],
        "cactus_root": str(root),
        "check_only": bool(check_only),
        "patches": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cactus-root", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            apply_release_patches(args.cactus_root, check_only=args.check_only),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
