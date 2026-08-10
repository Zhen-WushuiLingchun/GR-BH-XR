from gr_bh_xr.validate_bbh_spin import run_validation


def test_generic_spin_validation_smoke_passes() -> None:
    result = run_validation()
    assert result["pass"] is True
    assert result["evidence_label"] == "physics_approximation"
    assert result["provider"].endswith("spinning-circular-v1")
