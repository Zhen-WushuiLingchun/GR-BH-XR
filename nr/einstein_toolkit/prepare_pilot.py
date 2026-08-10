"""Materialize the two preregistered Einstein Toolkit BBH pilot parfiles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "gr-bh-xr.bbh.nr-pilot-inputs.v1"
RESOLUTIONS = (("low", 1), ("high", 2))
RHO_LINE = "$rho = 1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_pilot(template_path: Path | str, output_dir: Path | str) -> Path:
    """Write the low/high parfiles while changing only the rho assignment."""

    template = Path(template_path).resolve()
    output = Path(output_dir).resolve()
    source = template.read_text(encoding="utf8")
    if source.count(RHO_LINE) != 1:
        raise ValueError(f"template must contain exactly one {RHO_LINE!r} line")

    output.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, object]] = []
    for label, rho in RESOLUTIONS:
        parfile = output / f"bbh_equal_mass_{label}.par"
        parfile.write_text(source.replace(RHO_LINE, f"$rho = {rho}"), encoding="utf8")
        runs.append(
            {
                "label": label,
                "rho": rho,
                "parfile": str(parfile),
                "sha256": _sha256(parfile),
            }
        )

    manifest = output / "pilot_inputs.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "template": str(template),
                "template_sha256": _sha256(template),
                "invariant": "low/high differ only in the $rho assignment",
                "runs": runs,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(materialize_pilot(args.template, args.out_dir))


if __name__ == "__main__":
    main()
