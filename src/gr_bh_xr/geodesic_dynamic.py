"""Full four-dimensional Hamiltonian reference tracing for dynamic metrics."""

from __future__ import annotations

from collections import Counter
import math

import numpy as np
from scipy.integrate import solve_ivp

from .dynamic_types import (
    DynamicEventSpec,
    DynamicRayDiagnostics,
    DynamicTraceConfig,
    MetricSample,
    TimeDependentMetricProvider,
)
from .metric_ks import ks_radius
from .types import MetricParams, RayState


class MetricDomainError(RuntimeError):
    """Raised when a ray leaves a provider's declared validity domain."""


def dynamic_hamiltonian(sample: MetricSample, p: np.ndarray) -> float:
    """Return ``H = 1/2 g^{mu nu} p_mu p_nu``."""

    momentum = np.asarray(p, dtype=np.float64)
    return float(0.5 * momentum @ sample.g_inv @ momentum)


def dynamic_hamiltonian_rhs(
    provider: TimeDependentMetricProvider, _lam: float, y: np.ndarray
) -> np.ndarray:
    """Evaluate the full canonical RHS, including ``dp_t``."""

    state = np.asarray(y, dtype=np.float64)
    if state.shape != (8,):
        raise ValueError("dynamic canonical state must have shape (8,).")
    x = state[:4]
    p = state[4:]
    sample = provider.sample(float(x[0]), x[1:4])
    if sample.validity != "valid":
        raise MetricDomainError(
            f"metric provider returned {sample.validity} at t={x[0]}, x={x[1:4].tolist()}"
        )
    dx = sample.g_inv @ p
    dp = np.empty(4, dtype=np.float64)
    for mu in range(4):
        dp[mu] = -0.5 * float(p @ sample.d_g_inv[mu] @ p)
    return np.concatenate([dx, dp])


