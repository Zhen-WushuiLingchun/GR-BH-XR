import math

import pytest

from gr_bh_xr.validate_ks_finite_lens import (
    einstein_angle_point_lens,
    schwarzschild_second_order_ring_angle,
)


def test_einstein_angle_point_lens_matches_geometric_unit_formula():
    theta_e = einstein_angle_point_lens(M=1.0, D_l=10000.0, D_ls=5000.0)

    assert abs(theta_e * theta_e - 4.0 * 5000.0 / (10000.0 * 15000.0)) < 1.0e-18


def test_einstein_angle_point_lens_rejects_nonphysical_distances():
    with pytest.raises(ValueError):
        einstein_angle_point_lens(M=1.0, D_l=0.0, D_ls=5000.0)
    with pytest.raises(ValueError):
        einstein_angle_point_lens(M=-1.0, D_l=10000.0, D_ls=5000.0)


def test_schwarzschild_second_order_ring_angle_uses_standard_deflection_coefficient():
    theta_e = einstein_angle_point_lens(M=1.0, D_l=10000.0, D_ls=5000.0)
    theta_2 = schwarzschild_second_order_ring_angle(M=1.0, D_l=10000.0, D_ls=5000.0)
    expected_rel = (15.0 * math.pi / 32.0) / (10000.0 * theta_e)

    assert (theta_2 - theta_e) / theta_e == pytest.approx(expected_rel)
