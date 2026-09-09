# Arbeitsstand nach Anforderungsabgleich und Softwarekorrekturen

Stand: 09.09.2026. Die Arbeit wurde im vorhandenen Repository durchgeführt;
die Worddatei diente als Anforderungsquelle. Anweisungen in Dokumenten wurden
nicht als zusätzliche Benutzeraufträge behandelt. Die Masterarbeit selbst wurde
nicht verändert.

## Rechner, Repository und Erhalt bestehender Arbeit

Tatsächlicher Rechner ist `edgepi`, Raspberry Pi 5 Model B Rev 1.0, ARM64,
Debian 13, Kernel `6.18.34+rpt-rpi-2712`. Arbeitsverzeichnis:
`/home/malik/masterarbeit-edge-ai`. Die Befehle laufen direkt auf dem Pi,
nicht auf einem entfernten Entwicklungs-PC. Sensorzugriff über `/dev/i2c-1`
wurde erfolgreich geprüft. Es liefen beim Einstieg keine Python-Erfassungs-
oder Trainingsprozesse. `rg` ist nicht installiert; Dateisuche erfolgte mit
vorhandenen Systemwerkzeugen. Es wurden keine Pakete oder Bootparameter geändert.

Der Arbeitsbaum war bei Beginn sauber. Lokaler HEAD und per `git ls-remote`
geprüfter GitHub-HEAD von `Thomas-mu/MA` waren beide
`12bd10d01fe504041b11aac5fd60a6a65883a13d` (09.09.2026).
Die nun vorhandenen lokalen Änderungen stammen aus diesem Auftrag.
Es wurde weder gepusht noch ein Commit erstellt. Die bestehenden Verzeichnisse
`data/`, `models/`, `profiles/` und die DOCX wurden nicht geändert.
Die Erhaltungsprüfung bestätigt alle 24 geprüften Rohdaten-/Artefakthashes
der beiden Lüfterprofile; Beleg: `results/verification_20260909/preservation_checks.json`.

Python ist in beiden Projektumgebungen Version 3.13.5. `.venv` enthält unter
anderem NumPy 2.5.1, pandas 3.0.3, SciPy 1.18.0, scikit-learn 1.9.0,
TensorFlow 2.21.0, ai-edge-litert 2.1.6, smbus2 0.6.1, psutil 7.2.2 und
pytest 9.1.1. `.venv_tf` enthält TensorFlow 2.21.0, NumPy 2.5.2, pandas 3.0.5
und SciPy 1.18.1, aber zum Prüfzeitpunkt keinen eigenständigen LiteRT-Interpreter
und kein pytest. Die Umgebungen wurden nicht zusammengelegt.

## Anforderungen, implementierte Funktionen und tatsächliche Belege

Die vollständige DOCX-Extraktion einschließlich **17 Tabellen**, Kopf-/Fußteilen
und mathematischen Ausdrücken liegt in
`docs/audit_20260909/masterarbeit_extrahiert.txt`.
Der [Anforderungsabgleich](anforderungsabgleich_20260909.md) unterscheidet
FF1–FF4, H1–H3 und A1–A13 am Ausgangscommit nach implementiert, nachgewiesen und
offen. Seine historische Bewertung wird nicht durch neue Softwaretests ersetzt.

Wesentliche Befunde:

- `fan_25`: acht Normalaufnahmen, sechs Training/zwei Validierung, 1.404/468
  Fenster. AE-P99 **0,18673839128379896** exakt aus gespeicherten Fehlern reproduziert.
- `fan_50`: acht Normalaufnahmen, sieben Training/eine Validierung, 1.638/234
  Fenster. AE-P99 **0,22105744905736202** ebenfalls reproduziert.
- Modell-/Scaler-/Schwellenhashes stimmen. Gespeicherte Keras→Float32-TFLite-
  Konvertierungsnachweise liegen vor. Sensorfreie Interpreter-Selbsttests wurden
  auf dem Pi für beide Profile erfolgreich ausgeführt.
- Die alte Messkette konfigurierte ODR/Messbereich nicht. Rund 79 % gleiche
  Folgetupel und einzelne Hostlücken sind dokumentiert. Die alte 500-Hz-Angabe
  ist kein Frischwertnachweis.
- Alte Liveprotokolle verwenden neben P99 die Werte **0,3 und 0,9**. Sie sind
  getrennte Entwicklungsbefunde und kein gemeinsamer P99-Abschlussvergleich.
