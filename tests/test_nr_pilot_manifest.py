import importlib.util
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pytest


SCRIPT = Path(__file__).parents[1] / "nr" / "einstein_toolkit" / "export_manifest.py"
SPEC = importlib.util.spec_from_file_location("export_manifest", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PREPARE_SCRIPT = SCRIPT.parent / "prepare_pilot.py"
PREPARE_SPEC = importlib.util.spec_from_file_location("prepare_pilot", PREPARE_SCRIPT)
assert PREPARE_SPEC is not None and PREPARE_SPEC.loader is not None
PREPARE_MODULE = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_SPEC.loader.exec_module(PREPARE_MODULE)

ANALYZE_SCRIPT = SCRIPT.parent / "analyze_pilot.py"
ANALYZE_SPEC = importlib.util.spec_from_file_location("analyze_pilot", ANALYZE_SCRIPT)
assert ANALYZE_SPEC is not None and ANALYZE_SPEC.loader is not None
ANALYZE_MODULE = importlib.util.module_from_spec(ANALYZE_SPEC)
ANALYZE_SPEC.loader.exec_module(ANALYZE_MODULE)

CONVERTER_SCRIPT = SCRIPT.parent / "convert_openpmd_adm.py"
CONVERTER_SPEC = importlib.util.spec_from_file_location(
    "convert_openpmd_adm", CONVERTER_SCRIPT
)
assert CONVERTER_SPEC is not None and CONVERTER_SPEC.loader is not None
CONVERTER_MODULE = importlib.util.module_from_spec(CONVERTER_SPEC)
CONVERTER_SPEC.loader.exec_module(CONVERTER_MODULE)

PATCH_SCRIPT = SCRIPT.parent / "apply_release_patches.py"
PATCH_SPEC = importlib.util.spec_from_file_location("apply_release_patches", PATCH_SCRIPT)
assert PATCH_SPEC is not None and PATCH_SPEC.loader is not None
PATCH_MODULE = importlib.util.module_from_spec(PATCH_SPEC)
PATCH_SPEC.loader.exec_module(PATCH_MODULE)

CARPETX_ORDER_PATCH = (
    SCRIPT.parent / "patches" / "carpetx-driver-interpolate-per-call-order.patch"
)
AH_FINAL_THETA_PATCH = (
    SCRIPT.parent / "patches" / "ahfinderdirect-final-expansion-diagnostic.patch"
)
PILOT_PARFILE = SCRIPT.parent / "par" / "bbh_equal_mass.par"


def _write_spec(tmp_path: Path, *, omit: str | None = None) -> Path:
    artifacts = {}
    for label in ("low", "high"):
        role_map = {}
        for role in MODULE.REQUIRED_ARTIFACT_ROLES:
            if omit == role:
                continue
            path = tmp_path / f"{label}-{role}.dat"
            if role == "cactus_stdout":
                path.write_text("Cactus bounded pilot\nDone.\n", encoding="utf8")
            elif role == "adm_snapshot":
                with h5py.File(path, "w") as handle:
                    handle.attrs["schema"] = "gr-bh-xr.bbh.adm-snapshot.v1"
                    handle.create_dataset("times", data=[0.0, 2.0])
                    level = handle.create_group("levels").create_group("0")
                    level.create_dataset(
                        "extrinsic_curvature", data=[[[[[0.0] * 3] * 3]]]
                    )
            else:
                payload = {
                    "constraints": {
                        "finite": True,
                        "final_l2": {"hamiltonian": 0.1, "momentum": 0.2, "z4": 0.01},
                    },
                    "apparent_horizons": {
                        "finite": True,
                        "accepted_horizon_numbers": [1, 2],
                    },
                    "psi4": {"finite": True, "modes": [{"l": 2, "m": 2}]},
                    "ray_summary": {
                        "accepted": True,
                        "claim": "frozen_slice_two_resolution_nr_optical_convergence",
                        "full_dynamic_light_cone_claim": False,
                        "counts": {
                            "total": 18,
                            "resolved_pairs": 18,
                            "invalid_or_budget_pairs": 0,
                            "escape_direction_pairs": 16,
                        },
                        "event_agreement": 1.0,
                        "escape_direction_error_rad": {
                            "median": 0.0,
                            "rms": 0.0,
                            "max": 0.0,
                        },
                    },
                }[role]
                path.write_text(json.dumps(payload), encoding="utf8")
            role_map[role] = path.name
        artifacts[label] = role_map
    parfiles = {}
    for label, rho in (("low", 1), ("high", 2)):
        parfile = tmp_path / f"bbh-{label}.par"
        parfile.write_text(
            f"$rho = {rho}\nActiveThorns = \"CarpetX\"\n", encoding="utf8"
        )
        parfiles[label] = parfile
    release = json.loads(
        (SCRIPT.parent / "release_lock.json").read_text(encoding="utf8")
    )
    preflight = tmp_path / "linear-wave-preflight.log"
    preflight.write_text(
        "Success: 36 files compared, 15 differ in the last digits\n"
        "Number failed            -> 0\n"
        "Tests passed:\n"
        "  linear_wave_z4c (from CottonmouthZ4c4m)\n",
        encoding="utf8",
    )
    spec = {
        "release": release,
        "producer_preflight": preflight.name,
        "runs": [
            {
                "label": label,
                "resolution": resolution,
                "grid_spacing_M": spacing,
                "parfile": parfiles[label].name,
                "producer_command": f"cactus_{label}",
                "producer_executable_sha256": "2" * 64,
                "artifacts": artifacts[label],
            }
            for label, resolution, spacing in (("low", 1, 2.0), ("high", 2, 1.0))
        ],
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec), encoding="utf8")
    return path


