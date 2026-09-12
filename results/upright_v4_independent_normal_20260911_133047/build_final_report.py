#!/usr/bin/env python3
"""Create new descriptive report only after all three frozen normal tests exist.

No hardware access, model loading, fitting or inference. Existing artifacts are
read and verified; all outputs use exclusive creation. Standard library only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
METHODS = ("rms", "isolation_forest", "tflite_autoencoder")
NAMES = {"rms": "RMS", "isolation_forest": "Isolation Forest", "tflite_autoencoder": "TFLite-Autoencoder"}
PHASES = tuple(f"normal_test_{i:02d}" for i in range(1, 4))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def number(value, places=6):
    return "unbekannt" if value is None else f"{value:.{places}f}"


def percent(value):
    return "nicht bestimmbar (kein gültiges Fenster)" if value is None else f"{100 * value:.2f} %"


def local_time(value):
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Europe/Berlin")).isoformat(timespec="milliseconds")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows])


def metrics(rows):
    valid = [r for r in rows if r["decision"] in ("NORMAL", "ANOMALY")]
    check(all(r["decision"] in ("NORMAL", "ANOMALY", "INVALID") for r in rows), "Unknown decision")
    alarms = sum(r["decision"] == "ANOMALY" for r in valid)
    return {"total_windows": len(rows), "valid_windows": len(valid), "invalid_windows": len(rows) - len(valid),
            "false_alarms": alarms, "false_alarm_rate_among_valid_normal_windows": alarms / len(valid) if valid else None}


def main():
    outputs = [BASE / name for name in ("independent_normal_report.md", "descriptive_score_groups_30s.csv", "report_artifact_hashes.json")]
    check(not any(path.exists() for path in outputs), "Report output already exists; never overwrite")
    inventory = {}

    def verified(path, expected=None):
        path = Path(path).resolve()
        actual = digest(path)
        check(expected is None or actual == expected, f"Artifact hash mismatch: {path}")
        inventory[str(path)] = actual
        return path

    protocol_path = verified(BASE / "protocol.json", (BASE / "protocol.sha256").read_text().strip().split()[0])
    protocol = read(protocol_path)
    protocol_hash = digest(protocol_path)
    check(protocol["planned_runs"] == list(PHASES), "Unexpected run protocol")
    check(protocol["selection_seconds_since_pwm_command"] == [180, 300], "Interval changed")
    check(protocol["window_size"] == protocol["step_size"] == 128, "Window contract changed")
    bundle_dir = Path(protocol["frozen_bundle"]["directory"])
    bundle_path = verified(bundle_dir / "pilot_bundle.json", protocol["frozen_bundle"]["sha256"])
    bundle = read(bundle_path)
    for name, expected in bundle["artifact_sha256"].items():
        verified(bundle_dir / name, expected)
    for name, expected in protocol["implementation_sha256"].items():
        verified(name, expected)
    parity = read(verified(BASE / "training_test_preprocessing_parity.json"))
    check(parity["float64_window_centering_then_float32_then_frozen_scaler_exact"] is True, "Missing exact preprocessing parity")
    suites = ET.parse(verified(BASE / "software_tests.xml")).getroot().findall("testsuite")
    check(sum(int(s.attrib["tests"]) for s in suites) == 112, "Unexpected software-test count")
    check(all(int(s.attrib[k]) == 0 for s in suites for k in ("errors", "failures", "skipped")), "Software tests not fully passed")

    comparison = read(verified(BASE / "comparison/comparison.json"))
    check(comparison["whole_recordings"] == 3 and len(comparison["per_run"]) == 3, "Three complete evaluated runs required")
    check(comparison["normal_only"] is True and comparison["anomaly_performance_evaluated"] is False, "Normal-only contract missing")
    for name, expected in comparison["artifact_sha256"].items():
        verified(BASE / "comparison" / name, expected)

    summaries, sessions, all_rows, group_rows = [], [], [], []
    for index, phase in enumerate(PHASES, 1):
        folder = BASE / f"evaluation_{phase}"
        summary_path = verified(folder / "summary.json")
        summary = read(summary_path)
        check(summary["status"] == "evaluated_independent_normal_recording" and summary["phase"] == phase, "Missing complete evaluation")
        check(summary == comparison["per_run"][index - 1], "Comparison and single-run results differ")
        check(summary["protocol_sha256"] == protocol_hash, "Protocol mismatch")
        check(summary["frozen_bundle_sha256"] == digest(bundle_path), "Bundle mismatch")
        check(summary["models_changed"] is False and summary["scaler_fitted"] is False and summary["thresholds_changed"] is False, "Frozen contract changed")
        for kind in ("csv", "sidecar", "session"):
            verified(summary[kind], summary[kind + "_sha256"])
        for name, expected in summary["artifact_sha256"].items():
            verified(folder / name, expected)
        check(summary["csv_sha256"] not in protocol["excluded_recordings"]["csv_sha256"], "Historical source cannot become a test")
        check(summary["recording_id"] not in protocol["excluded_recordings"]["recording_ids"], "Historical recording ID")
        check(summary["csv"] not in protocol["excluded_recordings"]["csv_paths"], "Historical CSV path")
        session = read(summary["session"])
        check(session["status"] == "completed", "Incomplete session")
        final = session["final_readback"]
        check(final["pwm_configuration"]["configured_duty_percent"] == 0 and final["pwm_configuration"]["configured_frequency_hz"] == 25000 and final["pwm_mux_confirmed"] is True, "No final 0-percent PWM readback")
        verified(BASE / f"{phase}_release.json", session["user_release_sha256"])
        verified(session["fan_journal"])
        rows = read(folder / "scores.json")
        check(all(r["label"] == 0 and r["state"] == "normal" and r["phase"] == phase for r in rows), "Unexpected test label")
        summaries.append(summary)
        sessions.append(session)
        all_rows.extend(rows)
        for method in METHODS:
            chosen = [r for r in rows if r["method"] == method]
            check(metrics(chosen) == summary["metrics"][method], "Per-run metrics mismatch")
            check(all(r["threshold"] == bundle["thresholds"][method]["value"] for r in chosen), "Threshold mismatch")
            for start in (180, 210, 240, 270):
                grouped = [r for r in chosen if start <= (r["start_since_command_s"] + r["last_since_command_s"]) / 2 < start + 30]
                good = [r for r in grouped if r["decision"] in ("NORMAL", "ANOMALY")]
                values = [r["score"] for r in good]
                check(all(math.isfinite(v) for v in values), "Nonfinite valid score")
                group_rows.append({"phase": phase, "method": method, "start_s": start, "end_s_exclusive": start + 30,
                                   "window_assignment": "midpoint_of_first_and_last_host_sample_since_pwm_command",
                                   **metrics(grouped), "score_mean": statistics.mean(values) if values else None,
                                   "score_sample_sd": statistics.stdev(values) if len(values) > 1 else None,
                                   "score_min": min(values) if values else None, "score_max": max(values) if values else None,
                                   "frozen_threshold": bundle["thresholds"][method]["value"]})
    check(len({s["csv_sha256"] for s in summaries}) == len({s["recording_id"] for s in summaries}) == 3, "Independent recording identities not unique")
    for method in METHODS:
        check(metrics([r for r in all_rows if r["method"] == method]) == comparison["pooled"][method], "Pooled metrics mismatch")

    sections = ["# Unabhängige Normalitätsprüfung des eingefrorenen Modellpakets für Aufbau v4", "",
        "Drei separate Normalstarts ohne Platte wurden mit unveränderter Aufbauversion "
        f"`{protocol['mounting_id']}` aufgezeichnet und unabhängig vom Training ausgewertet. "
        "Die nachfolgend ausgewiesenen normalen Fehlalarme bleiben vollständig als Testergebnis erhalten. "
        "Dieser Bericht bewertet die Normalverträglichkeit des eingefrorenen Pilotpakets; er enthält keinen Nachweis der Erkennung veränderter Betriebszustände.", "",
        "## Vorab festgelegter Vergleich und Softwareprüfung", "",
        f"Das [Testprotokoll](test_protocol.md) wurde am {protocol['frozen_at_utc']} eingefroren, vor den drei Aufnahmen. "
        "Pro Start waren 300 Sekunden bei 75 % PWM und 25 kHz sowie 60 Sekunden zusätzliche Auszeit nach der jeweiligen Freigabe vorgesehen. "
        "Bewertet wird ausschließlich [180,300) Sekunden seit Aufruf des PWM-Stellbefehls. "
        "128 XYZ-Punkte je Fenster und Schrittweite 128 ergeben nicht überlappende Fenster, die keine Aufnahmegrenze überschreiten. "
        "Unvollständige Restfenster werden weder aufgefüllt noch als ungültige Modellfenster gezählt. "
        "Der vollständige Anlauf bleibt in den Rohdateien gespeichert; 180 Sekunden sind weiterhin eine vorläufige Einlaufzeit.", "",
        f"Die vorab eingefrorene Ausschlussliste enthält {len(protocol['excluded_recordings']['csv_paths'])} historische CSV-Pfade einschließlich der Trainings-, Validierungs- und bereits untersuchten Aufnahmen. "
        "Die drei neuen vollständigen Aufnahmen haben unterschiedliche IDs und Rohdatenhashes, stehen nicht in dieser Ausschlussliste und wurden erst nach dem Einfrieren erzeugt. "
        "Die Aufteilung erfolgt damit nach vollständigen Aufnahmen, nicht durch zufälliges Verteilen benachbarter Fenster.", "",
        "Vor Aufnahmebeginn bestanden 112 Softwaretests. Der [Paritätsnachweis](training_test_preprocessing_parity.json) "
        f"verglich {parity['training_windows']} Trainings- und {parity['validation_windows']} Validierungsfenster exakt mit dem Trainingsweg: "
        "achsenweise Mittelwertentfernung je 128er-Fenster in Float64, danach Float32 und Anwendung des gespeicherten Scalers. "
        "Die hierfür gelesenen alten Quellen dienten ausschließlich der Softwareprüfung und sind von den unabhängigen Tests ausgeschlossen. "
        "Alle drei Methoden erhalten wertgleiche standardisierte Eingaben. Modelle, Skalierung, Schwellen und Abschnittsauswahl wurden nicht angepasst. "
        "Der RMS-Methodenscore ist ein RMS des standardisierten Fensters und kein unskalierter physischer Vektor-AC-RMS in g.", "",
        table(["Methode", "Eingefrorene Schwelle"], [[NAMES[m], f"{bundle['thresholds'][m]['value']:.16g}"] for m in METHODS]), "",
        "## Durchführung, Aufbau und tatsächliche Zeitintervalle", "",
        "Der Lüfter blieb aufrecht an der festen v4-Position; der ADXL345 blieb mit zwei Schrauben am feststehenden äußeren Lüfterrahmen befestigt, bei schräger Platinenlage. "
        "Der bereits bestätigte sichere Aufbau und die angeschlossene externe 12-V-Versorgung wurden übernommen. "
        "Vor jedem Start lag eine neue Nutzerbestätigung des mechanischen Stillstands und eine Freigabe ausschließlich dieses Laufs vor. "
        "Es wurden keine Antworten während der Aufnahme, Antwortfristen oder automatischen Wiederholungsstarts verlangt. "
        "Die Erfassung hielt die Lüftersteuerung exklusiv; Erkennungsentscheidungen steuerten den Lüfter nicht.", "",
        table(["Lauf", "Freigabe, MESZ", "75-%-Befehlsaufruf, MESZ", "Erster XYZ-Punkt, MESZ (aus Hostzeit abgeleitet)", "0-%-Befehlsabschluss, MESZ"],
              [[i, local_time(s['user_release']['accepted_utc']), local_time(s['command_invocation_utc']), local_time(s['timing']['first_xyz_utc_estimate']), local_time(s['zero_command_completed_utc'])] for i, s in enumerate(sessions, 1)]), "",
        table(["Lauf", "Zusätzliche Auszeit ab Freigabe, s", "Gesamte Auszeit seit vorherigem 0-%-Befehlsabschluss, s", "Erster XYZ-Punkt nach Befehlsaufruf, ms", "Erster XYZ-Punkt nach Befehlsabschluss, ms", "Hostzeitspanne erster–letzter XYZ-Punkt, s"],
              [[i, number(s['additional_off_from_release_actual_s']), number(s['total_off_since_previous_zero_s']), number(1000*s['timing']['first_xyz_after_command_invocation_s']), number(1000*s['timing']['first_xyz_after_command_completion_s']), number(s['timing']['first_to_last_xyz_s'])] for i, s in enumerate(sessions, 1)]), "",
        "Die zusätzlichen Auszeiten umfassen die vorgesehenen 60 Sekunden und den anschließend gemessenen Softwareaufwand. "
        "Die gesamten Auszeiten waren nicht gleich; vor Lauf 1 ist die vollständige vorherige Auszeit unbekannt. "
        "Diese Intervalle beruhen auf monotoner Hostzeit zwischen Softwareereignissen, nicht auf gemessenen mechanischen Stopp- oder Anlaufzeitpunkten. "
        "Auch die angegebenen UTC/MESZ-Zeiten des ersten XYZ-Punkts sind aus Hostzeit abgeleitet. "
        "Der kleine Versatz zwischen Stellbefehl und erstem gelesenen Punkt bleibt dokumentiert; ein vollständig lückenlos abgebildeter Rotorstart wird nicht behauptet.", "",
        "## Datenqualität und Zeitbasis", "",
        "Unveränderte Sensorparameter: ADXL345, nominell 200 Hz, ±2 g, Full Resolution, 0,0039 g/LSB, FIFO-Stream, I²C-Bus 1 mit konfigurierten 100 kHz. "
        "Registerrücklesung: `0x2c=0x0b`, `0x31=0x08`, `0x2e=0x00`, `0x38=0x90`, `0x2d=0x08`. "
        "GPIO18 bezeichnet BCM GPIO18, physischen Pin 12, mit Pin-Funktion `PWM0_CHAN2`, PWM-Kanal 2 und 40.000 ns Periode. "
        "Die PWM-Konfiguration wurde zurückgelesen; elektrische Wellenform und tatsächliche Drehzahl wurden nicht gemessen.", ""]
    quality_fields = [("xyz_points", "Vollständige XYZ-Punkte", 0), ("individual_axis_values", "Einzelne Achsenwerte", 0),
                      ("nominal_sensor_odr_hz", "Nominelle Sensor-Abtastrate, Hz", 0), ("observed_xyz_per_second", "Beobachteter Durchsatz, XYZ/s", 6),
                      ("host_interval_p50_ms", "Host-Leseabstand Median, ms", 6), ("host_interval_p99_ms", "Host-Leseabstand 99. Perzentil, ms", 6),
                      ("host_interval_max_ms", "Host-Leseabstand Maximum, ms", 6), ("host_intervals_over_10ms", "Host-Leseabstände über 10 ms", 0),
                      ("host_intervals_over_160ms", "Host-Leseabstände über 160 ms", 0), ("read_duration_max_ms", "Maximale Sensor-Lesedauer, ms", 6),
                      ("fifo_depth_max", "Maximaler FIFO-Füllstand", 0), ("gap_flagged_xyz", "XYZ-Punkte mit Lückenflag", 0),
                      ("overrun_flagged_xyz", "XYZ-Punkte mit Überlaufflag", 0), ("saturated_flagged_xyz", "XYZ-Punkte mit Sättigungsflag", 0),
                      ("nonmonotonic_host_intervals", "Nichtmonotone Hostintervalle", 0), ("nonfinite_xyz_points", "Nichtendliche XYZ-Punkte", 0),
                      ("exact_lost_sensor_samples", "Exakte physische Sensorverluste", 0)]
    sections += [table(["Merkmal", "Lauf 1", "Lauf 2", "Lauf 3"], [[label] + [number(s['quality'][key], places) for s in summaries] for key, label, places in quality_fields]), "",
        "Der beobachtete Durchsatz wird als (N−1)/(Zeit des letzten minus Zeit des ersten Host-Leseabschlusses) berechnet. "
        "N zählt vollständige XYZ-Messpunkte; die Zahl einzelner Achsenwerte beträgt 3N. "
        "Der gegenüber nominell 200 Hz erhöhte Durchsatz ist ein Befund der Erfassung und keine nachgewiesene Umkonfiguration des Sensors. "
        "Die Software liest vollständige XYZ-Punkte aus dem FIFO und protokolliert monotone Host-Leseabschlüsse. "
        "FIFO-Abarbeitung und Hostplanung können ungleichmäßige Leseabstände verursachen, belegen jedoch nicht die Ursache der mittleren Ratendifferenz. "
        "Sensorwandlungstakt und Hostzeit wurden nicht unabhängig gegeneinander kalibriert. "
        "`sample_index / 200` ist nur eine nominelle Sensorzeitschätzung; es wurde weder auf 200 Hz umgerechnet noch neu abgetastet. "
        "Die tatsächliche Ursache der Rateabweichung und die exakte Zahl etwaiger physischer Verluste bleiben offen. "
        "Fehlende Flags sind kein Nachweis einer vollständig verlustfreien Wandlungsfolge.", "",
        table(["Lauf", "XYZ-Punkte in [180,300)", "Vollständige Modellfenster", "Nicht aufgefüllte Restpunkte"],
              [[i, s['quality']['selected_interval']['xyz_selected'], s['quality']['selected_interval']['full_model_windows'], s['quality']['selected_interval']['trailing_xyz_not_windowed']] for i, s in enumerate(summaries, 1)]), "",
        "## Fehlalarme unter normalen Testfenstern", "",
        "Fehlalarmrate = Anzahl als ANOMALY bewerteter normaler Fenster / Anzahl gültiger normaler Fenster. "
        "Ungültige Fenster zählen weder als NORMAL noch im Nenner. Die zusammengefasste Rate ist ein deskriptiver Fensteranteil. "
        "Die drei vollständigen Starts sind die Versuchsreplikate; die benachbarten Fenster sind keine unabhängigen Replikate.", ""]
    metric_rows = []
    for label, result in [(f"Lauf {i}", s['metrics']) for i, s in enumerate(summaries, 1)] + [("Zusammen, 3 Läufe", comparison['pooled'])]:
        for method in METHODS:
            m = result[method]
            metric_rows.append([label, NAMES[method], m['valid_windows'], m['invalid_windows'], m['false_alarms'], percent(m['false_alarm_rate_among_valid_normal_windows'])])
    sections += [table(["Lauf", "Methode", "Gültige Fenster", "Ungültige Fenster", "Fehlalarme", "Fehlalarmrate unter gültigen normalen Fenstern"], metric_rows), "",
        "![Scoreverläufe der drei Normalläufe mit eingefrorenen Schwellen](comparison/scores.png)", "",
        "[Grafik als PDF](comparison/scores.pdf) · [Maschinenlesbare Vergleichstabelle](comparison/comparison.csv)", "",
        "## Zeitliche Veränderungen innerhalb der Läufe und Unterschiede zwischen Starts", "",
        "Zur rein deskriptiven Prüfung werden die bereits bewerteten Fenster anhand der Mitte zwischen erstem und letztem Hostzeitstempel den vier 30-s-Gruppen "
        "[180,210), [210,240), [240,270) und [270,300) zugeordnet. Diese nachträgliche Zusammenfassung ändert weder die vorab gewählte Bewertungsstrecke "
        "noch Modellfenster oder Entscheidungen. Sie dient keiner Parameterwahl und keinem statistischen Signifikanztest. "
        "Die Tabelle enthält je Gruppe den Mittelwert der gültigen Scores; die [zusätzliche CSV](descriptive_score_groups_30s.csv) enthält auch Stichprobenstandardabweichung, Minima, Maxima, gültige/ungültige Fenster und Fehlalarme.", ""]
    trend_rows = []
    between_rows = []
    for method in METHODS:
        means = []
        for phase in PHASES:
            groups = [r for r in group_rows if r['phase'] == phase and r['method'] == method]
            delta = None if groups[0]['score_mean'] is None or groups[-1]['score_mean'] is None else groups[-1]['score_mean'] - groups[0]['score_mean']
            trend_rows.append([phase, NAMES[method]] + [number(g['score_mean']) for g in groups] + [number(delta)])
            values = [r['score'] for r in all_rows if r['phase'] == phase and r['method'] == method and r['decision'] in ('NORMAL', 'ANOMALY')]
            means.append(statistics.mean(values) if values else None)
        available = [v for v in means if v is not None]
        between_rows.append([NAMES[method]] + [number(v) for v in means] + [number(max(available)-min(available)) if available else 'nicht bestimmbar'])
    sections += [table(["Lauf", "Methode", "180–210 s", "210–240 s", "240–270 s", "270–300 s", "Letzte minus erste Gruppe"], trend_rows), "",
        table(["Methode", "Gesamtmittel Lauf 1", "Gesamtmittel Lauf 2", "Gesamtmittel Lauf 3", "Spanne der drei Laufmittel"], between_rows), "",
        "Die Differenz der letzten und ersten Gruppe beschreibt eine Veränderung innerhalb desselben Laufs; die Spanne der Laufmittel beschreibt Unterschiede zwischen Starts. "
        "Eine Endpunktdifferenz allein beweist keinen monotonen oder systematischen Verlauf; dafür sind auch die beiden mittleren Gruppen und die vollständige Grafik zu beachten. "
        "Unterschiedliche Mittelwerte oder nicht überlappende Scorebereiche zwischen Starts widerlegen für sich allein keine geeignete Einlaufzeit. "
        "Umgekehrt rechtfertigen späte zeitliche Veränderungen keine nachträgliche Verschiebung des Testabschnitts. "
        "Eine physische Ursache wie Erwärmung oder mechanische Veränderung lässt sich aus diesen Scoreverläufen nicht ableiten.", "",
        "## Bewertung und konkreter nächster Schritt", ""]
    for method in METHODS:
        pm = comparison['pooled'][method]
        rates = [s['metrics'][method]['false_alarm_rate_among_valid_normal_windows'] for s in summaries]
        sections += [f"{NAMES[method]}: Insgesamt {pm['false_alarms']} Fehlalarme unter {pm['valid_windows']} gültigen normalen Fenstern ({percent(pm['false_alarm_rate_among_valid_normal_windows'])}); "
                     f"je Lauf {', '.join(percent(r) for r in rates)}. " +
                     ("Die beobachteten normalen Fehlalarme begrenzen die Zuordnung späterer Alarme zu einer kontrollierten Luftstromveränderung. "
                      "Sie dürfen weder durch Mittelung verborgen noch nachträglich aus der Bewertung entfernt werden." if pm['false_alarms'] else
                      "In diesen drei Aufnahmen wurde kein Fehlalarm beobachtet. Das belegt weder eine allgemeine Nullfehlalarmrate noch Empfindlichkeit gegenüber veränderten Zuständen."), ""]
    sections += ["Das Pilotpaket bleibt als eingefrorener Vergleichsstand nutzbar, ist anhand dieser Prüfung jedoch nicht als zuverlässiger automatischer Störungsnachweis freigegeben. "
        "Die bereits im ersten Lauf hohen normalen RMS-/IF-Fehlalarmanteile bleiben ein wesentlicher Befund. "
        "Weitere perfekte oder konstante Normalverläufe sind keine Voraussetzung für die Beschreibung normaler Variabilität. "
        "Eine spätere Verbesserung der Modelle oder Schwellen müsste eine neue Modellversion erhalten; diese Testdaten wären dann Entwicklungswissen und dürften nicht erneut als unabhängiger Test dieser neuen Version gelten.", "",
        "Als nächsten kontrolliert veränderten Testzustand empfehle ich zunächst eine separat freizugebende Folge Normal → äußere Luftstromveränderung → Normal, "
        "jeweils 300 Sekunden bei denselben 75 % PWM und 25 kHz, gleicher Sensorerfassung und unverändertem Aufbau v4. "
        "Der gesamte Anlauf wird gespeichert; [180,300), 128er-Fenster und das hier eingefrorene Paket bleiben für diesen Vergleich vorab festgelegt. "
        "Zeitnahe Normalreferenzen sind notwendig, weil normale Fehlalarme bereits auftreten; die Platte darf nicht allein deshalb als erkennbar gelten, weil einzelne Alarme vorliegen. "
        "Die Folge ist zunächst ein Pilot und kein Reproduzierbarkeitsnachweis. Weitere unabhängige Folgen sollten nur anhand einer vorab benannten offenen Frage geplant werden.", "",
        "Für diesen späteren Versuch sind als bisherige Nutzerangaben eine Platte von 120 × 120 mm und 100 mm Abstand dokumentiert. "
        "Vor dem Versuch müssen die tatsächliche Auslassseite, die Bezugsebenen des Abstands, Position/Ausrichtung und Überdeckung eindeutig dokumentiert werden; "
        "diese Istangaben wurden hier nicht neu geprüft. Die Platte wird separat und kippsicher befestigt und berührt weder Sensor noch Lüfter. "
        "Zum Einsetzen oder Entfernen wird die externe 12-V-Versorgung getrennt und der vollständige Stillstand abgewartet; Lüfter und Sensor behalten ihre Position. "
        "Es gibt keinen Eingriff am laufenden Rotor. Es handelt sich um einen kontrolliert veränderten Betriebszustand, nicht um einen nachgewiesenen Defekt. "
        "Jetzt wurde kein Plattenversuch und kein weiterer PWM-Betriebspunkt gestartet.", "",
        "Aus ausschließlich normalen Testdaten werden kein Anomalie-Recall, kein F1-Wert und keine allgemeine Erkennungsleistung abgeleitet. "
        "Eine erfolgreiche Rückkehr oder Trennung in einem späteren Plattenpilot wäre ebenfalls noch kein allgemeiner KI-Erkennungsnachweis.", "",
        "## Abschlussstatus und Nachvollziehbarkeit", "",
        f"Nach Lauf 3 wurden am {local_time(sessions[-1]['zero_command_completed_utc'])} 0 % PWM bei 25 kHz eingestellt und zurückgelesen "
        "(Periode 40.000 ns, Tastdauer 0 ns, aktivierter PWM-Kanal, bestätigte Pin-Funktion). "
        "Ein vollständiger mechanischer Stillstand nach diesem letzten Lauf wurde zu diesem Berichtszeitpunkt nicht beobachtet oder bestätigt. "
        "Der Softwarestellwert ist kein Drehzahl- oder Stillstandsnachweis.", ""]
    verification = BASE / "final_verification.json"
    if verification.exists():
        verified(verification)
        audit = read(verification)
        preservation_ok = (audit.get('historical_files_checked') == 1172 and audit.get('historical_files_changed') == []
                           and audit.get('protocol_hash_matches') is True and audit.get('frozen_bundle_hash_matches') is True
                           and audit.get('implementation_hashes_unchanged') is True and audit.get('source_and_result_hash_mismatches') == [])
        sections += ["Die separat durchgeführte [abschließende Erhaltungs- und Statusprüfung](final_verification.json) ist als eigener Nachweis verlinkt. " +
                     ("Der Hashvergleich aller 1.172 bereits vor dieser Testreihe vorhandenen Dateien ergab keine Änderungen; Worddatei, historische Daten und vorhandene Modelle blieben unverändert. "
                      "Protokoll, eingefrorenes Modellpaket, Implementierung sowie Quellen- und Ergebnishashes stimmen mit den erwarteten Werten überein." if preservation_ok else
                      "Das Prüfprotokoll wird hier nicht pauschal als vollständig bestanden zusammengefasst; seine konkreten Felder und gegebenenfalls Abweichungen sind maßgeblich."), ""]
    else:
        sections += ["Eine abschließende Erhaltungsprüfung lag beim Erstellen dieses Berichts noch nicht als `final_verification.json` vor. "
                     "Deren Ergebnis wird hier deshalb nicht vorweggenommen. Der Berichtsgenerator hat ausschließlich neue Berichtsdateien angelegt.", ""]
    sections += [f"Modellpaket: `{bundle_path}`; SHA256 `{digest(bundle_path)}`. "
                 f"Protokoll-SHA256: `{protocol_hash}`. Evaluator-SHA256: `{protocol['evaluator_sha256']}`.", "",
        "Die vollständigen SHA256-Werte der Rohdateien, Metadaten, Sitzungsprotokolle, Freigaben, Steuerjournale, Einzel- und Vergleichsergebnisse sowie Modellartefakte "
        "stehen in [report_artifact_hashes.json](report_artifact_hashes.json). Die Hashliste enthält auch die neu erzeugte Gruppen-CSV und diesen Bericht. "
        "Sie ergänzt die bereits in den Einzelergebnissen gespeicherten Herkunftsnachweise.", ""]
    sections += [table(["Lauf", "Aufnahme-ID", "Rohdaten-SHA256", "Ergebnis / Sitzung"],
                      [[i, f"`{s['recording_id']}`", f"`{s['csv_sha256']}`", f"[Ergebnis](evaluation_{s['phase']}/summary.json) · [Sitzung]({s['phase']}_session.json)"] for i, s in enumerate(summaries, 1)]), ""]
    with outputs[1].open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(group_rows[0]))
        writer.writeheader()
        writer.writerows(group_rows)
    verified(outputs[1])
    with outputs[0].open("x", encoding="utf-8") as handle:
        handle.write("\n".join(sections))
    verified(outputs[0])
    verified(Path(__file__))
    with outputs[2].open("x", encoding="utf-8") as handle:
        json.dump({"created_at_utc": datetime.now(timezone.utc).isoformat(), "purpose": "descriptive_report_inputs_and_outputs_sha256", "self_hash_not_included": True,
                   "no_training_inference_or_hardware_access": True, "files_sha256": inventory}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"report": str(outputs[0]), "groups": str(outputs[1]), "hashes": str(outputs[2]), "whole_recordings": 3}, ensure_ascii=False))


if __name__ == "__main__":
    main()
