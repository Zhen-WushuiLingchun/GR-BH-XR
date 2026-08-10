import numpy as np

from gr_bh_xr.bbh_constraints import adm_constraint_sample
from gr_bh_xr.dynamic_metric import MinkowskiMetricProvider, StationaryKerrSchildProvider
from gr_bh_xr.metrics import SuperposedKerrSchildBBHProvider
from gr_bh_xr.types import MetricParams
from gr_bh_xr.validate_bbh_constraints import run_validation


def test_constraint_oracle_is_exact_for_minkowski() -> None:
    sample = adm_constraint_sample(
        MinkowskiMetricProvider(), 0.7, np.array([2.0, -3.0, 4.0]), stencil_step=0.1
    )
    assert sample.hamiltonian == 0.0
    np.testing.assert_array_equal(sample.momentum, 0.0)


def test_constraint_oracle_converges_for_exact_schwarzschild_ks() -> None:
    provider = StationaryKerrSchildProvider(MetricParams(M=1.0, a=0.0))
    point = np.array([4.0, 2.0, 1.0])
    coarse = adm_constraint_sample(provider, 0.0, point, stencil_step=0.08)
    fine = adm_constraint_sample(provider, 0.0, point, stencil_step=0.04)
    assert abs(fine.hamiltonian) < abs(coarse.hamiltonian) / 3.0
    assert fine.momentum_norm < coarse.momentum_norm / 3.0
    assert abs(fine.hamiltonian) < 2.0e-5
    assert fine.momentum_norm < 2.0e-6


def test_bbh_constraint_residual_is_finite_and_resolves_to_nonzero_plateau() -> None:
    provider = SuperposedKerrSchildBBHProvider()
    point = np.array([0.0, 3.0, 1.0])
    coarse = adm_constraint_sample(provider, 0.0, point, stencil_step=0.08)
    fine = adm_constraint_sample(provider, 0.0, point, stencil_step=0.04)
    assert np.isfinite(fine.hamiltonian)
    assert np.all(np.isfinite(fine.momentum))
    assert abs(fine.hamiltonian) > 1.0e-8
    relative_change = abs(fine.hamiltonian - coarse.hamiltonian) / abs(fine.hamiltonian)
    assert relative_change < 0.1


def test_bbh_constraint_validation_smoke_passes_and_persists_source_scales() -> None:
    result = run_validation(stencil_step=0.04)
    assert result["pass"] is True
    assert result["provider"]["evidence_label"] == "physics_approximation"
    assert result["threshold_provenance"]["far_reported_falloff"] == "about r^-4"
    assert len(result["samples"]) == 45
