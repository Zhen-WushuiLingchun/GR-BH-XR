"""Metric provider backed by audited ADM snapshot volumes."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path

import numpy as np

from ..dynamic_types import MetricSample
from ..nr_snapshot import ADMSnapshotLevel, NRADMSnapshot, load_nr_snapshot
from ..types import FloatArray


@dataclass(frozen=True)
class ADMInterpolationProvenance:
    level_id: int | None
    time_indices: tuple[int, int] | None
    spatial_cell: tuple[int, int, int] | None
    metric_sample: MetricSample


@dataclass(frozen=True)
class ADMMetricSnapshotProvider:
    snapshot: NRADMSnapshot
    _levels_by_priority: tuple[ADMSnapshotLevel, ...] = field(
        init=False, repr=False
    )
    _valid_lower: np.ndarray = field(init=False, repr=False)
    _valid_upper: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        levels = tuple(
            sorted(
                self.snapshot.levels,
                key=lambda level: (float(np.prod(level.spacing)), -level.level_id),
            )
        )
        object.__setattr__(self, "_levels_by_priority", levels)
        object.__setattr__(
            self, "_valid_lower", np.stack([level.valid_lower for level in levels])
        )
        object.__setattr__(
            self, "_valid_upper", np.stack([level.valid_upper for level in levels])
        )

    @classmethod
    def from_hdf5(
        cls, path: Path | str, *, verify_checksums: bool = True
    ) -> "ADMMetricSnapshotProvider":
        return cls(load_nr_snapshot(path, verify_checksums=verify_checksums))

    @property
    def source_revision(self) -> str:
        producer = self.snapshot.metadata["producer"]
        return f"{producer['name']}@{producer['commit']}:{self.snapshot.metadata['formulation']}"

    def sample(self, t: float, x: FloatArray) -> MetricSample:
        return self.sample_with_provenance(t, x).metric_sample

    def sample_with_provenance(
        self, t: float, x: FloatArray
    ) -> ADMInterpolationProvenance:
        xyz = np.asarray(x, dtype=np.float64)
        if xyz.shape != (3,) or not np.all(np.isfinite(xyz)) or not math.isfinite(t):
            raise ValueError("t and x must be finite with x.shape==(3,).")
        bracket = _time_bracket(self.snapshot.times, float(t))
        if bracket is None:
            return ADMInterpolationProvenance(
                None, None, None, self._outside_sample(float(t), xyz)
            )
        time0, time1, time_weight = bracket
        selection = self._select_level(xyz)
        if selection is None:
            return ADMInterpolationProvenance(
                None, (time0, time1), None, self._outside_sample(float(t), xyz)
            )
        level, cell, weights = selection

        alpha0, d_alpha0 = _trilinear(level.lapse[time0], level, cell, weights)
        alpha1, d_alpha1 = _trilinear(level.lapse[time1], level, cell, weights)
        beta0, d_beta0 = _trilinear(level.shift[time0], level, cell, weights)
        beta1, d_beta1 = _trilinear(level.shift[time1], level, cell, weights)
        gamma0, d_gamma0 = _trilinear(level.gamma_cov[time0], level, cell, weights)
        gamma1, d_gamma1 = _trilinear(level.gamma_cov[time1], level, cell, weights)

        dt = float(self.snapshot.times[time1] - self.snapshot.times[time0])
        alpha = float(_lerp(alpha0, alpha1, time_weight))
        beta = np.asarray(_lerp(beta0, beta1, time_weight), dtype=np.float64)
        gamma = np.asarray(_lerp(gamma0, gamma1, time_weight), dtype=np.float64)
        d_alpha = np.empty(4, dtype=np.float64)
        d_beta = np.empty((4, 3), dtype=np.float64)
        d_gamma = np.empty((4, 3, 3), dtype=np.float64)
        d_alpha[0] = float((alpha1 - alpha0) / dt)
        d_beta[0] = (beta1 - beta0) / dt
        d_gamma[0] = (gamma1 - gamma0) / dt
        d_alpha[1:4] = _lerp(d_alpha0, d_alpha1, time_weight)
        d_beta[1:4] = _lerp(d_beta0, d_beta1, time_weight)
        d_gamma[1:4] = _lerp(d_gamma0, d_gamma1, time_weight)

        spatial_error = float(
            _lerp(
                level.spatial_error_bound[time0],
                level.spatial_error_bound[time1],
                time_weight,
            )
        )
        interpolation_error = spatial_error + float(
            self.snapshot.temporal_error_bound[time0]
        )
        try:
            g_cov, g_inv, d_g_inv, gamma_inv = _metric_from_adm_with_derivatives(
                alpha, beta, gamma, d_alpha, d_beta, d_gamma
            )
        except (ValueError, np.linalg.LinAlgError):
            metric_sample = self._invalid_sample(float(t), xyz, interpolation_error)
        else:
            metric_sample = MetricSample(
                t=float(t),
                x=xyz,
                g_cov=g_cov,
                g_inv=g_inv,
                d_g_inv=d_g_inv,
                lapse=alpha,
                shift=beta,
                gamma_cov=gamma,
                gamma_inv=gamma_inv,
                validity="valid",
                evidence_label="nr_snapshot",
                source_revision=self.source_revision,
                interpolation_error=interpolation_error,
            )
        return ADMInterpolationProvenance(
            level.level_id, (time0, time1), cell, metric_sample
        )

    def _select_level(
        self, xyz: np.ndarray
    ) -> tuple[ADMSnapshotLevel, tuple[int, int, int], np.ndarray] | None:
        candidates = np.flatnonzero(
            np.all(xyz >= self._valid_lower, axis=1)
            & np.all(xyz <= self._valid_upper, axis=1)
        )
        for index in candidates:
            level = self._levels_by_priority[int(index)]
            coordinate = (xyz - level.origin) / level.spacing
            shape = np.asarray(level.grid_shape)
            if np.any(coordinate < 0.0) or np.any(coordinate > shape - 1):
                continue
            cell_array = np.floor(coordinate).astype(int)
            cell_array = np.minimum(cell_array, shape - 2)
            if np.any(cell_array < 0) or np.any(cell_array + 1 >= shape):
                continue
            weights = coordinate - cell_array
            return level, tuple(int(value) for value in cell_array), weights
        return None

    def _outside_sample(self, t: float, xyz: np.ndarray) -> MetricSample:
        return _empty_sample(t, xyz, "outside_domain", self.source_revision, 0.0)

    def _invalid_sample(
        self, t: float, xyz: np.ndarray, interpolation_error: float
    ) -> MetricSample:
        return _empty_sample(
            t, xyz, "invalid", self.source_revision, interpolation_error
        )


def _time_bracket(
    times: np.ndarray, t: float
) -> tuple[int, int, float] | None:
    if t < times[0] or t > times[-1]:
        return None
    index = int(np.searchsorted(times, t, side="right") - 1)
    index = min(max(index, 0), times.size - 2)
    dt = float(times[index + 1] - times[index])
    weight = (t - float(times[index])) / dt
    return index, index + 1, float(np.clip(weight, 0.0, 1.0))


def _lerp(left: np.ndarray | float, right: np.ndarray | float, weight: float):
    return (1.0 - weight) * left + weight * right


def _trilinear(
    values: np.ndarray,
    level: ADMSnapshotLevel,
    cell: tuple[int, int, int],
    weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return value and exact piecewise-linear spatial derivatives."""

    trailing_shape = values.shape[3:]
    result = np.zeros(trailing_shape, dtype=np.float64)
    derivatives = np.zeros((3,) + trailing_shape, dtype=np.float64)
    i0, j0, k0 = cell
    for ox in (0, 1):
        wx = weights[0] if ox else 1.0 - weights[0]
        for oy in (0, 1):
            wy = weights[1] if oy else 1.0 - weights[1]
            for oz in (0, 1):
                wz = weights[2] if oz else 1.0 - weights[2]
                corner = np.asarray(values[i0 + ox, j0 + oy, k0 + oz])
                result += wx * wy * wz * corner
                derivatives[0] += (
                    (1.0 if ox else -1.0)
                    * wy
                    * wz
                    / level.spacing[0]
                    * corner
                )
                derivatives[1] += (
                    wx
                    * (1.0 if oy else -1.0)
                    * wz
                    / level.spacing[1]
                    * corner
                )
                derivatives[2] += (
                    wx
                    * wy
                    * (1.0 if oz else -1.0)
                    / level.spacing[2]
                    * corner
                )
    return result, derivatives


