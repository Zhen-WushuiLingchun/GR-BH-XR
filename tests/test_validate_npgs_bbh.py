from pathlib import Path

import numpy as np

from gr_bh_xr.validate_npgs_bbh import (
    _audit_gradient_refinement,
    _expected_native_camera_direction,
    _event_boundary_mask,
    _sample_indices,
)


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"


def test_dynamic_bbh_native_path_integrates_all_canonical_momenta() -> None:
    common = (NPGS / "Sources/Engine/Shaders/BlackHole_common.glsl").read_text(
        encoding="utf-8"
    )
    provider = (NPGS / "Sources/Engine/Shaders/Common/MetricBBH.glsl").read_text(
        encoding="utf-8"
    )
    application = (NPGS / "Sources/Program/Application.cpp").read_text(
        encoding="utf-8"
    )

    for token in (
        "TraceBbhRay",
        "DynamicMetricRhs",
        "metricSample.DGInverseT",
        "derivative.P = -0.5 * vec4",
        "DynamicDiagnostics",
    ):
        assert token in common
    assert "MetricBbhInverseDerivative(X, 3)" in (
        NPGS / "Sources/Engine/Shaders/Common/MetricProvider.glsl"
    ).read_text(encoding="utf-8")
    assert "MetricBbhBoostedSchwarzschildTerm" in provider
    assert '"dynamic_metric_full_four_dimensional_hamiltonian"' in application
    assert '"stationary_conserved_quantity_claims_valid"' in application


def test_audit_gradient_refinement_uses_events_and_directions() -> None:
    events = np.ones((4, 5), dtype=np.int8)
    events[1:3, 2] = 0
    directions = np.zeros((4, 5, 3), dtype=np.float64)
    directions[..., 2] = 1.0
    directions[:, 4] = [0.1, 0.0, np.sqrt(0.99)]

    gradient, levels = _audit_gradient_refinement(
        events,
        directions,
        escape_code=1,
        boundary_pixels=0,
        direction_threshold_rad=0.02,
    )

    assert np.count_nonzero(levels == 2) > 0
    assert np.all(levels[:, 4] >= 1)
    assert np.nanmax(gradient) > 0.09
    assert np.all(np.isnan(gradient[events == 0]))


def test_sampling_and_boundary_masks_are_deterministic() -> None:
    indices = _sample_indices(81, 11)
    np.testing.assert_array_equal(indices, _sample_indices(81, 11))
    assert indices.size == 11
    assert np.all(np.diff(indices) > 0)

    events = np.ones((5, 5), dtype=np.int8)
    events[2, 2] = 0
    boundary = _event_boundary_mask(events, 1)
    assert boundary[2, 2]
    assert not boundary[0, 0]


def test_audit_camera_center_ray_uses_declared_basis() -> None:
    parameters = {
        "fov_deg": 30.0,
        "camera_right": [1.0, 0.0, 0.0],
        "camera_up": [0.0, np.sqrt(0.75), -0.5],
        "camera_back": [0.0, 0.5, np.sqrt(0.75)],
    }
    direction = _expected_native_camera_direction(
        row=16,
        col=16,
        height=33,
        width=33,
        parameters=parameters,
    )
    expected = -np.asarray(parameters["camera_back"])
    np.testing.assert_allclose(direction, expected, rtol=0.0, atol=2.0e-16)


def test_rank_two_woodbury_inverse_matches_direct_inverse() -> None:
    eta = np.diag([1.0, 1.0, 1.0, -1.0])
    l1 = np.array([0.6, 0.0, 0.8, 1.0])
    l2 = np.array([-0.2, np.sqrt(0.87), 0.3, 1.0])
    f1, f2 = 0.08, 0.05
    raised1 = eta @ l1
    raised2 = eta @ l2
    cross = float(l1 @ raised2)
    denominator = 1.0 - f1 * f2 * cross * cross
    correction = (
        f1 * np.outer(raised1, raised1)
        + f2 * np.outer(raised2, raised2)
        - f1
        * f2
        * cross
        * (np.outer(raised1, raised2) + np.outer(raised2, raised1))
    )
    woodbury = eta - correction / denominator
    direct = np.linalg.inv(eta + f1 * np.outer(l1, l1) + f2 * np.outer(l2, l2))

    np.testing.assert_allclose(woodbury, direct, rtol=0.0, atol=3.0e-16)
    shader = (NPGS / "Sources/Engine/Shaders/Common/MetricBBH.glsl").read_text(
        encoding="utf-8"
    )
    assert "Exact rank-two Woodbury inverse" in shader
    assert "return inverse(MetricBbhCovariantAt(X))" not in shader