def test_pilot_manifest_requires_and_hashes_two_resolution_evidence(tmp_path: Path) -> None:
    manifest = MODULE.build_pilot_manifest(_write_spec(tmp_path))
    assert manifest["accepted"]
    assert not manifest["full_nr_merger_claim"]
    assert manifest["validation"]["accepted"]
    assert manifest["validation"]["producer_preflight_passed"]
    assert manifest["producer_preflight"]["validation"] == {
        "test": "linear_wave_z4c",
        "files_compared": 36,
        "last_digit_differences": 15,
        "failures": 0,
        "accepted": True,
    }
    assert manifest["claims"]["bounded_two_resolution_nr_pipeline_pilot"]
    assert [run["resolution"] for run in manifest["runs"]] == [1.0, 2.0]
    for run in manifest["runs"]:
        assert set(run["artifacts"]) == set(MODULE.REQUIRED_ARTIFACT_ROLES)
        assert all(len(item["sha256"]) == 64 for item in run["artifacts"].values())


def test_pilot_manifest_fails_closed_when_constraint_history_is_missing(tmp_path: Path) -> None:
    with pytest.raises(MODULE.PilotManifestError) as error:
        MODULE.build_pilot_manifest(_write_spec(tmp_path, omit="constraints"))
    assert error.value.reason_code == "missing_evidence_artifact"


