# Nachvollziehbarer Livebetrieb (Softwarestand 09.09.2026)

Die folgenden Änderungen betreffen die Software. Ein erfolgreicher Hardwarelauf, eine GUI-Ressourcenmessung und der wissenschaftliche Abschlussvergleich sind damit nicht nachgewiesen. Vorhandene Profile, Trainingsdaten und alte Logs bleiben erhalten.

## Bestätigte Fehler und Korrekturen

- Zuvor liefen Erfassung, Skalierung und Inferenz nacheinander. Die GUI besaß zusätzlich eine unbegrenzte Nachrichtenqueue. Jetzt liest ein eigener Erfassungsthread frische FIFO-Sensorwerte; ein zweiter Ausführungspfad verarbeitet vollständige Fenster. Der Terminal-/GUI-Monitor verwendet dieselbe Funktion `iter_live_measurements`.
- Die Entscheidungsqueue umfasst standardmäßig vier Fenster. Bei Überlast wird das neueste vollständige Fenster nicht zur Entscheidung zugelassen. Seine Rohdaten bleiben gespeichert. Verworfenes Fenster, Queuefüllstand, Maximalfüllstand, Anzahl betroffener Samples und beim Ende noch ausstehende Fenster werden protokolliert. Das verlangsamt den Sensor nicht absichtlich; Linux-Scheduling, I²C und Dateischreiben müssen weiterhin am Prüfstand bewertet werden.
- Die GUI-Messwertqueue ist auf acht Nachrichten beschränkt. Alte Anzeigen können zugunsten aktueller Nachrichten entfallen; die Entscheidung und die Rohdaten werden unabhängig davon gespeichert. Logpfad, Status, Fehler und Ende werden getrennt als höchstens vier Kontrollzustände bis zur Abholung aufbewahrt. Ein voller Messwertpuffer kann deshalb den initialen Logpfad nicht verdrängen. GUI-Verwerfungen betreffen nur Messwertnachrichten und stehen im GUI-Zusatzlog.
- NaN/Inf, falsche Modellausgabeformen, überlaufender MSE und ungültige Schwellen erzeugen `ERROR`/Label `-1`. Sie erscheinen niemals als `NORMAL`. Fenster mit Gap, Overrun oder Sättigung erhalten ebenfalls keine gültige Normal-/Anomalieentscheidung. Modell-/Vorverarbeitungsfehler beenden den Lauf nach einer protokollierten Fehlerzeile.
- Rohwerte werden bereits während der Erfassung einschließlich Zeitstempeln und Diagnoseflags gespeichert. Beim normalen Stopp, Ctrl+C, SIGTERM oder Fehler werden CSVs geschlossen und synchronisiert; auch ein angebrochenes Fenster bleibt in der Rohdatei. Das Runmanifest enthält den Endstatus und die noch nicht ausgewerteten Fenster. Ein laufendes Modell wird beim Stopp nicht mitten im Interpreter-Aufruf unterbrochen.
- Die GUI zeigt den Ergebniszeitstempel. Sind die zugrunde liegenden Sensordaten oder die Entscheidung älter als drei nominelle Fensterdauern (mindestens eine Sekunde), lautet die Anzeige `STALE / VERALTET`. Das Datenalter beginnt am Host-Leseabschluss des vollständigen Fensters. Eine gerade fertig berechnete Entscheidung über ein bereits altes Fenster erscheint daher unmittelbar als veraltet. Gestoppte Messungen zeigen `STOPPED`, Fehler bleiben `ERROR`.

## Messrate und bestehende Profile

Ein ADXL345 besitzt keine ODR von 500 Hz. Der neue Treiber konfiguriert standardmäßig 200 Hz, Full Resolution, ±2 g und FIFO-Stream; die erlaubte ODR hängt außerdem von der tatsächlich konfigurierten I²C-Busfrequenz ab. Vor Aufnahmebeginn wird der während des Programmaufbaus gefüllte FIFO zurückgesetzt. Frische Samples stammen aus dem FIFO, nicht aus 500 zeitgesteuerten Softwareabfragen.

