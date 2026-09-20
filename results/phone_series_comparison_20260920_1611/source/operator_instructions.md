# Fortsetzung der laufenden Messreihe

Aufnahmeprozess PID 10815; autonome Sitzung, genau ein ADXL345-Leser.
Profil standlauf_pwm75_200hz; 75 % PWM bei 25 kHz bleiben unverändert.

Alle Befehle aus dem Projektverzeichnis mit .venv/bin/python und diesem eingefrorenen Skript:
results/phone_series_pwm75_20260920_155106_586322/source/phone_series_experiment.py
RUN = results/phone_series_pwm75_20260920_155106_586322

1. Bei Nutzer-Rückmeldung sofort `mark --run RUN --event end_reported --number N --note "Ich habe angerufen und aufgelegt."` ausführen. Der Befehl prüft die Gesundheit der Aufnahme, liest aber keinen Sensor.
2. Status prüfen. Bis mindestens 30 Sekunden gespeicherte Samples nach diesem Endmarker verstrichen sind warten; der Sensorprozess läuft unabhängig weiter.
3. Für N < 10 unmittelbar vor der nächsten Chat-Aufforderung `mark --run RUN --event call_requested --number N+1` ausführen. Anschließend dem Nutzer sagen: „Du kannst jetzt anrufen.“ Versuchsnummer nennen.
4. Nach Versuch 10 läuft der Prozess mindestens 30 Sekunden nach und stoppt selbständig. run.json/status.json auf Abschluss/Fehler prüfen.
5. Für Abbruch jederzeit `stop --run RUN --note "Nutzerabbruch"`; Stopp abwarten. PWM bleibt 75 %.
6. Nach Abschluss das eingefrorene source/analyze_phone_series.py mit --run RUN --output NEUER_ORDNER --runtime litert --threads 1 --benchmark ausführen. Keine Modelle nachtrainieren oder Schwellen ändern.

Status und Marker verwenden lokale Pi-Zeit und monotonic_ns; Rückmeldemarker ist der dokumentierte Eingangs-/Bearbeitungszeitpunkt, kein physischer Vibrations-Endzeitpunkt.
