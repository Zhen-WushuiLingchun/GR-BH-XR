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
