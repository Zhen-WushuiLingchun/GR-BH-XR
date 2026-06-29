"""Plot Phase 1 lens-map diagnostic buffers."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def plot_lens_map(*, input_path: Path, out: Path) -> None:
    """Render capture mask and Hamiltonian residual panels from an HDF5 lens map."""

    with h5py.File(input_path, "r") as handle:
        alpha = handle["alpha"][...]
        beta = handle["beta"][...]
        event_code = handle["event_code"][...]
        h_max_abs = handle["h_max_abs"][...]
        capture_code = int(handle["event_code"].attrs["code_capture"])
        a = float(handle.attrs["a"])
        inclination_deg = float(handle.attrs["inclination_deg"])

    capture_mask = event_code == capture_code
    finite_h = np.where(np.isfinite(h_max_abs), h_max_abs, np.nan)
    log_h = np.log10(np.maximum(finite_h, 1.0e-16))
    extent = [float(alpha[0]), float(alpha[-1]), float(beta[0]), float(beta[-1])]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    fig.suptitle(f"Phase 1 lens map: a={a:.3g}, i={inclination_deg:.3g} deg")

    mask_image = axes[0].imshow(
        capture_mask.astype(np.float64),
        origin="lower",
        extent=extent,
        cmap="gray_r",
        interpolation="nearest",
    )
    axes[0].set_title("Capture mask")
    axes[0].set_xlabel("alpha / M")
    axes[0].set_ylabel("beta / M")
    fig.colorbar(mask_image, ax=axes[0], label="capture=1")

    h_image = axes[1].imshow(
        log_h,
        origin="lower",
        extent=extent,
        cmap="viridis",
        interpolation="nearest",
    )
    axes[1].set_title("Hamiltonian residual")
    axes[1].set_xlabel("alpha / M")
    axes[1].set_ylabel("beta / M")
    fig.colorbar(h_image, ax=axes[1], label="log10 max |H|")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, dest="input_path")
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    plot_lens_map(input_path=args.input_path, out=args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