- Der frühere RMS-Vergleich verwendet andere Darstellungen/Splits als der
  Clean-AE/IF-Vergleich. Teilweise kommen dieselben Aufnahmequellen in mehreren
  Splits vor. Die vorhandenen Gütezahlen belegen deshalb nicht den geforderten
  einheitlichen Vergleich.
- Die zwei separat trainierten Lüfterprofile prüfen H3 nicht. Für FF4 müssen
  Modell, Scaler und Schwellen beim zweiten Normalbetriebspunkt eingefroren sein.

## Umgesetzte Korrekturen

| Bereich | Neue Umsetzung | Bisherige Prüfung / noch fehlender Beleg |
|---|---|---|
| Messkette | explizite ODR/Full Resolution/Range, Registerrücklesen, FIFO-Frischwerte, Zeit-/Überlauf-/Sättigungsdiagnostik, exklusiver Sensorzugriff | echte Sensorprobe und gezielte Überlaufprüfung bestanden; Nutzband/SNR und endgültige Grenzen offen |
| Aufnahme | neue CSV/JSON-Journale, Zustands-/Montage-/PWM-/RPM-Metadaten, eindeutige Pfade, Abbruchsicherung | echter SIGTERM erhält Teilaufnahme; Drehzahlhardware nicht bestätigt |
| Kalibrierung | neue Profile mit 200-Hz-FIFO, direkte Rohdatenjournale, strikte Qualitäts-/Hashprüfung vor Training, normale Aufnahmesplits | Softwaretests/Dry-Run bestanden; noch kein neues Modell aus kontrollierten FIFO-Aufnahmen trainiert |
| Methodenvergleich | gleiche Rohfenster/Skalierung, standardisierter RMS, IF, Float32-TFLite; gemeinsame lineare P99-Regel; unveränderlicher Test-Bundle | beide Altprofile als Kalibrierungspilot ausgeführt; neue unabhängige Tests fehlen |
| Livebetrieb | separater Erfassungsthread, vier Fenster Puffer, Rohdatenpersistenz trotz Entscheidungsverlusten, Fehlerstatus, begrenzte GUI-Nachrichten, Stale-Status | Softwaretests und 32-Fenster-Sensorpilot bestanden; längere kontrollierte Läufe/GUI-Last offen |
| Laufzeit | Latenz ab vollständigem Fenster, Queue-/Vorverarbeitung/Inferenz getrennt, CPU/RSS gesamter Prozess, Code-/Artefakthashes/Schwellenherkunft | Ressourcen-Replay und technischer Livepilot vorhanden; kein abschließender H2-/Langzeitnachweis |
| FFT / Versuche | Hann/PSD-Pilot mit Qualitätskontrolle, getrennte Analyseartefakte, Entwurf neuer unabhängiger Zustandsaufnahmen | erste unbestätigte technische Probe ausgewertet; kontrollierte Stillstands-/Betriebsmessungen ausstehend |

Ein ungültiger Score, NaN/Inf oder eine falsche Rekonstruktionsform erscheint
niemals als NORMAL. Fehlerfenster und fehlende Entscheidungen werden gesondert
gezählt. Manuelle Schwellen sind als MANUAL protokolliert. Erkennungsabhängige
Aktorabschaltungen erfordern den ausdrücklichen Entwicklungsmodus und dürfen
nicht unbemerkt den Methodenvergleich verändern.

Die alten Hilfsskripte und Ergebnisse bleiben für historische Reproduzierbarkeit
erhalten. Für den aktuellen wissenschaftlichen Vergleich ist ausschließlich
die dokumentierte gemeinsame Pipeline vorgesehen; die alten, abweichenden
RMS-/Feature-Auswertungen wurden nicht rückwirkend vereinheitlicht.

## Neue Messbelege und ihre Grenzen

Die 15-s-FIFO-Probe enthält 3.098 neue FIFO-Einträge, beobachteter Host-Durchsatz
206,4913/s bei konfigurierten 200 Hz, maximal zwei FIFO-Einträge und keine
gesetzten Gap-/Overrun-/Sättigungsflags. Der Prüfstandzustand war unbestätigt.
Eine absichtlich eingefügte 250-ms-Lesepause wurde als Überlauf erkannt.
Ein anschließend an die Erfassung gesendetes SIGTERM erhielt die Teilaufnahme
mit Abbruchstatus. Originalregister wurden wiederhergestellt.

