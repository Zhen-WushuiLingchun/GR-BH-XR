"""Plot Luminet-style thin-disk transfer diagnostics from CPU buffers."""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def plot_disk_transfer(
    *,
    input_path: Path | str,
    out: Path | str,
    contour_count: int = 8,
) -> dict[str, object]:
    """Render direct/secondary equal-radius curves from a disk-transfer HDF5 file."""

    input_path = Path(input_path)
    out = Path(out)
    if contour_count < 2:
        raise ValueError("contour_count must be at least 2.")

    with h5py.File(input_path, "r") as handle:
        alpha = handle["alpha"][...]
        beta = handle["beta"][...]
        disk_r = handle["disk_r_m"][...]
        disk_g = handle["disk_g_m"][...]
        a = float(handle.attrs["a"])
        inclination_deg = float(handle.attrs["inclination_deg"])
        r_in = float(handle.attrs["r_in"])
        r_out = float(handle.attrs["r_out"])
        schema = str(handle.attrs["schema"])

    if disk_r.ndim != 3:
        raise ValueError("disk_r_m must have shape (max_order, grid, grid).")

    max_order = disk_r.shape[0]
    visual_beta = -beta[::-1]
    visual_disk_r = disk_r[:, ::-1, :]
    visual_disk_g = disk_g[:, ::-1, :]
    extent = [
        float(alpha[0]),
        float(alpha[-1]),
        float(visual_beta[0]),
        float(visual_beta[-1]),
    ]
    levels = np.linspace(r_in, r_out, contour_count)
    order0 = (
        visual_disk_r[0] if max_order >= 1 else np.full((len(visual_beta), len(alpha)), np.nan)
    )
    order1 = visual_disk_r[1] if max_order >= 2 else np.full_like(order0, np.nan)
    g0 = visual_disk_g[0] if max_order >= 1 else np.full_like(order0, np.nan)

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), constrained_layout=True)
    fig.suptitle(
        f"Thin-disk transfer diagnostic: a={a:.3g}, i={inclination_deg:.3g} deg; "
        f"schema={schema}"
    )

    _plot_equal_radius_panel(
        axes[0],
        alpha,
        visual_beta,
        order0,
        levels,
        title="m=0 direct image: equal r_m",
    )
    _plot_equal_radius_panel(
        axes[1],
        alpha,
        visual_beta,
        order1,
        levels,
        title="m=1 secondary image: equal r_m",
    )

    g_plot = np.where(np.isfinite(g0), g0, np.nan)
    g_image = axes[2].imshow(
        g_plot,
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap="coolwarm",
    )
    axes[2].set_title("m=0 redshift factor g")
    axes[2].set_xlabel("alpha / M")
    axes[2].set_ylabel("visual beta / M (up = - solver beta)")
    fig.colorbar(g_image, ax=axes[2], label="g")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)

    return {
        "out": str(out),
        "schema": schema,
        "max_order": int(max_order),
        "valid_by_order": [
            int(np.count_nonzero(np.isfinite(disk_r[order]))) for order in range(max_order)
        ],
        "levels": [float(value) for value in levels],
        "visual_beta_flipped": True,
    }


def _plot_equal_radius_panel(
    axis,
    alpha: np.ndarray,
    beta: np.ndarray,
    disk_r: np.ndarray,
    levels: np.ndarray,
    *,
    title: str,
) -> None:
    extent = [float(alpha[0]), float(alpha[-1]), float(beta[0]), float(beta[-1])]
    valid = np.isfinite(disk_r)
    axis.imshow(
        valid.astype(float),
        origin="lower",
        extent=extent,
        interpolation="nearest",
        cmap="Greys",
        alpha=0.20,
        vmin=0.0,
        vmax=1.0,
    )
    finite = disk_r[np.isfinite(disk_r)]
    if finite.size:
        usable_levels = levels[(levels >= np.nanmin(finite)) & (levels <= np.nanmax(finite))]
        if usable_levels.size >= 2:
            contour = axis.contour(alpha, beta, disk_r, levels=usable_levels, cmap="viridis")
            axis.clabel(contour, inline=True, fontsize=7, fmt="%.1f")
    axis.set_title(title)
    axis.set_xlabel("alpha / M")
    axis.set_ylabel("visual beta / M (up = - solver beta)")
    axis.set_aspect("equal", adjustable="box")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, dest="input_path")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--contours", type=int, default=8)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = plot_disk_transfer(
        input_path=args.input_path,
        out=args.out,
        contour_count=args.contours,
    )
    print(f"wrote {summary['out']}")


if __name__ == "__main__":
    main()
