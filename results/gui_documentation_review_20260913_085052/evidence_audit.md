# Vorhandene GUI-Nachweise: Prüfung vom 13.09.2026

## Ergebnis

Die GUI ist implementiert und besitzt historische protokollierte Ausgaben. Im Repository liegt jedoch kein Nachweis vor, dass der aktuelle GUI-Code das finale v4-Paket verwendet hat. Die vollständigen Laufzeit- und Ressourcenreihen des finalen Pakets schließen die GUI ausdrücklich aus. Deshalb ist A12 nicht vollständig nachgewiesen. Die drei erneut ausgeführten Regressionen prüfen gezielt GUI-Logik mit Mocks; sie ersetzen weder eine sichtbare Bedienprüfung noch einen Lastvergleich.

## Gespeicherte historische GUI-Ausgaben

In `profiles/home_v001/results/`, `profiles/fan_50/results/` und `profiles/fan_25/results/` liegen insgesamt **16 CSV-Dateien mit dem Präfix `live_tflite_gui_` und 30.075 Entscheidungszeilen**, datiert 23.–26.08.2026. Die Einzelzählung, Spalten und Anfangs-/Endzeilen stehen in `historical_gui_log_inventory.json` dieses Prüfverzeichnisses. Beispiele:

| Datei | Entscheidungszeilen | Schwelle |
|---|---:|---:|
| `profiles/home_v001/results/live_tflite_gui_20260823_165053_058349.csv` | 505 | 0,0798548072 |
| `profiles/fan_50/results/live_tflite_gui_20260824_104135_081561.csv` | 474 | 0,2210574491 |
| `profiles/fan_25/results/live_tflite_gui_20260825_161129_988401.csv` | 293 | 0,1867383913 |
| `profiles/fan_25/results/live_tflite_gui_20260826_140730_902708.csv` | 10.244 | 0,3 |

Alle Dateien haben die sieben Spalten `timestamp`, `window_index`, `reconstruction_error`, `threshold`, `predicted_label`, `inference_time_ms`, `measured_sampling_rate_hz` (jeweils Zeile 1). Bei den drei Altprofilen steht `sampling_rate_hz=500`, `window_size=128`, `step_size=128` in `profile.json`, Zeilen 9–11. Die Profilmetadaten beschreiben den damaligen Zugriff als zeitgesteuerte Softwareabfrage ohne explizite ODR-Konfiguration, beispielsweise `profiles/fan_25/profile.json:59–63`. Die circa 500 Hz der historischen CSVs sind deshalb kein Nachweis einer physischen Sensor-ODR.

Die Dateien sind historische Protokollartefakte des GUI-Pfads. Sie enthalten weder Quellen-/Artefakthashes des konkreten GUI-Laufs noch CPU, RSS, Rohdatenqualität, Fenster-zu-Anzeige-Zeiten oder Screenshots/Bedienprotokolle. Aus ihnen folgen weder die visuelle Richtigkeit der damaligen Anzeige noch die Einbindung des späteren v4-Pakets. Die aktuelle Software trennt ihre synthetische Simulation vom protokollierenden Livepfad (`src/live_tflite_gui.py:230–284`); die historischen CSVs enthalten aber keine ausreichend vollständige Provenienz, um damit nachträglich den genauen damaligen Code- und Hardwarezustand zu bestätigen. Keine dieser historischen Zeilen wurde für die aktuellen Ergebnisse neu bewertet.

## Softwareprüfungen und grafische Prüfung

Vorhandene Testberichte dokumentieren die drei GUI-Regressionen unter anderem in `results/verification_20260909/software_tests_final_v2.xml` und `results/hardware_confirmation_20260909/software_tests_final.xml`. Frühere fehlgeschlagene Testberichte bleiben erhalten. Die späteren bestandenen Tests belegen die Korrekturen ihres jeweiligen Softwarestands, keine nachträgliche Heilung historischer Messläufe.

Am 13.09.2026 wurden ausschließlich die drei einschlägigen vorhandenen Tests erneut ausgeführt:

| Test in `tests/test_live_pipeline.py` | Geprüfter Sachverhalt | Grenze |
|---|---|---|
| `test_gui_queue_is_bounded_and_preserves_terminal_error`, Zeilen 159–172 | Begrenzte Messwertqueue; gezählte Verwerfungen; Fehler und Ende bleiben gesondert verfügbar | Kein realer Erfassungsthread und keine Oberfläche gestartet |
| `test_gui_log_path_survives_measurement_overflow_and_opens_journal`, Zeilen 174–202 | Logpfad bleibt trotz Queueüberlast erhalten; Zusatzjournal lässt sich öffnen; nur verbleibende Meldungen werden übergeben | Widgets und Messwertanzeige sind Mocks; Journalöffnung ist keine Zeichenlatenzmessung |
| `test_fresh_decision_on_old_window_is_stale_in_actual_gui_update`, Zeilen 204–224 | Frische Entscheidung über ein fünf Sekunden altes Sensorfenster wird als `STALE / VERALTET` behandelt und nicht als NORMAL gezählt | Synthetische Zeitpunkte und Mock-Widgets; keine Sichtkontrolle |

