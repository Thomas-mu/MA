"""Freeze the new test contract only after hardware-free integration checks pass."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    from controlled_airflow_contract import PHASES
    from prepare_pilot_dataset import EXPECTED_SENSOR
    import controlled_airflow_test as evaluation
    import independent_normal_test as independent
    import pilot_method_comparison as pilot

    assert not (BASE / "protocol.json").exists()
    suites = ET.parse(BASE / "software_tests.xml").getroot().findall("testsuite")
    assert suites and sum(int(s.attrib["tests"]) for s in suites) >= 103
    assert all(int(s.attrib[k]) == 0 for s in suites for k in ("failures", "errors", "skipped"))
    assert evaluation.build_windows is independent.build_windows
    assert evaluation.summarize_quality is independent.summarize_quality
    previous_base = ROOT / "results/upright_v4_independent_normal_20260911_133047"
    previous = json.loads((previous_base / "protocol.json").read_text())
    old_parity = json.loads((previous_base / "training_test_preprocessing_parity.json").read_text())
    assert old_parity["float64_window_centering_then_float32_then_frozen_scaler_exact"] is True
    assert sha(ROOT / "src/independent_normal_test.py") == old_parity["evaluator_sha256"]
    for path, digest in previous["implementation_sha256"].items():
        assert sha(path) == digest, path
    bundle_dir = Path(previous["frozen_bundle"]["directory"])
    pilot.load_bundle(bundle_dir)
    assert sha(bundle_dir / "pilot_bundle.json") == evaluation.FROZEN_BUNDLE_SHA256
    inventory = json.loads((BASE / "preservation_inventory.json").read_text())["files"]
    assert all((ROOT / path).is_file() and sha(ROOT / path) == digest for path, digest in inventory.items())
    csv_paths = sorted(str((ROOT / path).resolve()) for path in inventory if path.endswith(".csv"))
    sources = [
        "src/controlled_airflow_contract.py", "src/run_controlled_airflow_test.py",
        "src/controlled_airflow_test.py", "src/independent_normal_test.py",
        "src/pilot_method_comparison.py", "src/prepare_pilot_dataset.py",
        "src/common_comparison.py", "src/adxl345.py", "src/collect_real_data.py", "src/fan_pwm.py",
    ]
    prior_zero = previous_base / "normal_test_03_session.json"
    protocol = {
        "schema_version": 1, "purpose": "controlled_airflow_test", "protocol_id": BASE.name,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_at_monotonic_ns": time.monotonic_ns(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "frozen_bundle": previous["frozen_bundle"], "mounting_id": previous["mounting_id"],
        "mounting": previous["mounting"], "sensor": EXPECTED_SENSOR,
        "selection_seconds_since_pwm_command": [180, 300], "window_size": 128, "step_size": 128,
        "pwm_percent": 75, "pwm_frequency_hz": 25000, "duration_s": 300,
        "additional_off_after_release_s": 60, "planned_runs": PHASES,
        "data_directory": str(ROOT / "data" / BASE.name),
        "evaluator_sha256": sha(ROOT / "src/controlled_airflow_test.py"),
        "implementation_sha256": {str(ROOT / path): sha(ROOT / path) for path in sources},
        "excluded_recordings": {"csv_paths": csv_paths, "csv_sha256": [sha(path) for path in csv_paths],
                                "recording_ids": [Path(path).stem for path in csv_paths]},
        "exclusion_inventory_source": str(BASE / "preservation_inventory.json"),
        "exclusion_inventory_sha256": sha(BASE / "preservation_inventory.json"),
        "first_previous_zero_reference": {"session": str(prior_zero), "sha256": sha(prior_zero)},
        "first_ready_confirmation_pending": True,
        "readiness_rule": "Fresh explicit per-phase readiness; no deadline or automatic retry. Manual changes only supply disconnected, rotor stopped, fan and sensor fixed.",
        "no_automatic_restarts": True, "no_model_or_scaler_fit": True,
        "no_threshold_or_interval_changes": True,
        "phase_conditions": {"normal_before": {"state": "normal", "label": 0},
                             "airflow_modified": {"state": "airflow_modified", "label": 1},
                             "normal_after": {"state": "normal", "label": 0}},
        "label_1_meaning": "Controlled altered airflow, not a verified defect",
        "geometry_plan": {"path": str(BASE / "geometry_plan.json"), "sha256": sha(BASE / "geometry_plan.json")},
        "actual_plate_geometry": None, "rpm_measured": None,
        "quality_policy": previous["quality_policy"],
        "metrics_contract": "Normal phases: false alarms/valid normal windows. Altered phase: alarms/valid altered-state windows, not defect recall. Invalid excluded from denominators, never NORMAL; no F1 or general detection claims.",
        "physical_rms": "60 consecutive [5k,5k+5) host-time blocks since PWM command; each axis mean removed within block in Float64; vector sqrt(mean(sum(axis_ac**2))); late comparison [180,300).",
        "total_off_definition": "Previous recorded zero-command completion to next start-command invocation; no mechanical stop or continuous waveform measurement.",
        "software_tests": {"path": str(BASE / "software_tests.xml"), "sha256": sha(BASE / "software_tests.xml"),
                           "passed": sum(int(s.attrib["tests"]) for s in suites)},
        "human_protocol_sha256": sha(BASE / "test_protocol.md"),
    }
    # Mounting observations persist; this new sequence is not yet ready by implication.
    with (BASE / "protocol.json").open("x") as handle:
        json.dump(protocol, handle, indent=2, ensure_ascii=False, allow_nan=False)
    with (BASE / "protocol.sha256").open("x") as handle:
        handle.write(sha(BASE / "protocol.json") + "\n")
    evaluation.load_protocol(BASE / "protocol.json")
    parity = {"verified_utc": datetime.now(timezone.utc).isoformat(),
              "new_evaluator_uses_identical_build_windows_function": True,
              "training_parity_source": str(previous_base / "training_test_preprocessing_parity.json"),
              "training_parity_source_sha256": sha(previous_base / "training_test_preprocessing_parity.json"),
              "original_training_and_validation_parity": old_parity,
              "shared_helpers_and_frozen_package_unchanged": True,
              "new_synthetic_integration_tests_passed": protocol["software_tests"]["passed"],
              "old_sources_are_not_new_test_data": True}
    with (BASE / "preprocessing_parity.json").open("x") as handle:
        json.dump(parity, handle, indent=2, ensure_ascii=False)
    print(json.dumps({"protocol": str(BASE / "protocol.json"), "sha256": sha(BASE / "protocol.json"),
                      "excluded_csv_count": len(csv_paths), "software_tests_passed": protocol["software_tests"]["passed"],
                      "hardware_started": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