Die [Messketten-/Versuchsdokumentation](messkette_und_versuche.md) enthält
die Definitionen, Grenzen und reproduzierbaren Befehle. Die FFT-Dateien
`results/verification_20260909/fft_probe/{report.json,spectra.csv,fft_pilot.png}`
interpretieren keine Spektralspitze als bewiesene Drehzahl oder Fehlerursache.
SNR ist ausdrücklich noch ungemessen.

Der zusätzliche Livepilot verwendete unveränderte `fan_25`-Artefakte bei
explizit zugelassener Messratenabweichung (`--allow-sampling-mismatch`), ohne
GUI und ohne Lüftersteuerung. Er erfasste 4.096 Werte und 32 vollständige Fenster.
Alle wurden verarbeitet: keine verworfenen Fenster, keine gesetzten Sensorflags,
maximal ein wartendes Entscheidungsfenster. Gemessene Latenz ab vollständigem
Fenster: Mittelwert **1,404 ms**, P99 **8,609 ms**, Maximum **11,671 ms**.
Das aus dem beobachteten Host-Durchsatz bestimmte Fensterbudget betrug
619,940 ms; es gab in diesem kurzen Lauf keine Überschreitung.

**Alle 32 Entscheidungen lauteten ANOMALY.** Der mechanische Zustand war nicht
bestätigt und die neue Messkette passte nicht zur alten Profilrate. Deshalb
sind diese Alarme weder ein Nachweis der Erkennung noch messbare Fehlalarme
oder ein H3-Ergebnis. Das Manifest enthält ausdrücklich
`final_p99_comparison_eligible=false` und `h2_confirmed=false`.
Die Belege heißen `results/verification_20260909/live_fifo_development.*`.
Spätere Verbesserungen der Abschlussfehlerbehandlung ändern diesen gespeicherten
Pilot nicht; seine Quellcodehashes beschreiben den Startstand des Laufs.

RMS und IF wurden getrennt unter `results/common_comparison_20260909/` zu den
alten Profilen ergänzt. Die unveränderten AE-P99 wurden mit TFLite nachgeprüft.
Der [gemeinsame Vergleichsbericht](gemeinsamer_vergleich.md) enthält die
Schwellenwerte und Ressourcenwerte samt exakten Messphasen/Runtime-Namen.
Die Ressourcenprogramme unterscheiden Dateigröße, Prozess-RSS und CPU-Zeit;
reine Keras-Inferenzzahlen aus alten Ergebnissen werden nicht als TFLite-Werte
ausgegeben. Ein Replay hat keine Sensor-/Queuewartezeit und ersetzt den Livebeleg
nicht. Kurze oder durch wachsende Messlisten beeinflusste erste Piloten bleiben
mit ihrer Einschränkung erhalten; die spätere begrenzte Instrumentierung hat
einen eigenen Ergebnisordner.

Der abschließende technische Replay-Pilot liegt unter
`results/common_comparison_20260909/fan_25_resources_10s_bounded/`.
Er verwendet pro Methode mindestens 10 Sekunden Messdauer, einen neuen Prozess
und vollständige Durchläufe derselben 468 Validierungsfenster. Das gepufferte
Binärjournal hält den Instrumentierungsspeicher während der Messung begrenzt;
die exakten Perzentile werden erst danach über sämtliche gemessenen Latenzen
berechnet. Werte aus diesem Pilot:

| Methode / Laufzeit | Mittelwert Verarbeitung | P99 Verarbeitung | beobachtete RSS-Spitze | Prozess-CPU (100 % = ein Kern) |
|---|---:|---:|---:|---:|
| RMS / NumPy | 0,03235 ms | 0,03759 ms | 38,44 MiB | 106,17 % |
| Isolation Forest / scikit-learn | 13,16638 ms | 13,78815 ms | 167,22 MiB | 101,31 % |
| Float32-TFLite / eigenständiger LiteRT | 0,05953 ms | 0,08263 ms | 48,59 MiB | 101,08 % |