def _metric_from_adm_with_derivatives(
    lapse: float,
    shift: np.ndarray,
    gamma_cov: np.ndarray,
    d_lapse: np.ndarray,
    d_shift: np.ndarray,
    d_gamma_cov: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not math.isfinite(lapse) or lapse <= 0.0:
        raise ValueError("interpolated lapse must be positive.")
    gamma_cov = 0.5 * (gamma_cov + gamma_cov.T)
    if np.min(np.linalg.eigvalsh(gamma_cov)) <= 0.0:
        raise ValueError("interpolated spatial metric is not positive definite.")
    gamma_inv = np.linalg.inv(gamma_cov)
    shift_cov = gamma_cov @ shift
    lapse_inv_sq = 1.0 / (lapse * lapse)

    g_cov = np.empty((4, 4), dtype=np.float64)
    g_cov[0, 0] = -lapse * lapse + float(shift @ shift_cov)
    g_cov[0, 1:4] = shift_cov
    g_cov[1:4, 0] = shift_cov
    g_cov[1:4, 1:4] = gamma_cov

    g_inv = np.empty((4, 4), dtype=np.float64)
    g_inv[0, 0] = -lapse_inv_sq
    g_inv[0, 1:4] = lapse_inv_sq * shift
    g_inv[1:4, 0] = g_inv[0, 1:4]
    g_inv[1:4, 1:4] = gamma_inv - lapse_inv_sq * np.outer(shift, shift)

    derivatives = np.empty((4, 4, 4), dtype=np.float64)
    for mu in range(4):
        d_q = -2.0 * d_lapse[mu] / (lapse**3)
        d_gamma_inv = -gamma_inv @ d_gamma_cov[mu] @ gamma_inv
        derivative = np.empty((4, 4), dtype=np.float64)
        derivative[0, 0] = -d_q
        derivative[0, 1:4] = d_q * shift + lapse_inv_sq * d_shift[mu]
        derivative[1:4, 0] = derivative[0, 1:4]
        derivative[1:4, 1:4] = d_gamma_inv - (
            d_q * np.outer(shift, shift)
            + lapse_inv_sq
            * (np.outer(d_shift[mu], shift) + np.outer(shift, d_shift[mu]))
        )
        derivatives[mu] = derivative
    return g_cov, g_inv, derivatives, gamma_inv


def _empty_sample(
    t: float,
    xyz: np.ndarray,
    validity: str,
    source_revision: str,
    interpolation_error: float,
) -> MetricSample:
    nan44 = np.full((4, 4), np.nan)
    nan33 = np.full((3, 3), np.nan)
    return MetricSample(
        t=t,
        x=xyz,
        g_cov=nan44,
        g_inv=nan44.copy(),
        d_g_inv=np.full((4, 4, 4), np.nan),
        lapse=math.nan,
        shift=np.full(3, np.nan),
        gamma_cov=nan33,
        gamma_inv=nan33.copy(),
        validity=validity,  # type: ignore[arg-type]
        evidence_label="nr_snapshot",
        source_revision=source_revision,
        interpolation_error=interpolation_error,
    )
