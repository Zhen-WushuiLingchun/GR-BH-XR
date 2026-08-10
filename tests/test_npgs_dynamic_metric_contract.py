from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPGS = ROOT / "runtime" / "NPGS" / "NPGS"


def test_native_metric_provider_contract_has_dynamic_audit_fields() -> None:
    interface = (
        NPGS / "Sources/Engine/Physics/Metric/IMetricProvider.h"
    ).read_text(encoding="utf-8")
    for token in (
        "FMetricSample", "Time", "Covariant", "Inverse", "PartialMuInverse",
        "Lapse", "Shift", "SpatialCovariant", "SpatialInverse", "Validity",
        "Evidence", "InterpolationError", "Sample(double MetricTime",
        "IsStationary", "SourceRevision",
    ):
        assert token in interface


def test_stationary_provider_exposes_analytic_derivatives_and_revision() -> None:
    implementation = (
        NPGS / "Sources/Engine/Physics/Metric/KerrStationaryProvider.cpp"
    ).read_text(encoding="utf-8")
    header = (
        NPGS / "Sources/Engine/Physics/Metric/KerrStationaryProvider.h"
    ).read_text(encoding="utf-8")
    assert "PartialMuInverse[Axis + 1]" in implementation
    assert "PartialMuInverse[0] = glm::dmat4(0.0)" in implementation
    assert "a^2+Q^2<=M^2" in implementation
    assert "npgs.kerr-newman-ks.v1" in header
    assert "return true" in header


def test_shader_routes_stationary_rhs_through_shared_provider() -> None:
    common = (
        NPGS / "Sources/Engine/Shaders/BlackHole_common.glsl"
    ).read_text(encoding="utf-8")
    provider = (
        NPGS / "Sources/Engine/Shaders/Common/MetricProvider.glsl"
    ).read_text(encoding="utf-8")
    assert '#include "Common/MetricProvider.glsl"' in common
    assert "return EvaluateStationaryMetricProviderRhs(" in common
    for token in (
        "MetricTime", "EvidenceLabel", "Validity", "SourceRevision", "Stationary",
        "DGInverseX", "DGInverseY", "DGInverseZ", "DGInverseT",
        "metricSample.DGInverseT = mat4(0.0)", "deriv.P = vec4(force, 0.0)",
    ):
        assert token in provider


def test_native_audit_records_metric_provider_provenance() -> None:
    application = (
        NPGS / "Sources/Program/Application.cpp"
    ).read_text(encoding="utf-8")
    for token in (
        'Metadata["metric_provider"]', '"kerr_newman_stationary"',
        '"npgs.kerr-newman-ks.v1"', '"metric_time"', '"stationary"',
        '"analytic_exact"', '"interpolation_error"',
        '"analytic partial_mu g_inverse',
    ):
        assert token in application


def test_visual_studio_project_compiles_native_metric_provider() -> None:
    project = (NPGS / "NPGS.vcxproj").read_text(encoding="utf-8")
    assert 'Physics\\Metric\\KerrStationaryProvider.cpp' in project
    assert 'Physics\\Metric\\IMetricProvider.h' in project
    assert 'Shaders\\Common\\MetricProvider.glsl' in project
