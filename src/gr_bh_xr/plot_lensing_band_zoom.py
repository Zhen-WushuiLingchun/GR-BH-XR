"""Plot a zoomed critical/lensing-band diagnostic from a CPU lens map."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402


def plot_lensing_band_zoom(*, input_path: Path | str, out: Path | str) -> None:
    """Render image-order and winding diagnostics near a critical curve."""

    input_path = Path(input_path)
    out = Path(out)
    with h5py.File(input_path, "r") as handle:
        alpha = handle["alpha"][...]
        beta = handle["beta"][...]
        event_code = handle["event_code"][...]
        image_order = handle["image_order"][...]
        winding = handle["azimuthal_winding"][...]
        min_r = handle["min_r"][...]
        a = float(handle.attrs["a"])
        inclination_deg = float(handle.attrs["inclination_deg"])

    extent = [float(alpha[0]), float(alpha[-1]), float(beta[0]), float(beta[-1])]
    valid = event_code != 3
    order_plot = np.where(valid, image_order, np.nan)
    winding_plot = np.where(valid, winding, np.nan)
    min_r_plot = np.where(valid, min_r, np.nan)
    max_order = int(np.nanmax(order_plot)) if np.any(np.isfinite(order_plot)) else 0

    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.8), constrained_layout=True)
    fig.suptitle(
        f"Lensing-band zoom: a={a:.3g}, i={inclination_deg:.3g} deg; "
        "order=floor(2 |Delta phi| / 2pi)"
    )

    colors = ["#1f2937", "#2563eb", "#7c3aed", "#db2777", "#f97316", "#facc15"]
    if max_order + 1 > len(colors):
        colors = colors + ["#fde68a"] * (max_order + 1 - len(colors))
    cmap = ListedColormap(colors[: max_order + 1])
    bounds = np.arange(-0.5, max_order + 1.5, 1.0)
    norm = BoundaryNorm(bounds, cmap.N)
    order_image = axes[0].imshow(
        order_plot,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap=cmap,
        norm=norm,
    )
    axes[0].set_title("Image-order proxy")
    axes[0].set_xlabel("alpha / M")
    axes[0].set_ylabel("beta / M")
    fig.colorbar(order_image, ax=axes[0], ticks=np.arange(0, max_order + 1))

    winding_image = axes[1].imshow(
        winding_plot,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap="magma",
    )
    axes[1].set_title("Azimuthal winding")
    axes[1].set_xlabel("alpha / M")
    axes[1].set_ylabel("beta / M")
    fig.colorbar(winding_image, ax=axes[1], label="|Delta phi| / 2pi")

    min_r_image = axes[2].imshow(
        min_r_plot,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap="viridis_r",
    )
    axes[2].set_title("Minimum BL radius")
    axes[2].set_xlabel("alpha / M")
    axes[2].set_ylabel("beta / M")
    fig.colorbar(min_r_image, ax=axes[2], label="min r / M")

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
    plot_lensing_band_zoom(input_path=args.input_path, out=args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
