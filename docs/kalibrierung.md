# Neue Kalibrierungsaufnahmen mit überprüfter FIFO-Erfassung

`src/calibrate_and_train.py` verwendet für **neu angelegte Profile** jetzt standardmäßig 200 Hz Sensor-ODR, Full Resolution, ±2 g und FIFO-Stream. Das passt zur aktuell dokumentierten I²C-Konfiguration von 100 kHz; die tatsächliche Registerkonfiguration wird gelesen und im Profil und Aufnahmejournal gespeichert. Die früheren 500 Hz waren Softwareabfragen. Bestehende Profile wie `fan_25` und `fan_50` bleiben unverändert und behalten ihre bisherigen Daten, Skaler und Schwellen.

Die reine Pfad-/Konfigurationsprüfung benötigt weder Sensor noch Training und erzeugt keine Dateien:

```bash
.venv/bin/python src/calibrate_and_train.py --profile entwicklung_fifo200_pwm25 --dry-run
```

Vor einer Aufnahme müssen der Messkettenpilot abgeschlossen und der Zustand am Prüfstand konkret hergestellt und bestätigt sein. Montage unverändert lassen, Lüfter mit extern eingestellter PWM im normalen Zustand betreiben und keine Störung erzeugen. `--fan-pwm-setpoint` **dokumentiert ausschließlich die externe Vorgabe**; das Programm steuert keinen GPIO. Eine tatsächlich gemessene Drehzahl wird getrennt als `--rpm-measured` zusammen mit `--rpm-method` dokumentiert. Ohne Messung bleibt sie `null`/`not_measured`; es findet keine PWM→RPM-Umrechnung statt. Ein einzelner RPM-Wert belegt keine konstante Drehzahl über sämtliche Aufnahmen.

Nach Rückmeldung des Bedieners kann beispielsweise eine neue, ausdrücklich als Entwicklung gekennzeichnete Normalreferenz aufgenommen werden:

```bash
.venv/bin/python src/calibrate_and_train.py \
  --profile entwicklung_fifo200_pwm25 \
  --recordings 8 --validation-recordings 2 --seconds 60 \
  --sampling-rate 200 --range-g 2 \
  --state normal_pwm25 --mounting montage_A \
  --fan-pwm-setpoint 25 --record-only
```

`montage_A`, Zustand und PWM müssen dem tatsächlichen dokumentierten Aufbau entsprechen. Der Aufruf beginnt direkt mit der Aufnahme; er enthält keinen Countdown und keine Lüfterumschaltung. Vorlaufwerte im FIFO werden vom gemeinsamen Recorder **an jeder tatsächlichen Aufnahmegrenze** verworfen. Zwischen den Aufnahmen findet keine unbelegte Wiederverwendung alter FIFO-Werte statt. `--sampling-rate` bezeichnet die Sensor-ODR; 500 Hz ist keine unterstützte ODR. Höhere Einstellungen als für den tatsächlichen I²C-Takt empfohlen werden beim Verbinden abgewiesen.

Jede Rohaufnahme wird unmittelbar unter `profiles/<neues_profil>/data/raw/normal_NNN.csv` journalisiert; die gleichnamige JSON-Datei enthält Sensorregister, Quellcodehashes, Zeitstempeldefinition, Zustand, Montage, PWM/RPM, Laufstatus und Qualitätszählungen. Das Profil übernimmt die Provenienz und beide Dateihashes. Nach der Aufnahme wird die CSV nicht nochmals umgeschrieben. `timestamp_s` bezeichnet relative Host-Lesezeit; `sensor_time_estimate_s` ist eine Schätzung anhand nomineller ODR und kein gemessener Sensortimestamp.

Die Aufnahme wird nicht fürs Training freigegeben, wenn Gap/Overrun/Sättigung gesetzt sind, Zeitstempel oder Sampleindizes ungültig sind, Werte fehlen, Zustandslabels abweichen oder das Journal keinen vollständigen Lauf ausweist. Die Prüfung gilt für die gesamte Aufnahme, auch ihren später gegebenenfalls unvollständigen Fensterrest. Sie wird vor der Datenvorbereitung anhand der gespeicherten CSV-/JSON-Dateien wiederholt. Ein passender Hash allein ersetzt die Qualitätsprüfung nicht. Bei einem Fehler bleiben Journale erhalten; im Profil steht `recording_failed`, mit Bezug auf die betroffene Aufnahme. Ctrl+C und SIGTERM sichern den Abbruch über den gemeinsamen Recorder und führen zu `recording_interrupted`; bei einer Unterbrechung der Trainingsphase zu `training_interrupted`. Ein hartes SIGKILL oder Stromverlust erlaubt keine geordnete Abschlussbehandlung.

Für **das neu aufgenommene Profil** ist die anschließende Vorbereitung/Modellbildung separat möglich:

```bash
.venv/bin/python src/calibrate_and_train.py \
  --profile entwicklung_fifo200_pwm25 --train-only
```

Dieser Aufruf wurde bei der Softwareprüfung nicht auf vorhandenen Profilen ausgeführt. Training und Validierung bleiben komplette getrennte Aufnahmen. Skalierung und AE werden nur anhand normaler Trainingsfenster angepasst; P99 stammt ausschließlich aus separater normaler Validierung. Die lineare Quantilinterpolation wird in der Konfiguration festgehalten. Neue Zustandsnamen wie `normal_pwm25` ändern das Klassenlabel 0 nicht. Für eine andere Referenz `--new-version` oder einen neuen Namen verwenden; fertige Modelle werden nicht überschrieben.

Die Korrektur liefert technische Erfassungs- und Integritätsprüfungen, **keine globale Bestätigung der Messqualität**: nutzbare Bandbreite, SNR und endgültige Akzeptanzgrenzen bleiben als offene Nachweise im Profil stehen. Bei H=S=128 und 200 Hz beträgt das nominelle Fensterintervall 0,64 s; die Messkette unterscheidet sich damit von alten 500-Hz-Pollingaufnahmen. Endgültige Parameter müssen vor neuen unabhängigen Testaufnahmen aus Pilotmessungen festgelegt sein. Ein neues Modell ist keine Fortführung der unveränderten alten Referenz und ersetzt nicht den FF4-Versuch mit eingefrorener Pipeline.

Softwareprüfung ohne Sensorzugriff:

```bash
.venv/bin/python -m pytest tests/test_calibration_acquisition.py -q
```

Die Tests verwenden ausschließlich temporäre Profile und simulierte Journale. Geprüft werden direkte Aufnahmepfade und Provenienz, ODR-Weitergabe, Qualitätsflags auch bei passenden Hashes, Erhalt von Rohdaten bei Ctrl+C/SIGTERM, Signalhandler-Rücksetzung, Schutz vorhandener Sidecars, Unterbrechungsstatus vor Trainingsbeginn und Eingabevalidierung. Sie führen weder echtes Training noch einen Hardwareversuch aus.