**Ergebnis: 3 bestanden, 10 abgewählt.** Laufzeit des Testprogramms: 1,06 s; kein Benchmark. Vollständiger Aufruf, Rückgabestatus und Hashes liegen in `gui_hardware_free_tests.log` und `gui_hardware_free_tests_context.json`, JUnit-Ergebnis in `gui_hardware_free_tests.xml`. Sensorzugriff, PWM, Lüftersteuerung, TFLite-Aufrufe, Training, Tk-Hauptfenster und GUI-Simulation wurden nicht gestartet. Die temporären Testjournale wurden im neuen Prüfverzeichnis erzeugt und vom vorhandenen Test danach entfernt. Python-Bytecode und pytest-Cache waren deaktiviert; Matplotlib-Cache wurde in das neue Prüfverzeichnis umgeleitet.

Der Arbeitsstand vom 09.09.2026 dokumentiert einen damals fehlgeschlagenen Desktopzugriff (`docs/arbeitsstand_20260909.md:169–175`: `Invalid MIT-MAGIC-COOKIE`, keine Displayverbindung). Das ist ein damaliger Zugriffsbericht, keine aktuelle Displayprüfung und kein Beweis einer fehlenden GUI-Implementierung. `--self-test` ist in `src/live_tflite_gui.py:760–771` als synthetische Anzeigeprüfung vorgesehen; ein gespeicherter erfolgreicher grafischer Selbsttest des aktuellen Codes wurde in den untersuchten Nachweisen nicht gefunden. Die im Arbeitsbericht erfolgreich genannten „sensorfreien Interpreter-Selbsttests“ (`docs/arbeitsstand_20260909.md:65–67`) beziehen sich auf die TFLite-Interpreter der Altprofile, nicht auf eine Tk-Anzeige. Der spätere Import-/Backend-Fix und bestandene Gesamttest werden ausdrücklich von einer realen GUI-Sichtprüfung getrennt (`docs/arbeitsstand_20260909.md:554–561`, `docs/steuerungsuebernahme_20260909.md:295–302`). Ein gespeicherter Bildschirm-/CSV-Abgleich oder ein erfolgreiches grafisches Selbsttestprotokoll wurde auch in den lesbaren historischen Berichten nicht gefunden.

## Kein gemessener Zusatzaufwand der GUI

Das vorab fixierte Endprotokoll setzt `GUI_included: false` ausdrücklich (`results/upright_v4_finalization_20260912_103145/runtime_evidence/protocol.json:189`). Der zugehörige Laufzeitbericht beschreibt neun Sensorprozesse und neun zeitgetreue Offline-Replay-Prozesse, alle ohne GUI (`runtime_analysis/runtime_report.md:9–17`). Seine CPU-, RSS- und Latenzwerte sind daher **keine GUI-Werte**. Die Replay- und Sensorbedingungen unterscheiden sich unter anderem im Vorladen der Quelldaten; ihre Differenz ist keine Schätzung der GUI-Kosten (`runtime_report.md:13–15`).

Auch die früheren Ressourcenreplays kennzeichnen den Ausschluss der GUI: beispielsweise `results/common_comparison_20260909/fan_25_resources_10s_bounded/summary.json` (`gui_overhead_measured=false`) und die drei Methodendateien (`measurement_mode=offline_sequential_replay_without_GUI_without_sensor`). Der gespeicherte frühe Sensorpilot `results/verification_20260909/live_fifo_development.run.json` setzt `gui_enabled=false`.

Die neue GUI besitzt inzwischen eine Instrumentierung für `decision_to_gui_draw_ms`, `window_to_gui_draw_ms` und `gui_messages_dropped` (`src/live_tflite_gui.py:699–712`). Diese misst im Code den Matplotlib-Zeichenabschluss, nicht den physikalischen Anzeigezeitpunkt auf dem Monitor. Außer dem kurzlebigen Mock-Testjournal wurde im geprüften historischen Repository keine `*.gui.csv` gefunden. Keine gespeicherte echte Laufdatei mit `gui_enabled=true` und finale-v4-Artefaktzuordnung wurde gefunden. Es existiert damit kein belastbarer, unter sonst gleichen Bedingungen wiederholter Vergleich **mit/ohne GUI** für das finale Paket.

## Konsequenz für den Bericht

A12 ist als **implementiert, teilweise softwareseitig geprüft; finale Einbindung und GUI-Nachweise offen** zu bewerten. Die ursprüngliche Anforderung bleibt erhalten: angezeigte Werte mit gespeicherten Entscheidungen abgleichen, Fehler/Veralterung/fehlende Daten prüfen und Zusatzaufwand gegenüber dem Betrieb ohne GUI messen (`docs/anforderungsabgleich_20260909.md:50`). Fehlende grafische Nachweise dürfen nicht zu „GUI nicht umgesetzt“ verkürzt werden; vorhandene Altlogs dürfen umgekehrt nicht als finaler v4-GUI-Nachweis gelten.

Die Codekompatibilität wird gesondert durch den zweiten Review untersucht. Für die vorliegende Dokumentationskorrektur ist keine Nutzerrückfrage und kein neuer Hardwareversuch nötig. Nur ein tatsächlich nicht gespeicherter früherer Bedienvorgang könnte durch einen nachträglichen Nutzerbericht ergänzt werden; er wäre als Nutzerangabe mit damaligem Profil/Datum zu kennzeichnen und würde fehlende Artefakt-, Anzeige- und Lastnachweise nicht ersetzen.
