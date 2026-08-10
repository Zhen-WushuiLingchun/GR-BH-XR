from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_current_status_is_linked_as_canonical_source() -> None:
    status = (ROOT / "docs" / "current_status.md").read_text(encoding="utf8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf8")
    readme = (ROOT / "README.md").read_text(encoding="utf8")

    assert "canonical status summary" in status
    assert "docs/current_status.md" in agents
    assert "docs/current_status.md" in readme
    assert "NPGS Native Migration" in status
    assert "unaccepted" in status.lower()


def test_unity_readme_distinguishes_baked_and_live_tracing() -> None:
    unity_readme = (ROOT / "xr" / "unity_frontend" / "README.md").read_text(
        encoding="utf8"
    )

    assert "The baked playback path does not perform real-time geodesic integration" in unity_readme
    assert "Live tracing (Task 9)" in unity_readme
    assert "The package does not perform real-time geodesic integration" not in unity_readme


def test_bbh_dynamic_track_has_versioned_plan_and_fail_closed_status() -> None:
    plan_path = ROOT / "docs" / "plans" / "2026-08-10-bbh-dynamic-spacetime-xr.md"
    note_path = (
        ROOT
        / "references"
        / "source_notes"
        / "2026-08-10-bbh-dynamic-spacetime-foundations.md"
    )
    status = (ROOT / "docs" / "current_status.md").read_text(encoding="utf8")
    targets = (ROOT / "docs" / "validation_targets.md").read_text(encoding="utf8")
    plan = plan_path.read_text(encoding="utf8")
    note = note_path.read_text(encoding="utf8")

    assert plan_path.is_file()
    assert note_path.is_file()
    assert "ACTIVE_PLAN" in plan
    assert "no BBH implementation is accepted yet" in plan
    assert "real_time_metric_evaluation" in plan
    assert "nr_snapshot_truth" in plan
    assert "apparent horizons or explicit worldtubes" in plan
    assert "docs/plans/2026-08-10-bbh-dynamic-spacetime-xr.md" in status
    assert "implementation not started" in status
    assert "simulated stereo" in targets
    assert "both-invalid rays" in targets
    assert "waveform-only assets" in note


def test_bbh_foundation_sources_are_indexed_and_bibliographed() -> None:
    references = (ROOT / "references" / "references.md").read_text(encoding="utf8")
    bib = (ROOT / "references" / "references.bib").read_text(encoding="utf8")
    required_keys = {
        "bohn2015bbhAppearance",
        "vincent2012geodesic3p1",
        "vincent2011gyoto",
        "combi2021superposedMetric",
        "combi2026bbhMetricApproximation",
        "combiRessler2024bbhMetricCode",
        "baumgarte1998bssn",
        "campanelli2006movingPuncture",
        "pretorius2005bbhEvolution",
        "einsteinToolkit2026hypatia",
        "carpetx2026manual",
        "sxs2026waveformDocs",
        "ashtekar2004dynamicalHorizons",
        "angelil2015gwOptics",
        "cunha2018exactBinaryShadows",
    }

    for key in required_keys:
        assert key in references
        assert f"{{{key}," in bib

    code_review = (
        ROOT
        / "references"
        / "code_reviews"
        / "2026-08-10-combi-ressler-bbh-metric.md"
    ).read_text(encoding="utf8")
    equations = (ROOT / "docs" / "equations.md").read_text(encoding="utf8")
    assert "10.5281/zenodo.10841021" in code_review
    assert "ecc4d1268342520f29e4537d5f3ab183" in code_review
    assert "does **not** vendor" in code_review
    assert "dp_t / dlambda" in equations
    assert "Pi_i = p_i / (alpha p^0)" in equations
    assert "event horizon is" in equations.lower()
