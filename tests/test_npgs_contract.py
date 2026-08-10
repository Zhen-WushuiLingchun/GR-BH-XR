import copy

import pytest

from gr_bh_xr.npgs_contract import (
    COORDINATES,
    MR_FRAME_SCHEMA,
    Feature,
    GateStatus,
    accepted_features,
    feature_status,
    integration_manifest,
    validate_mr_frame_record,
    validate_native_integration_metadata,
)


def _metadata(*, charge: float = 0.0, disk: bool = True, polarization: bool = True):
    claims = {
        "shared_trace_ray": True,
        "disk_transfer_slots_valid": disk,
        "raw_hamiltonian_is_pre_projection": True,
    }
    if polarization:
        claims.update(
            camera_polarization_evidence_emitted=True,
            camera_polarization_model=(
                "complete Boyer-Lindquist Walker-Penrose scalar; "
                "emission/Stokes model not validated"
            ),
        )
    return {
        "parameters": {"M_internal": 0.5, "charge_Q_over_M": charge},
        "claims": claims,
        "canonical_state_contract": {
            "chart": "ingoing Cartesian Kerr-Schild",
            "component_order": ["x", "y", "z", "t"],
            "momentum_variance": "covariant",
            "spin_axis": "+y",
        },
    }


def _mr_record(*, coverage: str = "forward_camera_only"):
    return {
        "schema": MR_FRAME_SCHEMA,
        "sequence": 3,
        "capture_time_ns": 1_000,
        "receive_time_ns": 1_100,
        "native_image": 9,
        "fresh": True,
        "calibrated": True,
        "color_encoding": "srgb",
        "radiance_coverage": coverage,
        "camera_pose": {
            "position_m": [0.03, 1.62, -0.04],
            "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "intrinsics": {
            "fx": 900.0,
            "fy": 901.0,
            "cx": 640.0,
            "cy": 480.0,
            "width": 1280,
            "height": 960,
        },
    }


def test_reviewed_feature_matrix_keeps_claim_boundaries_explicit() -> None:
    assert feature_status(Feature.NEUTRAL_KERR_RAYS).status is GateStatus.ACCEPTED
    assert feature_status(Feature.NEUTRAL_KERR_NEWMAN_RAYS).status is GateStatus.ACCEPTED
    assert feature_status(Feature.KERR_DISK_TRANSFER).status is GateStatus.ACCEPTED
    assert feature_status(Feature.WALKER_PENROSE_GEOMETRY).status is GateStatus.ACCEPTED
    assert feature_status(Feature.STOKES_TRANSPORT).status is GateStatus.BLOCKED
    assert feature_status(Feature.CHARGED_DISK_PHYSICS).status is GateStatus.BLOCKED
    assert feature_status(Feature.MAXIMAL_EXTENSION_ASTROPHYSICS).status is GateStatus.VISUAL_ONLY
    assert feature_status(Feature.NATIVE_OPENXR).status is GateStatus.CANDIDATE
    assert feature_status(Feature.MR_CAMERA_PIXELS).status is GateStatus.BLOCKED


def test_native_coordinate_and_claim_contract_accepts_reviewed_kerr_slice() -> None:
    metadata = _metadata()
    validate_native_integration_metadata(metadata)

    assert accepted_features(metadata) == (
        Feature.NEUTRAL_KERR_RAYS,
        Feature.KERR_DISK_TRANSFER,
        Feature.WALKER_PENROSE_GEOMETRY,
    )
    assert COORDINATES.native_mass == 0.5


def test_native_contract_accepts_neutral_kn_but_rejects_charged_disk_claim() -> None:
    metadata = _metadata(charge=0.5, disk=False)
    validate_native_integration_metadata(metadata)
    assert accepted_features(metadata) == (
        Feature.NEUTRAL_KERR_NEWMAN_RAYS,
        Feature.WALKER_PENROSE_GEOMETRY,
    )

    metadata["claims"]["disk_transfer_slots_valid"] = True
    with pytest.raises(ValueError, match="charged-disk"):
        validate_native_integration_metadata(metadata)


@pytest.mark.parametrize(
    "claim",
    [
        "stokes_transport_valid",
        "charged_disk_physics_valid",
        "maximal_extension_astrophysics_valid",
        "native_openxr_valid",
        "mr_passthrough_camera_pixels_valid",
        "bbh_gravitational_waves_valid",
    ],
)
def test_native_contract_rejects_unaccepted_true_claims(claim: str) -> None:
    metadata = _metadata()
    metadata["claims"][claim] = True
    with pytest.raises(ValueError, match="overclaims"):
        validate_native_integration_metadata(metadata)


def test_native_contract_rejects_coordinate_or_mass_drift() -> None:
    metadata = _metadata()
    metadata["parameters"]["M_internal"] = 1.0
    with pytest.raises(ValueError, match="M_internal=0.5"):
        validate_native_integration_metadata(metadata)

    metadata = _metadata()
    metadata["canonical_state_contract"]["spin_axis"] = "+z"
    with pytest.raises(ValueError, match="spin_axis"):
        validate_native_integration_metadata(metadata)


def test_mr_frame_claim_is_bounded_by_measured_radiance_coverage() -> None:
    assert validate_mr_frame_record(_mr_record()) == "forward_camera_only"
    assert (
        validate_mr_frame_record(_mr_record(coverage="forward_camera_plus_cached_environment"))
        == "forward_camera_only"
    )
    assert (
        validate_mr_frame_record(_mr_record(coverage="calibrated_full_sphere"))
        == "calibrated_full_sphere"
    )


def test_mr_frame_rejects_placeholder_or_uncalibrated_input() -> None:
    for key, value in (("native_image", 0), ("fresh", False), ("calibrated", False)):
        record = _mr_record()
        record[key] = value
        with pytest.raises(ValueError):
            validate_mr_frame_record(record)


def test_mr_frame_rejects_missing_or_nonrigid_camera_pose() -> None:
    record = _mr_record()
    del record["camera_pose"]
    with pytest.raises(ValueError, match="camera_pose"):
        validate_mr_frame_record(record)

    record = _mr_record()
    record["camera_pose"]["orientation_xyzw"] = [0.0, 0.0, 0.0, 2.0]
    with pytest.raises(ValueError, match="unit normalized"):
        validate_mr_frame_record(record)


def test_mr_frame_validates_optional_depth_independently() -> None:
    record = _mr_record()
    record.update(
        has_depth=True,
        depth={
            "sequence": 7,
            "capture_time_ns": 1_005,
            "native_image": 11,
            "width": 320,
            "height": 320,
            "near_m": 0.2,
            "far_m": 8.0,
            "fresh": True,
            "calibrated": True,
            "depth_pose": {
                "position_m": [0.0, 1.6, 0.0],
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
        },
    )
    assert validate_mr_frame_record(record) == "forward_camera_only"

    record["depth"]["near_m"] = 9.0
    with pytest.raises(ValueError, match="depth range"):
        validate_mr_frame_record(record)


def test_integration_manifest_is_serializable_and_versioned() -> None:
    manifest = integration_manifest()
    assert manifest["schema"] == "gr-bh-xr.npgs.integration.v1"
    assert manifest["coordinates"]["component_order"] == ["x", "y", "z", "t"]
    assert manifest["features"]["native_openxr"]["status"] == "candidate"