def kerr_schild_radius_events(
    params: MetricParams, *, capture_radius: float, escape_radius: float
) -> tuple[DynamicEventSpec, DynamicEventSpec]:
    """Build caller-owned KS radius events for stationary zero regression."""

    if capture_radius <= 0.0 or escape_radius <= capture_radius:
        raise ValueError("radius events require 0 < capture_radius < escape_radius.")

    def capture(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return ks_radius(params, x[1:4]) - capture_radius

    def escape(_lam: float, x: np.ndarray, _p: np.ndarray) -> float:
        return ks_radius(params, x[1:4]) - escape_radius

    return (
        DynamicEventSpec("capture", capture, direction=-1.0, provenance="ks_radius"),
        DynamicEventSpec("escape", escape, direction=1.0, provenance="ks_radius"),
    )


def trace_dynamic_state(
    provider: TimeDependentMetricProvider,
    state: RayState,
    config: DynamicTraceConfig | None = None,
) -> DynamicRayDiagnostics:
    """Trace an explicitly initialized ray through a generic metric provider."""

    cfg = config or DynamicTraceConfig()
    x0 = np.asarray(state.x, dtype=np.float64)
    p0 = np.asarray(state.p, dtype=np.float64)
    if x0.shape != (4,) or p0.shape != (4,):
        raise ValueError("RayState x and p must each have shape (4,).")
    y0 = np.concatenate([x0, p0])
    last_state = y0.copy()
    last_lambda = 0.0
    validity_counts: Counter[str] = Counter()
    interpolation_error_max = 0.0

    def sampled_rhs(lam: float, y: np.ndarray) -> np.ndarray:
        nonlocal last_state, last_lambda, interpolation_error_max
        last_state = np.asarray(y, dtype=np.float64).copy()
        last_lambda = float(lam)
        sample = provider.sample(float(y[0]), np.asarray(y[1:4], dtype=np.float64))
        validity_counts[sample.validity] += 1
        interpolation_error_max = max(interpolation_error_max, sample.interpolation_error)
        if sample.validity != "valid":
            raise MetricDomainError(
                f"metric provider returned {sample.validity} at t={y[0]}, x={y[1:4].tolist()}"
            )
        x = np.asarray(y[:4], dtype=np.float64)
        p = np.asarray(y[4:], dtype=np.float64)
        dx = sample.g_inv @ p
        dp = np.empty(4, dtype=np.float64)
        for mu in range(4):
            dp[mu] = -0.5 * float(p @ sample.d_g_inv[mu] @ p)
        return np.concatenate([dx, dp])

    scipy_events = []
    for spec in cfg.events:
        def event(lam: float, y: np.ndarray, *, _spec: DynamicEventSpec = spec) -> float:
            return float(_spec.function(lam, y[:4], y[4:]))

        event.terminal = spec.terminal  # type: ignore[attr-defined]
        event.direction = spec.direction  # type: ignore[attr-defined]
        scipy_events.append(event)

    try:
        solution = solve_ivp(
            sampled_rhs,
            (0.0, cfg.max_lambda),
            y0,
            method="DOP853",
            rtol=cfg.rtol,
            atol=cfg.atol,
            max_step=cfg.max_step,
            events=scipy_events or None,
            dense_output=True,
        )
    except Exception as exc:
        return _dynamic_diagnostics(
            provider,
            np.vstack([y0, last_state]),
            last_lambda,
            event="invalid",
            event_provenance="metric_provider",
            failure_reason="metric_or_solver_exception",
            message=str(exc),
            validity_counts=validity_counts,
            interpolation_error_max=interpolation_error_max,
        )

    event_name = "budget_exhaustion"
    provenance = "integrator_budget"
    if solution.success:
        event_times_by_spec = solution.t_events if solution.t_events is not None else ()
        terminal_hits = [
            (float(event_times[-1]), spec)
            for spec, event_times in zip(cfg.events, event_times_by_spec)
            if spec.terminal and event_times.size
        ]
        if terminal_hits:
            _, hit_spec = min(terminal_hits, key=lambda item: abs(item[0] - float(solution.t[-1])))
            event_name = hit_spec.name
            provenance = hit_spec.provenance
    else:
        event_name = "invalid"
        provenance = "scipy_dop853"

    failure_reason = "none" if solution.success else "solver_failure"
    return _dynamic_diagnostics(
        provider,
        solution.y.T,
        float(solution.t[-1]),
        event=event_name,
        event_provenance=provenance,
        failure_reason=failure_reason,
        message=solution.message,
        validity_counts=validity_counts,
        interpolation_error_max=interpolation_error_max,
    )


def _dynamic_diagnostics(
    provider: TimeDependentMetricProvider,
    states: np.ndarray,
    lambda_end: float,
    *,
    event: str,
    event_provenance: str,
    failure_reason: str,
    message: str,
    validity_counts: Counter[str],
    interpolation_error_max: float,
) -> DynamicRayDiagnostics:
    h_values: list[float] = []
    evidence_label = "unknown"
    source_revision = "unknown"
    for row in states:
        try:
            sample = provider.sample(float(row[0]), row[1:4])
            if sample.validity != "valid":
                continue
            h_values.append(dynamic_hamiltonian(sample, row[4:]))
            evidence_label = sample.evidence_label
            source_revision = sample.source_revision
        except Exception:
            continue
    finite_h = np.asarray(h_values, dtype=np.float64)
    h_initial = float(finite_h[0]) if finite_h.size else math.nan
    h_final = float(finite_h[-1]) if finite_h.size else math.nan
    h_max_abs = float(np.max(np.abs(finite_h))) if finite_h.size else math.nan
    return DynamicRayDiagnostics(
        event=event,
        event_provenance=event_provenance,
        failure_reason=failure_reason,
        message=message,
        h_initial=h_initial,
        h_final=h_final,
        h_max_abs=h_max_abs,
        lambda_end=float(lambda_end),
        steps=int(states.shape[0]),
        final_x=np.asarray(states[-1, :4], dtype=np.float64),
        final_p=np.asarray(states[-1, 4:], dtype=np.float64),
        p_t_initial=float(states[0, 4]),
        p_t_final=float(states[-1, 4]),
        provider_valid_samples=int(validity_counts.get("valid", 0)),
        provider_invalid_samples=int(
            validity_counts.get("outside_domain", 0) + validity_counts.get("invalid", 0)
        ),
        interpolation_error_max=float(interpolation_error_max),
        metric_evidence_label=evidence_label,
        metric_source_revision=source_revision,
    )
