"""Explicit operator conditions for the new frozen v4 airflow pilot.

This module validates recorded statements; it does not measure physical safety,
geometry, rotor motion, electrical waveforms, or rotational speed.
"""
import math

PHASES = ["normal_before", "airflow_modified", "normal_after"]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def conditions(phase):
    check(phase in PHASES, "Unknown airflow-test phase")
    return ("airflow_modified", 1) if phase == "airflow_modified" else ("normal", 0)


def validate_plate_geometry(geometry):
    check(isinstance(geometry, dict), "Actual operator-reported plate geometry missing")
    check(geometry.get("source") == "operator_report", "Geometry source must be explicit")
    for key, target in (("width_mm", 120), ("height_mm", 120), ("distance_mm", 100)):
        value = geometry.get(key)
        check(type(value) in (int, float) and math.isfinite(value) and value == target,
              f"Reported {key} must match planned {target}; clarify deviations before starting")
    check(geometry.get("distance_reference") == "outlet_frame_plane_to_nearest_plate_face",
          "Distance reference planes missing or different")
    evidence = geometry.get("outlet_identification")
    check(isinstance(evidence, str) and len(evidence.strip()) >= 4 and
          evidence.strip().lower() not in ("unknown", "unbekannt", "nicht geprüft", "not checked"),
          "Outlet identification observation missing")
    for key in ("parallel_to_outlet", "centered_on_outlet", "separate_stable_holder", "no_contact"):
        check(geometry.get(key) is True, f"Plate condition not confirmed: {key}")
    check(geometry.get("independently_measured") is False,
          "Operator report must not be represented as an independent measurement")


def validate_release_conditions(release, phase):
    conditions(phase)
    for key in ("ready", "external_supply_connected", "mechanical_standstill_confirmed", "mounting_unchanged"):
        check(release.get(key) is True, f"Current release condition missing: {key}")
    if phase == "airflow_modified":
        check(release.get("plate_present") is True and release.get("plate_absent") is not True,
              "Modified phase requires plate present")
        validate_plate_geometry(release.get("plate_geometry"))
    else:
        check(release.get("plate_absent") is True and release.get("plate_present") is not True,
              "Normal phase requires plate absent")
        check(release.get("plate_geometry") is None, "Normal phase must not claim a present plate geometry")
    if phase != "normal_before":
        for key in ("manual_change_power_disconnected", "no_fan_sensor_movement"):
            check(release.get(key) is True, f"Manual change condition missing: {key}")