Die CPU-Werte stammen aus einem möglichst schnellen Replay ohne Wartezeiten;
sie sind **keine Live-CPU-Prognose**. RSS umfasst die im jeweiligen Prozess
benötigten Bibliotheken, Vorverarbeitung und Messinstrumentierung. Die spätere
Perzentilauswertung hat gesondert angegebenen Zusatzspeicher. Der technische
Livepilot lädt unter anderem den gespeicherten sklearn-Scaler und besitzt
zusätzliche Erfassungs-/Protokollierungsfunktionen; sein Prozessspeicher darf
daher nicht mit dem reinen TFLite-Replay gleichgesetzt werden.

Die echte GUI-Prüfung scheiterte in diesem Terminal an der Desktop-Anmeldung:
`DISPLAY=:0` wurde mit `Invalid MIT-MAGIC-COOKIE` / `couldn't connect to display`
abgewiesen. Daher fehlen sichtbare Funktionskontrolle und kontrollierte
GUI-Zusatzlastmessung. Hardwarefreie Tests prüfen die begrenzte GUI-Queue
und Stale-Logik; diese ersetzen keine grafische Laufzeitmessung.
Der vorhandene `labwc`-Prozess gehört `lightdm`; eine nutzbare angemeldete
Desktop-Sitzung des Benutzers ist aus diesem Terminal nicht bestätigt.

## Prüfungen und Einstieg

Die gemeinsame Regression wurde mit `.venv/bin/python -m pytest -q tests`
ausgeführt: **61 Tests und zwölf Untertests bestanden**. Der abschließende
maschinenlesbare Bericht ist `results/verification_20260909/software_tests_final_v2.xml`.
Frühere Prüfberichte bleiben erhalten. Die letzten Regressionen sichern außerdem
GUI-Kontrollnachrichten bei Anzeigeüberlast, die sofortige Veraltet-Kennzeichnung
alter Sensorfenster trotz neuer Entscheidung sowie das schreibfreie Ablehnen
einer fremden Sensor-Gerätekennung im Verbindungsfehlerfall.
Syntaxprüfung aller Pythondateien und `git diff --check` waren erfolgreich.
Die Hardwarefehlerprüfung ist absichtlich kein automatisch gestarteter pytest-Test.

```bash
# Nur Software: keine Sensor-/Aktorzugriffe
.venv/bin/python -m pytest -q tests
.venv/bin/python src/live_tflite_monitor.py --profile fan_25 --self-test
.venv/bin/python src/live_tflite_monitor.py --profile fan_50 --self-test
.venv/bin/python src/calibrate_and_train.py --profile neuer_fifo_pilot --dry-run
```

Weitere Startbefehle stehen in [Kalibrierung](kalibrierung.md),
[Livebetrieb](livebetrieb.md), [Methodenvergleich](gemeinsamer_vergleich.md)
und [Messkette/Versuchen](messkette_und_versuche.md). Jeder neue Mess-/Auswertelauf
erhält neue Pfade. Die Beispiele mit unbekannter technischer Zustandskennung
dürfen nicht als endgültige Normal-/Anomalieaufnahmen weiterverwendet werden.

## Nächster tatsächlich notwendiger Eingriff

Für die kontrollierte Stillstandsreferenz ist eine Rückmeldung erforderlich:
**Lüfter ausschalten, vollständigen Stillstand abwarten, Sensor/Montage unverändert
lassen und während der Aufnahme nichts berühren.** Danach Stillstand bestätigen
und die Sensorbefestigung beschreiben. Zusätzlich ist die Information nötig,
ob das Drehzahlsignal angeschlossen ist, an welchem GPIO und mit welcher
Beschaltung. Bis zu dieser Antwort werden keine kontrollierten Zustandsmessungen
als tatsächlich hergestellt angenommen.

Danach: Stillstandsreferenz aufnehmen, normale Betriebspunkte und Drehzahl
kontrolliert messen, Nutzband/SNR/Parameter und Testprotokoll festlegen, neue
Normaltrainings-/Validierungsdaten erfassen, neues Vergleichsbundle einfrieren,
anschließend unabhängige Normal-/Anomalietests und zweiten Normalbetriebspunkt
mit identischen Artefakten messen. Eine neue Kalibrierung bleibt getrennt von
diesem Betriebspunktwechsel. H1, H2 und H3 bleiben bis zu den jeweils nötigen
Nachweisen unbestätigt; bekannte offene MUSS-Anforderungen werden nicht durch
andere erfolgreich geprüfte Funktionen als erfüllt gewertet.