Die bestehenden Profile geben `sampling_rate_hz=500` an. Eine Anwendung auf neue 200-Hz-Fenster wird daher standardmäßig vor dem Sensorzugriff abgelehnt. `--allow-sampling-mismatch` erlaubt nur einen ausdrücklich gekennzeichneten Entwicklungslauf mit den unveränderten Altartefakten. Ein solcher Lauf ist kein abschließender P99-Vergleich. Die neue Messkette und dazu passende Aufnahmen müssen vor einer neuen, getrennt gespeicherten Kalibrierung bestätigt werden. Alte Daten werden nicht umgedeutet oder umgerechnet.

Die historisch benannte CSV-Spalte `measured_sampling_rate_hz` beschreibt jetzt den Abstand zwischen dem ersten und letzten **Host-Empfangszeitpunkt** eines Fensters: `(N−1)/Δt`. FIFO-Samples können gebündelt gelesen werden. Dieser Wert beweist daher keine exakte physische Sensor-ODR. Die konfigurierte und zurückgelesene ODR steht separat im Runmanifest. `sensor_time_estimate_s` ist ein nominelles Zeitraster aus Sampleindex/ODR, kein Sensorzeitstempel. Overrun-/Gap-Ereignisse werden gezählt; die genaue Zahl verlorener Sensorwerte bleibt unbekannt. Pufferverluste auf Softwareebene sind dagegen exakt zählbar.

## Startbefehle

Alle Befehle im Repository ausführen. Die ersten Befehle greifen **nicht** auf den Sensor oder Lüfter zu:

```bash
.venv/bin/python -m unittest discover -s tests -p test_live_pipeline.py -v
.venv/bin/python src/live_tflite_monitor.py --profile fan_25 --self-test
.venv/bin/python src/live_tflite_monitor.py --profile fan_50 --self-test
```

Erst nach bestätigtem, dokumentiertem Prüfstandszustand ist beispielsweise ein begrenzter Entwicklungslauf mit einem Altprofil sinnvoll. Dieser Befehl steuert den Lüfter nicht:

```bash
.venv/bin/python src/live_tflite_monitor.py --profile fan_25 --sensor-odr 200 --sensor-range 2 --allow-sampling-mismatch --buffer-windows 4 --max-windows 40
```

`--max-windows` begrenzt die **erfassten** vollständigen Fenster. Bei Überlast können weniger Entscheidungen vorliegen. `--fan-pwm-setpoint 25` dokumentiert eine separat eingestellte Vorgabe; diese Option setzt keine PWM. `--measured-rpm WERT --rpm-source 'Messverfahren und Zeitpunkt'` dokumentiert eine unabhängige Messung. Ohne Drehzahlmessung bleibt RPM leer. PWM-Prozent werden niemals in RPM umgerechnet.

Mit lokalem Display kann dieselbe Pipeline in der GUI gestartet werden:

```bash
.venv/bin/python src/live_tflite_gui.py --profile fan_25 --sensor-odr 200 --allow-sampling-mismatch
```

Die GUI verwendet ohne Zusatzoption den Profil-P99. `--threshold 0.3` bleibt eine Entwicklungsoption; Anzeige, CSV und Manifest kennzeichnen die Herkunft als `MANUAL`. Die Dateien des Profils werden dadurch nicht verändert. Ein manueller Schwellenlauf ist kein finaler P99-Vergleich.

Eine reine Sensor-/Amplitudenanzeige ohne Lüftersteuerung ist möglich mit:

```bash
.venv/bin/python src/live_monitor.py --no-fan-control --sensor-odr 200
```

