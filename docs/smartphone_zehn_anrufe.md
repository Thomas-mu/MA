# Smartphone-Messreihe mit zehn Anrufen

`src/phone_series_experiment.py` erfasst die gesamte Serie in genau einem
Sensorprozess. GPIO18 bleibt ab Beginn der Einlaufzeit bei 75 % PWM und 25 kHz.
Das Profil `standlauf_pwm75_200hz` und sein bestehendes Vergleichsbündel werden
in einen neuen Ergebnisordner kopiert; Training, Skalierung, Fenster und
Schwellen werden nicht verändert.

Vor dem Start erfolgen Modellhash- und Prozessprüfungen. Der Prozess hält die
vorhandenen Sensor- und Lüfterlocks, stellt einmal 75 % ein und speichert die
Rücklesung in `config.json`. Erwartet: Periode 40.000 ns, Tastzeit 30.000 ns,
aktivierte PWM, normale Polarität und GPIO18 als PWM0_CHAN2. Während der Serie
prüft er diese Einstellung alle fünf Sekunden ohne nachzuregeln. Eine
Abweichung beendet die Aufnahme mit dokumentiertem Fehler. PWM-Rücklesung ist
keine Drehzahlmessung.

Die gewählte Einlaufzeit beträgt 30 s entsprechend der vorhandenen anfänglichen
Einlaufregel in `versuchsplan_kontrolliert_20260909.md`. Das aktuelle Modellprofil
enthält selbst keine gesonderte mechanische Einlaufzeit. Anschließend werden
mindestens 30 s Normalbetrieb entsprechend dem bestehenden Smartphoneplan
erfasst. Beide Abschnitte sind in den Rohdaten enthalten; die Einlaufzeit wird
in der Auswertung nicht als Normalreferenz gezählt.

Vor jeder Aufforderung wird der Aufnahmestatus geprüft und der lokale
`call_requested`-Marker gespeichert. Nach der Rückmeldung des Nutzers wird
`end_reported` für dieselbe Versuchsnummer gespeichert. Diese Befehle greifen
nicht auf den Sensor zu. Die nächste Freigabe wird erst nach mindestens 30 s
zusätzlichen aufgezeichneten Messwerten zugelassen. Chatmarker grenzen einen
Suchbereich ein; sie messen keinen physischen Vibrationsbeginn oder sein Ende.
Die Anrufdauer wird nicht auf fünf Sekunden gesetzt.

Nach der Rückmeldung zu Versuch 10 beendet der Prozess die Aufnahme automatisch
nach mindestens 30 s Nachlauf. Ein Stop-Befehl oder SIGTERM beendet sie auch
vorher kontrolliert. Teilfenster bleiben erhalten. PWM bleibt beim Beenden
unverändert. Es gibt keine zeitliche Begrenzung auf 600 s.

Beispielbefehle, wobei RUN einen neu angelegten Serienordner bezeichnet:

```bash
.venv/bin/python src/phone_series_experiment.py prepare --output "$RUN"
.venv/bin/python "$RUN/source/phone_series_experiment.py" record --run "$RUN"
.venv/bin/python "$RUN/source/phone_series_experiment.py" status --run "$RUN"
.venv/bin/python "$RUN/source/phone_series_experiment.py" mark --run "$RUN" --event call_requested --number 1
.venv/bin/python "$RUN/source/phone_series_experiment.py" mark --run "$RUN" --event end_reported --number 1
.venv/bin/python "$RUN/source/phone_series_experiment.py" stop --run "$RUN" --note 'Kontrollierter Abbruch'
```

Für den interaktiven Betrieb wird `record` als eigenständiger Prozess mit
abgetrennter Sitzung, ohne Standardeingabe und mit einer exklusiv angelegten
Logdatei gestartet. Er bleibt damit unabhängig von Chatpausen aktiv. Status,
Marker und Abbruch werden über gesonderte kurze Verwaltungsbefehle bedient.

Die spätere Auswertung liest ausschließlich die gespeicherten Rohdaten.
`analysis_rules.json` legt die Regeln vor den Ergebnissen fest. Alle drei
Methoden erhalten dieselben 128/128-Fenster; ungültige und über Markergrenzen
reichende Fenster bleiben sichtbar. Alle zehn Versuche erscheinen in der
Vergleichstabelle, auch bei Abbruch oder fehlendem Alarm. Ein fortbestehender
Alarm zählt nicht als neuer Alarmbeginn. Der separate Rechenzeitbenchmark
erfolgt nach dem Aufnahmestopp auf dem Pi und belegt keine Live-Reaktionszeit.
