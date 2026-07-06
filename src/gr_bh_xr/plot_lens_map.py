"""Plot Phase 1 lens-map diagnostic buffers."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402


def plot_lens_map(*, input_path: Path | str, out: Path | str) -> None:
    """Render capture mask and Hamiltonian residual panels from an HDF5 lens map."""

    input_path = Path(input_path)
    out = Path(out)
    with h5py.File(input_path, "r") as handle:
        alpha = handle["alpha"][...]
        beta = handle["beta"][...]
        event_code = handle["event_code"][...]
        h_max_abs = handle["h_max_abs"][...]
        a = float(handle.attrs["a"])
        inclination_deg = float(handle.attrs["inclination_deg"])

    log_h = np.full_like(h_max_abs, np.nan, dtype=np.float64)
    finite = np.isfinite(h_max_abs)
    log_h[finite] = np.log10(np.maximum(h_max_abs[finite], 1.0e-16))
    extent = [float(alpha[0]), float(alpha[-1]), float(beta[0]), float(beta[-1])]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), constrained_layout=True)
    fig.suptitle(f"Phase 1 lens map: a={a:.3g}, i={inclination_deg:.3g} deg")

    event_cmap = ListedColormap(["black", "white", "#2b6cb0", "#f59e0b"])
    event_norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], event_cmap.N)
    mask_image = axes[0].imshow(
        event_code,
        origin="lower",
        extent=extent,
        cmap=event_cmap,
        norm=event_norm,
        interpolation="nearest",
    )
    axes[0].set_title("Event class")
    axes[0].set_xlabel("alpha / M")
    axes[0].set_ylabel("beta / M")
    event_bar = fig.colorbar(mask_image, ax=axes[0], ticks=[0, 1, 2, 3])
    event_bar.ax.set_yticklabels(["capture", "escape", "disk", "invalid"])

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