Die etablierte Option `live_monitor.py --fan-pwm PROZENT` steuert weiterhin den Lüfter. Das Programm verwendet eine momentane Beschleunigungsamplitude; es ist **kein RMS-Fensterverfahren**. Amplitudenabhängiges Abschalten erfordert jetzt ausdrücklich `--enable-development-shutdown`. Beim Beenden eines Laufs mit aktiviertem FanController wird der Lüfter wie bisher gestoppt; dieses Ereignis wird gesondert protokolliert. Ein Abschaltereignis fordert nicht mehr blockierend im GUI-Thread eine Neustartentscheidung an.

`live_tflite_fan_control.py` akzeptiert reale Erkennungsabschaltung nur mit `--enable-development-shutdown`, alternativ `--dry-run` ohne Aktorzugriff. Der bestehende reale Aktor verwendet RUN=100 % und STOP=0 %; widersprüchliche PWM-Metadaten werden abgelehnt. Fehler, Datenlücken und ausgelassene Entscheidungsfenster unterbrechen eine noch unbestätigte Anomaliesequenz. Jeder Aktorlauf wird als Entwicklungsdemonstration gekennzeichnet und ist vom Methodenvergleich ausgeschlossen. Der reine Terminal-/GUI-TFLite-Monitor greift nicht auf GPIO/PWM zu.

## Neue Ergebnisdateien und Latenzen

Neue Läufe liegen unter `results/live_runs/` oder am ausdrücklich gewählten neuen `--output`-Pfad. Bestehende Dateien werden nicht überschrieben:

| Datei | Inhalt |
|---|---|
| `NAME.csv` | Entscheidungen, Schwelle und Herkunft, Fehler, Zeiten, Ressourcen, Puffer-/Sensorflags |
| `NAME.raw.csv` | Alle erfassten Rohsamples mit Host-Monotonzeit, UTC-Empfangszeit und Sensordiagnosen, einschließlich verworfener/angebrochener Fenster |
| `NAME.raw.events.jsonl` | Exakte IDs vollständiger Fenster, die wegen voller Entscheidungsqueue verworfen wurden |
| `NAME.run.json` | Start-/Endstatus, Argumente, Host/Python/Paketversionen, Git-Commit und Dirty-Status, SHA256 aller `src/*.py`, Profil-/Modell-/Scaler-/Thresholdhash, wirksame Schwelle und Herkunft, Sensorkonfiguration, Abschlusszähler |
| `NAME.gui.csv` | Zeit von Entscheidung und Fensterabschluss bis zum abgeschlossenen Matplotlib-Zeichnen und GUI-Messwertverluste; nur GUI-Läufe |
| `NAME.control.csv` und Ereignis-JSON | Zusätzliche Bestätigungs-/Aktorinformationen; nur Entwicklungs-Fan-Control |

`decision_latency_ms` beginnt am Host-Leseabschluss des letzten Samples und endet, sobald Score und Klasse bzw. Fehlerentscheidung verfügbar sind. Enthalten sind Queuewartezeit, Skalierung, Tensorübergabe, TFLite-Aufruf, Rücklesen und Score-/Schwellenberechnung. `queue_wait_ms`, `preprocessing_time_ms` und `inference_time_ms` erlauben die Aufteilung. Die historische Inferenzzeit umfasst Tensorübergaben und Scoreberechnung und ist daher nicht ausschließlich `Interpreter.invoke()`.

`window_formation_time_ms` enthält den Host-Zeitabstand der Samples. `total_window_pipeline_time_ms` enthält zusätzlich diese Fensterbildung. Diese beiden Werte dürfen nicht mit der geforderten Latenz **ab vollständigem Fenster** verwechselt werden. CSV-/Konsolenausgabe folgen auf die verfügbare Entscheidung. GUI-Zeichenzeit wird separat erfasst; `draw_event` bestätigt das Matplotlib-Zeichnen, nicht den physikalischen Zeitpunkt der Darstellung auf dem Bildschirm.

