"""Validate native NPGS synthetic-stereo GPU timing evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence


SCHEMA = "gr-bh-xr.npgs.stereo-performance.v1"
_CONFIG_RE = re.compile(
    r"^NPGS_STEREO_CONFIG\s+"
    r"mode=(?P<mode>\w+)\s+eye_width=(?P<width>\d+)\s+"
    r"eye_height=(?P<height>\d+)\s+ipd_m=(?P<ipd>[-+0-9.eE]+)\s+"
    r"meters_per_M=(?P<meters>[-+0-9.eE]+)\s+disk=(?P<disk>[01])\s+"
    r"polarization=(?P<polarization>[01])\s+taa=(?P<taa>\w+)\s*$"
)
_SAMPLE_RE = re.compile(
    r"^NPGS_STEREO_GPU\s+pair=(?P<pair>\d+)\s+eye=(?P<eye>[01])\s+"
    r"valid=(?P<valid>[01])\s+total_ms=(?P<total>[-+0-9.eE]+)\s+"
    r"prepass_ms=(?P<prepass>[-+0-9.eE]+)\s+"
    r"composite_ms=(?P<composite>[-+0-9.eE]+)\s+"
    r"post_ms=(?P<post>[-+0-9.eE]+)\s+cpu_submit_ms=(?P<cpu>[-+0-9.eE]+)\s*$"
)


@dataclass(frozen=True)
class StereoConfig:
    mode: str
    eye_width: int
    eye_height: int
    ipd_m: float
    meters_per_M: float
    disk: bool
    polarization: bool
    taa: str


@dataclass(frozen=True)
class EyeSample:
    pair: int
    eye: int
    valid: bool
    total_ms: float
    prepass_ms: float
    composite_ms: float
    post_ms: float
    cpu_submit_ms: float


def parse_stereo_log(lines: Iterable[str]) -> tuple[StereoConfig, list[EyeSample]]:
    """Parse the fail-closed native line protocol."""

    config: StereoConfig | None = None
    samples: list[EyeSample] = []
    for raw_line in lines:
        line = raw_line.strip()
        if match := _CONFIG_RE.match(line):
            parsed = StereoConfig(
                mode=match["mode"],
                eye_width=int(match["width"]),
                eye_height=int(match["height"]),
                ipd_m=float(match["ipd"]),
                meters_per_M=float(match["meters"]),
                disk=match["disk"] == "1",
                polarization=match["polarization"] == "1",
                taa=match["taa"],
            )
            if config is not None and config != parsed:
                raise ValueError("stereo log contains conflicting configurations")
            config = parsed
            continue
        if match := _SAMPLE_RE.match(line):
            values = [
                float(match[name])
                for name in ("total", "prepass", "composite", "post", "cpu")
            ]
            if not all(math.isfinite(value) and value >= 0.0 for value in values):
                raise ValueError("stereo sample contains an invalid duration")
            samples.append(
                EyeSample(
                    pair=int(match["pair"]),
                    eye=int(match["eye"]),
                    valid=match["valid"] == "1",
                    total_ms=values[0],
                    prepass_ms=values[1],
                    composite_ms=values[2],
                    post_ms=values[3],
                    cpu_submit_ms=values[4],
                )
            )
    if config is None:
        raise ValueError("stereo log has no NPGS_STEREO_CONFIG record")
    if config.mode not in {"sequential", "multiview"}:
        raise ValueError(f"unsupported stereo mode {config.mode!r}")
    if config.eye_width <= 0 or config.eye_height <= 0:
        raise ValueError("stereo eye extent must be positive")
    if not math.isfinite(config.ipd_m) or config.ipd_m < 0.0:
        raise ValueError("stereo IPD must be finite and nonnegative")
    if not math.isfinite(config.meters_per_M) or config.meters_per_M <= 0.0:
        raise ValueError("meters_per_M must be finite and positive")
    return config, samples


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile from no values")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _stats(values: Sequence[float]) -> dict[str, float]:
    return {
        "p50": median(values),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "max": max(values),
    }


def summarize_stereo_performance(
    config: StereoConfig,
    samples: Sequence[EyeSample],
    *,
    minimum_valid_ratio: float = 0.99,
) -> dict[str, object]:
    """Aggregate complete left/right pairs and apply refresh-rate gates."""

    by_pair: dict[int, dict[int, EyeSample]] = {}
    duplicate_count = 0
    for sample in samples:
        eyes = by_pair.setdefault(sample.pair, {})
        if sample.eye in eyes:
            duplicate_count += 1
        eyes[sample.eye] = sample

    complete_pairs = [(pair, eyes) for pair, eyes in sorted(by_pair.items()) if set(eyes) == {0, 1}]
    valid_pairs = [
        (pair, eyes)
        for pair, eyes in complete_pairs
        if eyes[0].valid and eyes[1].valid
    ]
    # A missing eye record is itself invalid timing evidence. Using only
    # complete pairs here would let a truncated logger silently improve the
    # headline ratio.
    valid_ratio = len(valid_pairs) / len(by_pair) if by_pair else 0.0
    pair_gpu = [eyes[0].total_ms + eyes[1].total_ms for _, eyes in valid_pairs]
    pair_cpu = [eyes[0].cpu_submit_ms + eyes[1].cpu_submit_ms for _, eyes in valid_pairs]
    eye_totals = [eyes[eye].total_ms for _, eyes in valid_pairs for eye in (0, 1)]
    prepass = [eyes[eye].prepass_ms for _, eyes in valid_pairs for eye in (0, 1)]
    composite = [eyes[eye].composite_ms for _, eyes in valid_pairs for eye in (0, 1)]
    post = [eyes[eye].post_ms for _, eyes in valid_pairs for eye in (0, 1)]

    enough_valid = bool(complete_pairs) and valid_ratio >= minimum_valid_ratio
    gpu_stats = _stats(pair_gpu) if pair_gpu else None
    cpu_stats = _stats(pair_cpu) if pair_cpu else None
    eye_stats = _stats(eye_totals) if eye_totals else None
    stage_stats = {
        "prepass": _stats(prepass) if prepass else None,
        "composite": _stats(composite) if composite else None,
        "post": _stats(post) if post else None,
    }
    p95 = gpu_stats["p95"] if gpu_stats is not None else math.inf
    return {
        "schema": SCHEMA,
        "config": asdict(config),
        "counts": {
            "eye_samples": len(samples),
            "pair_ids": len(by_pair),
            "complete_pairs": len(complete_pairs),
            "valid_pairs": len(valid_pairs),
            "invalid_or_incomplete_pairs": len(by_pair) - len(valid_pairs),
            "duplicate_eye_records": duplicate_count,
        },
        "valid_timestamp_ratio": valid_ratio,
        "minimum_valid_timestamp_ratio": minimum_valid_ratio,
        "timing_ms": {
            "stereo_pair_gpu": gpu_stats,
            "stereo_pair_cpu_submission": cpu_stats,
            "per_eye_gpu": eye_stats,
            "per_eye_stages": stage_stats,
        },
        "gates": {
            "valid_timestamps": enough_valid,
            "physics_render_72hz": enough_valid and p95 < 11.0,
            "physics_render_90hz": enough_valid and p95 < 9.0,
            "gpu_time_below_total_72hz_budget": enough_valid and p95 < 13.89,
            "gpu_time_below_total_90hz_budget": enough_valid and p95 < 11.11,
            "openxr_total_frame_72hz": None,
            "openxr_total_frame_90hz": None,
        },
        "claim_boundary": (
            "Synthetic sequential stereo measures two native eye renders without an OpenXR runtime. "
            "It is performance evidence, not a headset refresh-rate result; OpenXR total-frame gates remain unset."
        ),
    }


def validate_log_file(
    path: Path,
    *,
    warmup_pairs: int = 0,
    max_pairs: int | None = None,
) -> dict[str, object]:
    config, samples = parse_stereo_log(path.read_text(encoding="utf-8", errors="replace").splitlines())
    pair_ids = sorted({sample.pair for sample in samples})
    selected = pair_ids[warmup_pairs:]
    if max_pairs is not None:
        selected = selected[:max_pairs]
    selected_set = set(selected)
    samples = [sample for sample in samples if sample.pair in selected_set]
    return summarize_stereo_performance(config, samples)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--warmup-pairs", type=int, default=0)
    parser.add_argument("--max-pairs", type=int)
    args = parser.parse_args(argv)
    if args.warmup_pairs < 0 or (args.max_pairs is not None and args.max_pairs <= 0):
        parser.error("warmup-pairs must be nonnegative and max-pairs must be positive")
    result = validate_log_file(
        args.input, warmup_pairs=args.warmup_pairs, max_pairs=args.max_pairs
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["gates"]["valid_timestamps"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
