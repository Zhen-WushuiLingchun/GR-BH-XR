import pytest

from gr_bh_xr.validate_npgs_stereo_performance import (
    parse_stereo_log,
    summarize_stereo_performance,
)


def _log(*, invalid_pair: bool = False) -> list[str]:
    lines = [
        "NPGS_STEREO_CONFIG mode=sequential eye_width=1832 eye_height=1920 "
        "ipd_m=0.064 meters_per_M=1.0 disk=1 polarization=0 taa=per_eye_disabled",
    ]
    for pair in range(100):
        for eye in (0, 1):
            valid = 0 if invalid_pair and pair == 99 and eye == 1 else 1
            total = 4.0 + 0.1 * eye
            lines.append(
                f"NPGS_STEREO_GPU pair={pair} eye={eye} valid={valid} "
                f"total_ms={total} prepass_ms=1.0 composite_ms=2.0 "
                "post_ms=1.0 cpu_submit_ms=0.3"
            )
    return lines


def test_parser_and_pair_aggregation_use_two_complete_eyes() -> None:
    config, samples = parse_stereo_log(_log())
    result = summarize_stereo_performance(config, samples)

    assert result["schema"] == "gr-bh-xr.npgs.stereo-performance.v1"
    assert result["counts"]["complete_pairs"] == 100
    assert result["counts"]["valid_pairs"] == 100
    assert result["timing_ms"]["stereo_pair_gpu"]["p95"] == pytest.approx(8.1)
    assert result["gates"]["physics_render_72hz"] is True
    assert result["gates"]["physics_render_90hz"] is True
    assert result["gates"]["openxr_total_frame_90hz"] is None


def test_timestamp_gate_fails_closed_below_ninety_nine_percent() -> None:
    config, samples = parse_stereo_log(_log(invalid_pair=True)[:-3])
    result = summarize_stereo_performance(config, samples)
    assert result["valid_timestamp_ratio"] < 0.99
    assert result["gates"]["valid_timestamps"] is False
    assert result["gates"]["physics_render_72hz"] is False


def test_parser_rejects_conflicting_configuration() -> None:
    lines = _log()[:1]
    lines.append(
        "NPGS_STEREO_CONFIG mode=sequential eye_width=1600 eye_height=1728 "
        "ipd_m=0.064 meters_per_M=1.0 disk=1 polarization=0 taa=per_eye_disabled"
    )
    with pytest.raises(ValueError, match="conflicting"):
        parse_stereo_log(lines)


def test_parser_records_dynamic_bbh_timing_configuration() -> None:
    lines = _log()
    lines[0] = lines[0].replace(
        "taa=per_eye_disabled",
        "bbh=1 bbh_separation_M=20 bbh_phase_rad=0.25 "
        "bbh_time_M=4 bbh_worldtube_factor=2.4 taa=per_eye_disabled",
    )

    config, samples = parse_stereo_log(lines)
    result = summarize_stereo_performance(config, samples)

    assert config.bbh is True
    assert config.bbh_separation_M == pytest.approx(20.0)
    assert config.bbh_phase_rad == pytest.approx(0.25)
    assert config.bbh_time_M == pytest.approx(4.0)
    assert "does not solve the Einstein equations" in result["claim_boundary"]