CPU-Werte betreffen den gesamten Prozess inklusive Erfassung, Vorverarbeitung, Bibliotheken und gegebenenfalls GUI; 100 % entsprechen einem Kern, Werte darüber sind bei mehreren aktiven Threads möglich. Das Intervall reicht von der vorherigen Ressourcenabfrage bis zur aktuellen Entscheidung. RSS ist eine Momentaufnahme des gesamten Prozesses. Der zusätzliche Linux-Prozesshöchstwert enthält auch Initialisierung und Warmup; er ist kein ausschließlich auf die einzelne Inferenz bezogener Speicherbedarf. Der Loader bevorzugt den installierten eigenständigen `ai_edge_litert.Interpreter` (hier 2.1.6) und verwendet nur bei fehlendem Import `tf.lite.Interpreter`. Beide verwenden ausdrücklich `num_threads=1`; Backend und Version werden geloggt. Ein Lauf in `.venv_tf` kann durch den Fallback deutlich andere Bibliothekslast als ein eigenständiger LiteRT-Lauf besitzen. Diese Werte sind keine Keras-Benchmarks.

Nach Ende liest die Software das Entscheidungs-CSV erneut und berechnet ein exaktes P99 mit linearer Perzentilinterpolation. Eine temporäre SQLite-Datei mit begrenztem Cache vermeidet eine über die gesamte Livezeit wachsende RAM-Liste. `latency_summary` enthält das empirische Budget `128 / beobachtete Hostzustellrate`, P99, Mittelwert, Maximum sowie Deadlineüberschreitungen (`Latenz ≥ Budget`) als Anzahl und Anteil gültiger Entscheidungen. Ungültige, verworfene und ausstehende Entscheidungen werden separat ausgewiesen und können nicht durch ein günstiges P99 verschwinden. Diese Diagnose bestätigt H2 nicht; `h2_confirmed` bleibt ausdrücklich falsch.

## Prüfstatus und offene Nachweise

Hardwarefreie Regressionen prüfen Queueüberlauf mit vollständiger Rohdatenablage, Stop mitten im Fenster, I²C-Fehler, ungültige Modellwerte und Scoreüberlauf, ODR-Mismatch vor Hardwarezugriff, manifestierte Fehlerläufe, begrenzte GUI-Messwertqueues bei dauerhaft erhaltenem Logpfad, Journalöffnung nach Queueüberlauf, unmittelbare Veraltet-Kennzeichnung einer frisch berechneten Entscheidung über alte Daten und die vorhandenen Aktor-Bestätigungssequenzen. Die grafische Darstellung selbst und ihre Last müssen mit einem echten Display zusätzlich geprüft werden. Ein GUI-`--self-test` verwendet simulierte Scores ohne Sensor und ohne Modellinferenz; er belegt ausschließlich GUI-Funktion und ist keine Messung des zusätzlichen Aufwands im echten Livebetrieb. Im aktuellen Terminal fehlen DISPLAY/WAYLAND-Anzeigen. Der separat geprüfte Zugriff über `DISPLAY=:0` wurde mit `Invalid MIT-MAGIC-COOKIE` abgewiesen; ein nutzbarer Zugriff auf den laufenden Desktop ist damit nicht bestätigt.

Für CPU-/RSS-/Latenzvergleich sind identische gespeicherte Aufnahmen/Fenster, identische Artefakte, gleiche Threadkonfiguration und getrennte Wiederholungen nötig. Headless und GUI werden als eigene Bedingungen berichtet; TFLite und Keras bleiben getrennt. Für GUI-Zusatzlast fehlen derzeit kontrollierte Messungen. Ebenso offen bleiben die nachhaltige Erfassungsrate unter Inferenz/GUI, nachgewiesene Sensorverluste/Sättigungsfreiheit am vorgesehenen mechanischen Aufbau und die Qualitätskennzahlen aus unabhängigen, eindeutig gelabelten Tests. Eine neue Livefunktion oder ein erfolgreicher Softwaretest bestätigt keine Forschungshypothese.