def test_pilot_manifest_requires_successful_producer_preflight(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    spec = json.loads(spec_path.read_text(encoding="utf8"))
    preflight = tmp_path / spec["producer_preflight"]
    preflight.write_text(
        "Success: 36 files compared, 15 differ in the last digits\n"
        "Number failed -> 1\n",
        encoding="utf8",
    )

    manifest = MODULE.build_pilot_manifest(spec_path)
    assert not manifest["accepted"]
    assert not manifest["validation"]["producer_preflight_passed"]


def test_pilot_manifest_rejects_well_formed_but_unpinned_component_commit(
    tmp_path: Path,
) -> None:
    spec_path = _write_spec(tmp_path)
    spec = json.loads(spec_path.read_text(encoding="utf8"))
    spec["release"]["component_commits"]["SpacetimeX"] = "1" * 40
    spec_path.write_text(json.dumps(spec), encoding="utf8")

    with pytest.raises(MODULE.PilotManifestError) as error:
        MODULE.build_pilot_manifest(spec_path)
    assert error.value.reason_code == "release_provenance_mismatch"


def test_pilot_manifest_does_not_accept_present_but_failed_evidence(
    tmp_path: Path,
) -> None:
    spec = _write_spec(tmp_path)
    failed = tmp_path / "high-apparent_horizons.dat"
    payload = json.loads(failed.read_text(encoding="utf8"))
    payload["finite"] = False
    payload["accepted_horizon_numbers"] = []
    failed.write_text(json.dumps(payload), encoding="utf8")

    manifest = MODULE.build_pilot_manifest(spec)
    assert not manifest["accepted"]
    assert not manifest["claims"]["bounded_two_resolution_nr_pipeline_pilot"]
    assert not manifest["runs"][1]["validation"]["gates"][
        "two_individual_apparent_horizons"
    ]


def test_pilot_manifest_requires_extrinsic_curvature_volume(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path)
    with h5py.File(tmp_path / "high-adm_snapshot.dat", "r+") as handle:
        del handle["levels/0/extrinsic_curvature"]

    manifest = MODULE.build_pilot_manifest(spec)
    assert not manifest["accepted"]
    assert not manifest["runs"][1]["validation"]["gates"][
        "compatible_adm_volume"
    ]


def test_pilot_manifest_recomputes_ray_gate_instead_of_trusting_accept_flag(
    tmp_path: Path,
) -> None:
    spec = _write_spec(tmp_path)
    rays = tmp_path / "high-ray_summary.dat"
    payload = json.loads(rays.read_text(encoding="utf8"))
    payload["event_agreement"] = 0.5
    rays.write_text(json.dumps(payload), encoding="utf8")

    manifest = MODULE.build_pilot_manifest(spec)
    assert not manifest["accepted"]
    assert not manifest["runs"][1]["validation"]["gates"]["fixed_camera_ray_gate"]


def test_pilot_materializer_changes_only_resolution_assignment(tmp_path: Path) -> None:
    template = tmp_path / "template.par"
    template.write_text("$rho = 1\nphysics = fixed\n", encoding="utf8")

    manifest_path = PREPARE_MODULE.materialize_pilot(template, tmp_path / "runs")
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    low = Path(manifest["runs"][0]["parfile"]).read_text(encoding="utf8")
    high = Path(manifest["runs"][1]["parfile"]).read_text(encoding="utf8")

    assert low == "$rho = 1\nphysics = fixed\n"
    assert high == "$rho = 2\nphysics = fixed\n"
    assert low.replace("$rho = 1", "$rho = 2") == high


def test_ahfinder_interpolation_contract_reaches_release_kernel() -> None:
    patch = CARPETX_ORDER_PATCH.read_text(encoding="utf8")
    parfile = PILOT_PARFILE.read_text(encoding="utf8")

    assert 'geometry_interpolator_pars = "order=3 ' in parfile
    assert "CarpetX::interpolation_order = 3" in parfile
    assert "N_zones_per_right_angle[1] = 8 * $rho" in parfile
    assert "N_zones_per_right_angle[2] = 8 * $rho" in parfile
    assert "const CCTK_INT requested_order" in patch
    assert "switch (requested_order)" in patch
    assert "DECLARE_CCTK_PARAMETERS;" in patch
    assert "order, allowed_boundaries, resultptrs" in patch


def test_bounded_pilot_uses_fixed_boxes_and_independent_horizon_tracks() -> None:
    parfile = PILOT_PARFILE.read_text(encoding="utf8")

    assert "CarpetX::regrid_every = 0" in parfile
    assert "$nlevels = 7" in parfile
    assert "$final_time = 1.0" in parfile
    assert "0.75, 0.375" in parfile
    assert "\n  PunctureTracker\n" not in parfile
    assert "PunctureTracker::" not in parfile
    assert "AHFinderDirect::N_horizons = 2" in parfile


def test_ahfinder_success_log_contains_full_precision_expansion_residual() -> None:
    patch = AH_FINAL_THETA_PATCH.read_text(encoding="utf8")

    assert "found_this_horizon && ! I_am_pretracking" in patch
    assert "verbose_info.print_physics_details" in patch
    assert "final Theta rms-norm %.17g, infinity-norm %.17g" in patch


def test_release_lock_hashes_every_local_et_patch() -> None:
    lock = json.loads((SCRIPT.parent / "release_lock.json").read_text(encoding="utf8"))
    patches = sorted((SCRIPT.parent / "patches").glob("*.patch"))

    assert sorted(lock["local_patches"]) == [path.name for path in patches]
    for path in patches:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == lock["local_patches"][path.name]

    assert hashlib.sha256(
        (SCRIPT.parent / "optionlists" / "hypatia-release.cfg").read_bytes()
    ).hexdigest() == lock["build_optionlist_sha256"]
    assert hashlib.sha256(
        (SCRIPT.parent / "thornlists" / "hypatia-carpetx.th").read_bytes()
    ).hexdigest() == lock["build_thornlist_sha256"]


def test_release_patch_targets_cover_every_locked_patch() -> None:
    lock = json.loads((SCRIPT.parent / "release_lock.json").read_text(encoding="utf8"))

    assert set(PATCH_MODULE.PATCH_TARGETS) == set(lock["local_patches"])
    assert PATCH_MODULE.PATCH_TARGETS[
        "carpetx-driver-interpolate-per-call-order.patch"
    ] == ("repos/CarpetX", "CarpetX")


def _write_norm(path: Path, field: str, values: list[float]) -> None:
    path.write_text(
        "# 1:iteration\t2:time\t3:test::"
        + field
        + ".L2norm\n"
        + "\n".join(
            f"{index}\t{float(index):.1f}\t{value:.9e}"
            for index, value in enumerate(values)
        )
        + "\n",
        encoding="utf8",
    )


def test_pilot_analyzer_extracts_numerical_evidence(tmp_path: Path) -> None:
    data = tmp_path / "run"
    norms = data / "norms"
    norms.mkdir(parents=True)
    _write_norm(norms / "cottonmouthz4c4m-hamcons.tsv", "hamcons", [0.2, 0.1])
    _write_norm(norms / "cottonmouthz4c4m-momcons.tsv", "momconsu0", [0.3, 0.2])
    _write_norm(norms / "cottonmouthz4c4m-ztcons.tsv", "ztconsu0", [0.1, 0.05])
    (data / "puncturetracker-pt_loc.it000001.tsv").write_text(
        "# 1:iteration\t2:time\t3:pt_loc_x[0]\t4:pt_loc_x[1]"
        "\t5:pt_loc_y[0]\t6:pt_loc_y[1]\t7:pt_loc_z[0]\t8:pt_loc_z[1]\n"
        "1\t1.0\t3.0\t-3.0\t0.1\t-0.1\t0.0\t0.0\n",
        encoding="utf8",
    )
    (data / "mp_NP_Psi4_l2_m2_r20.00.asc").write_text(
        "0.0 1.0e-4 2.0e-4\n1.0 2.0e-4 3.0e-4\n", encoding="utf8"
    )
    bp5 = data / "run.it00000001.bp5"
    bp5.mkdir()
    (bp5 / "md.idx").write_bytes(b"openpmd")
    stdout = tmp_path / "cactus.out"
    stdout.write_text(
        "INFO (AHFinderX): iter: 1\n"
        "INFO (AHFinderX):     pos=[3.0,0.1,0.0]\n"
        "INFO (AHFinderX):     r_avg=0.29   r_min=0.28 r_max=0.30\n"
        "INFO (AHFinderX):     Theta_avg=0   Theta_maxabs=0.0005\n",
        encoding="utf8",
    )

    result = ANALYZE_MODULE.analyze_run(
        data,
        stdout,
        tmp_path / "evidence",
        label="low",
        resolution=1.0,
        grid_spacing_M=0.125,
    )
    assert result["producer_gate_passed"]
    constraints = json.loads(Path(result["artifacts"]["constraints"]).read_text())
    horizons = json.loads(
        Path(result["artifacts"]["apparent_horizons"]).read_text()
    )
    psi4 = json.loads(Path(result["artifacts"]["psi4"]).read_text())
    assert constraints["final_l2"]["hamiltonian"] == pytest.approx(0.1)
    assert horizons["accepted_solution_count"] == 1
    assert horizons["center_to_puncture_max_M"] == pytest.approx(0.0)
    assert psi4["bounded_pilot_note"].startswith(
        "The 1M evolution is shorter than the light travel time to r=20M"
    )


class _Chunk:
    def __init__(self, offset, extent):
        self.offset = offset
        self.extent = extent


class _FakeOpenPmdComponent:
    def __init__(self, chunks):
        self._chunks = chunks

    def available_chunks(self):
        return self._chunks

    def load_chunk(self, offset, extent):
        value = float(offset[0] + 10 * offset[1] + 100 * offset[2])
        return np.full(tuple(extent), value)


class _FakeOpenPmdSeries:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


def test_openpmd_converter_chunk_bbox_requires_dense_union() -> None:
    lower, upper = CONVERTER_MODULE._chunk_bbox(
        [_Chunk([2, 3, 4], [3, 2, 2]), _Chunk([5, 3, 4], [1, 2, 2])]
    )
    assert lower.tolist() == [2, 3, 4]
    assert upper.tolist() == [6, 5, 6]
    with pytest.raises(ValueError, match="contains holes"):
        CONVERTER_MODULE._chunk_bbox(
            [_Chunk([0, 0, 0], [1, 1, 1]), _Chunk([2, 0, 0], [1, 1, 1])]
        )


def test_openpmd_converter_preserves_disconnected_chunks_as_patches() -> None:
    series = _FakeOpenPmdSeries()
    component = _FakeOpenPmdComponent(
        [_Chunk([4, 0, 0], [2, 2, 2]), _Chunk([0, 0, 0], [2, 2, 2])]
    )
    patches = CONVERTER_MODULE._read_component_patches(series, component)

    assert series.flush_count == 1
    assert len(patches) == 2
    assert patches[0][1].tolist() == [0, 0, 0]
    assert patches[1][1].tolist() == [4, 0, 0]
    assert np.all(patches[0][0] == 0.0)
    assert np.all(patches[1][0] == 4.0)


def test_openpmd_converter_selects_nearest_containing_parent_patch() -> None:
    coarse_left = {
        "source_level_id": 0,
        "source_patch_index": 0,
        "origin": np.array([-8.0, -8.0, -8.0]),
        "spacing": np.ones(3),
        "shape": (17, 17, 17),
    }
    coarse_right = {
        "source_level_id": 0,
        "source_patch_index": 1,
        "origin": np.array([16.0, -8.0, -8.0]),
        "spacing": np.ones(3),
        "shape": (17, 17, 17),
    }
    child = {
        "source_level_id": 1,
        "source_patch_index": 0,
        "origin": np.array([-2.0, -2.0, -2.0]),
        "spacing": np.full(3, 0.5),
        "shape": (9, 9, 9),
    }

    assert (
        CONVERTER_MODULE._select_parent_level_id(
            child,
            [(0, 10, coarse_left), (0, 11, coarse_right)],
        )
        == 10
    )
    with pytest.raises(ValueError, match="no containing coarser parent"):
        CONVERTER_MODULE._select_parent_level_id(child, [(0, 11, coarse_right)])


def test_openpmd_converter_axis_permutation_is_explicit() -> None:
    assert CONVERTER_MODULE._axis_permutation(["z", "y", "x"]) == (2, 1, 0)
    with pytest.raises(ValueError, match="Cartesian"):
        CONVERTER_MODULE._axis_permutation(["r", "theta", "phi"])


def test_pilot_analyzer_parses_two_ahfinderdirect_horizons(tmp_path: Path) -> None:
    data = tmp_path / "run"
    data.mkdir()
    (data / "puncturetracker-pt_loc.it000000.tsv").write_text(
        "# 1:iteration\t2:time\t3:pt_loc_x[0]\t4:pt_loc_x[1]"
        "\t5:pt_loc_y[0]\t6:pt_loc_y[1]\t7:pt_loc_z[0]\t8:pt_loc_z[1]\n"
        "0\t0.0\t3.0\t-3.0\t0.0\t0.0\t0.0\t0.0\n",
        encoding="utf8",
    )
    stdout = tmp_path / "cactus.out"
    stdout.write_text(
        "INFO (AHFinderDirect):    Theta rms-norm 2.0e-10, infinity-norm 8.0e-10\n"
        "INFO (AHFinderDirect): AH 1/2: r=0.29 at (3.000000,0.000000,0.000000)\n"
        "INFO (AHFinderDirect): AH 1/2: area=3.1 m_irreducible=0.248\n"
        "INFO (AHFinderDirect):    Theta rms-norm 2.2e-10, infinity-norm 9.0e-10\n"
        "INFO (AHFinderDirect): AH 2/2: r=0.29 at (-3.000000,0.000000,0.000000)\n"
        "INFO (AHFinderDirect): AH 2/2: area=3.1 m_irreducible=0.248\n",
        encoding="utf8",
    )

    horizons = ANALYZE_MODULE.extract_horizons(data, stdout, 1.0e-3)
    assert horizons["finder"] == "SpacetimeX/AHFinderDirect"
    assert horizons["accepted_horizon_numbers"] == [1, 2]
    assert horizons["accepted_solution_count"] == 2
    assert horizons["center_to_puncture_max_M"] == 0.0
    assert horizons["finite"]


def test_pilot_analyzer_accepts_two_direct_horizons_without_puncture_tracker(
    tmp_path: Path,
) -> None:
    data = tmp_path / "run"
    data.mkdir()
    stdout = tmp_path / "cactus.out"
    stdout.write_text(
        "INFO (AHFinderDirect):    final Theta rms-norm 2.0e-10, infinity-norm 8.0e-10\n"
        "INFO (AHFinderDirect): AH 1/2: r=0.29 at (3.000000,0.000000,0.000000)\n"
        "INFO (AHFinderDirect): AH 1/2: area=3.1 m_irreducible=0.248\n"
        "INFO (AHFinderDirect):    final Theta rms-norm 2.2e-10, infinity-norm 9.0e-10\n"
        "INFO (AHFinderDirect): AH 2/2: r=0.29 at (-3.000000,0.000000,0.000000)\n"
        "INFO (AHFinderDirect): AH 2/2: area=3.1 m_irreducible=0.248\n",
        encoding="utf8",
    )

    horizons = ANALYZE_MODULE.extract_horizons(data, stdout, 1.0e-3)
    assert horizons["accepted_horizon_numbers"] == [1, 2]
    assert horizons["punctures"] == {"samples": [], "finite": False}
    assert horizons["center_to_puncture_max_M"] is None
    assert horizons["finite"]
