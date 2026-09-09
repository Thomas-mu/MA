# Arbeitsstand nach Anforderungsabgleich und Softwarekorrekturen

**Aktueller Stand nach abschließender Nutzerklärung:** GPIO18 ist der bestätigte
Steueranschluss des Lüfters. Der ADXL345 ist mit vorgesehener I²C-Beschaltung an
einer Ecke des Lüfterrahmens befestigt. Diese beiden Hardwarepunkte sind
abgeschlossen und keine offenen TODOs. Die historische Chronologie darunter
bewahrt die damals gestellten Fragen und Antworten; sie verlangt keine erneute
Klärung. Die jetzige Fortsetzung betrifft Softwareprüfung und Wordbearbeitung.
Eine unabhängige Drehzahlmessung und die kontrollierte Pilot-/Evaluationsfolge
sind dadurch nicht nachgewiesen.

Historischer Bericht des ersten Arbeitsdurchlaufs vom 09.09.2026; der unten
angefügte Nachtrag dokumentiert die Fortsetzung und nachträgliche Nutzerangaben.
Die Aussagen dieses ursprünglichen Berichtsteils beziehen sich auf den ersten
Durchlauf, insbesondere die damals noch nicht bearbeitete Worddatei.

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

## Nachtrag: Nutzerklarstellung und Fortsetzung am 09.09.2026

Die nachträglich eingegangene Nutzerangabe lautet: Die Hardware ist bereits
aufgebaut und angeschlossen. Lüftersteuerung und Code haben mit diesem Aufbau
schon funktioniert. Die PWM-Vorgabe wurde zwischenzeitlich halbiert; genaue
Ausgangs- und Zielwerte einschließlich der verwendeten Skala sind noch offen.
Während des gesamten vorherigen Arbeitsdurchlaufs war der Lüfter nach Angabe
des Nutzers ausgeschaltet, entsprechend der damaligen Empfehlung.

Dies ist eine **nachträgliche Nutzerangabe**, kein zeitgleich erhobener
Versuchsnachweis. Die ursprünglichen CSV-/JSON-Messprotokolle, Zustandslabels,
FFT- und Liveergebnisse werden nicht umgeschrieben. Insbesondere wird aus
„ausgeschaltet“ keine automatisch kontrollierte Stillstandsreferenz: vollständiger
mechanischer Stillstand, unveränderte Befestigung, Berührungsfreiheit und
Umgebungseinflüsse waren nicht für jede damalige Aufnahme bestätigt. Die neue
Angabe erklärt den Kontext, macht die 32 historischen ANOMALY-Entscheidungen
aber weder zu nachgewiesenen Fehlalarmen noch zu einer bestätigten Erkennung.
Ein Neuaufbau der Hardware ist nicht erforderlich.

### Erneute Prüfung vor Hardwarezugriff

Bei Einstieg war der Arbeitsbaum sauber, HEAD `5335853`. Die Prozess-/Dienstprüfung
zeigte keinen laufenden Erfassungs- oder Lüftersteuerungsprozess. `fuser` meldete
keinen Halter der geprüften I²C-/GPIO-Geräte. Das ist eine Momentaufnahme und
erfasst insbesondere keine zukünftigen Zugriffe fremder Programme.

Rein lesend festgestellt: `pwmchip0/pwm2`, Periode 40.000 ns, Tastzeit 10.000 ns,
`enable=1`, Polarität `normal`, also gespeicherte Vorgabe **25 % bei 25 kHz**.
Bei der ersten Abfrage war GPIO18 auf `PWM0_CHAN2` geschaltet. Nach der
Unterbrechung zeigte `pinctrl` GPIO18 als normalen Ausgang auf Low, während
die PWM-Sysfs-Werte gleich blieben. Ursache und Zeitpunkt dieses Pinwechsels
sind unbekannt; in diesem Arbeitsdurchlauf wurden keine Pin-/PWM-Schreibbefehle
ausgeführt. Gespeicherte PWM-Konfiguration, Pinmultiplexer, tatsächliches
elektrisches Signal, Versorgung und mechanische Drehzahl sind getrennte Größen.
Die ausgelesenen 25 % beweisen insbesondere keine frühere Halbierung von
50 auf 25 %. Der eigene Pi-Kühler unter `hwmon` ist kein bestätigter
Tachokanal des Prüflüfters.

Beleg: `results/continuation_20260909/read_only_hardware_state.json`.

### Noch fehlende Angaben und nächste Aufnahme

Offen sind die Sensorbefestigung (Mittel, genauer Ort, Achsausrichtung), die
Lüfterbefestigung und Unterlage sowie die Bestätigung unveränderter Montage.
Für den früheren Durchlauf fehlen zusätzlich Angaben zu Berührungen,
Fremdschwingungen, Auslaufzeit und gegebenenfalls Änderungen zwischen den
Aufnahmen. Eine nicht mehr erinnerliche Bedingung bleibt unbekannt.
Ebenso fehlen der genaue PWM-Ausgangs-/Zielwert und die aktuelle Abschaltart
(Versorgung, Steuersignal oder anderes). Ein Tachoanschluss ist noch nicht
bestätigt; GPIO, Beschaltung/Pull-up-Spannung und Impulse je Umdrehung sind
gegebenenfalls zu klären. Vorhandene Beispielwerte und Profilnamen ersetzen
diese Angaben nicht.

**Nächster Eingriff: Lüfter AUS lassen, vollständigen Stillstand abwarten,
Montage unverändert lassen und diese Bedingungen bestätigen. PWM derzeit
nicht ändern; 25 % ist nur die ausgelesene gespeicherte Einstellung.**
Nach der Bestätigung wird der Beginn einer neuen 30-s-Pilotaufnahme mit
200-Hz-ODR, Full Resolution, ±2 g und FIFO ausdrücklich angekündigt.
Die Stillstandsaufnahme dient ausschließlich der Pilotdiagnose, nicht als
Normaltraining des laufenden Lüfters. Ohne neue Bestätigung beginnt keine
kontrollierte Aufnahme. Die Fragen wurden dem Nutzer gestellt; eine Antwort
liegt zum Stand dieses Nachtrags noch nicht vor.

Die Betriebsmessung wird erst nach Auswertung des Stillstands gesondert
angekündigt, mit konkreter PWM, Zuständigkeit für das Einschalten und
Bereitschaftsbestätigung. Bis dahin wird weder ein Betriebspunkt angenommen
noch ein neues Modell trainiert. Der vorbereitete Ablauf steht in
`docs/versuchsplan_kontrolliert_20260909.md`.

### Worddatei und Erhaltung

Die Ausgangskopie liegt unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_implementierung_20260909.docx`.
SHA-256: `87fc9b2665e739cec9165c14d4cf074b7afd6f7721b4561b5f7ba5f28ea9d6b6`.
Das Ausgangsmanifest `results/continuation_20260909/baseline.json` enthält
außerdem Prüfsummen von 293 bestehenden Daten-/Modell-/Ergebnisdateien.
Kapitel 6 wurde auf Grundlage der Kapitel 1–5 und des geprüften Quelltexts
ergänzt; Funktionen, technische Entwicklungsbelege und offene Versuche werden
getrennt dargestellt. Kapitel 7 erhält keine vorweggenommenen Güteergebnisse.
Für die Layoutkontrolle wurde LibreOffice Writer mit Python-UNO und den
Ersatzschriften Carlito/Caladea aus den Debian-Paketquellen installiert.
Carlito dient hier als metrisch kompatible Calibri-Ersatzschrift; die DOCX
behält ihre ursprünglichen Schriftvorgaben. Die Projekt-Pythonumgebungen und die
Hardware-/Bootkonfiguration wurden dafür nicht verändert. Diese zusätzliche
Systemsoftware ist bei zukünftigen Ressourcenmessungen im Umgebungsstand
mitzuführen; Dokumentrendern und Messbetrieb werden zeitlich getrennt.

Die Überarbeitung umfasst sieben Unterabschnitte und fünf neue Tabellen
(6-1 bis 6-5), ein ergänztes Inhalts-/Tabellenverzeichnis und die Entfernung
der unmittelbar doppelten, inhaltlich leeren Ausblick-Überschrift. Alle 187
Dokumentblöcke der Kapitel 1–5 sind XML-identisch erhalten; ebenso die drei
Office-Math-Formelobjekte. Außer `word/document.xml` und `word/settings.xml`
wurde kein Bestandteil des DOCX-Pakets verändert. Neue Tabellen haben feste
Spaltenbreiten, wiederholbare Kopfzeilen und gegen Teilung geschützte Zeilen.
Die Seitenverweise wurden anhand der LibreOffice-Paginierung aktualisiert;
native Word-Felder bleiben aktualisierbar. Die PDF-Kontrolle ist ein
Layoutnachweis mit diesem Renderer, keine Prüfung in Microsoft Word selbst.

Die neue reine Software-Regression ergab erneut **61 bestandene Tests und zwölf
bestandene Untertests**; Beleg: `results/continuation_20260909/software_tests.xml`.
Der Sensor-/Steuerungsquelltext wurde in dieser Fortsetzung nicht geändert.
Neue Hilfsprogramme unter `tools/` dienen ausschließlich der dokumenterhaltenden
DOCX-Ergänzung, Paginierung und Strukturprüfung. Der Kapiteltext liegt zusätzlich
unter `docs/implementierung_20260909.md` vor. Die neuen Layout-/Erhaltungsbelege
werden getrennt von allen früheren Messprotokollen gespeichert.

**Weiterhin ausstehend:** Nutzerbestätigung und erste kontrollierte
Stillstandsmessung, danach bestätigter Betriebspilot mit geklärter PWM und
gegebenenfalls Tacho, abschließende Messparameterentscheidung, neue
Trainings-/Validierungsaufnahmen und Modellbildung sowie unabhängige Tests.
Es wurden in dieser Fortsetzung keine Sensormessung, kein Training und kein
Eingriff an PWM oder Pinbelegung ausgeführt. Keine Anforderung oder Hypothese
wurde allein aufgrund der Dokumentergänzung als erfüllt markiert.

Die geprüfte Fassung wurde in `docs/Akz_Masterarbeit_Bericht(3).docx` gespeichert.
Die Layout-PDF `results/continuation_20260909/word_layout_final/report.pdf` enthält
52 Seiten, davon Kapitel 6 auf den arabisch nummerierten Seiten 29–37.
Der Strukturbericht heißt `docx_structure_check_final.json`; die 76 aktualisierten
Seitenfelder stehen im `docx_page_reference_cache.json` desselben Ergebnisordners.
Alle **293** im Ausgangsmanifest erfassten Rohdaten-/Modell-/Ergebnisdateien sind
nach der Bearbeitung hashidentisch; Beleg: `preservation_and_status_final.json`.
Der eigens gestartete Dokumentrenderer wurde anschließend beendet. Es wurde
kein Commit erstellt und nichts gepusht.

## Weitere Zustandsänderung: Übernahme der Lüftersteuerung

Der Nutzer meldete anschließend einen Start durch `pinctrl set 18 op dh`
und beobachtete einen Lauf mit voller Leistung. Damit ist die zuvor angefragte
Stillstandsbedingung ausdrücklich aufgehoben. Dies ist eine Nutzerbeobachtung,
keine gemessene Drehzahl oder Leistungsaufnahme. Der tatsächliche Zeitpunkt
seines Steuerbefehls wurde nicht mitgeliefert. Zugleich autorisierte der Nutzer
die softwareseitige Steuerung durch den Agenten für die vereinbarten Prüfungen;
er soll keine Steuerbefehle mehr selbst eingeben müssen.

Die erneute Prüfung umfasste vorhandene Code-/Bootdokumentation, GPIO-/physische
Pinnummern, laufende Dienste, offene Sensor-/GPIO-Geräte und PWM-Sysfs. Die lokale
Abfrage `pinctrl -p get 12,18` bestätigt: **GPIO18 = physischer Pin 12**,
**physischer Pin 18 = GPIO24**. Ohne `-p` verwendet `pinctrl` GPIO-Nummern.
Der vorhandene RP1-PWM0-Kanal ist `pwmchip0/pwm2`; GPIO18 verwendet dafür `a3`
beziehungsweise `PWM0_CHAN2`. `/boot/firmware/config.txt` enthält bereits
`dtoverlay=pwm`; es wurde kein Overlay geändert und kein Kanal neu exportiert.
Die Pythonbibliothek `rpi_hardware_pwm` war in den geprüften Umgebungen nicht
vorhanden. Die vorhandene Kernel-Hardware-PWM ist trotzdem über Sysfs zugänglich.

Vor dem Eingriff war kein Steuer-/Erfassungsprozess erkennbar. Ein früherer
lesender Zugriff zeigte GPIO18 als Digitalausgang High, eine spätere Abfrage
bereits wieder `a3`, noch vor dem eigenen ersten Schreibzugriff. Herkunft und
Zeitpunkt dieser zwischenzeitlichen Muxänderung sind nicht belegt. Der Aufbau
ist laut Nutzer angeschlossen; eine vollständige Schaltungs- und
Montagebeschreibung fehlt weiterhin. Insbesondere ist kein Tachokanal bestätigt.

### Tatsächlich ausgeführtes Ausschalten

Nach ausdrücklicher Ankündigung wurden am **09.09.2026, 18:23:45 UTC
(20:23:45 CEST)** folgende Schritte journalisiert ausgeführt:

1. GPIO18 mit `pinctrl set 18 op dl` auf digitalen Low-Ausgang setzen.
2. Am vorhandenen `pwmchip0/pwm2` die Tastzeit auf `0` ns setzen und
   `enable=1` schreiben; die vorhandene Periode von 40.000 ns und Polarität
   `normal` beibehalten.
3. GPIO18 mit `pinctrl set 18 a3` der Hardware-PWM wieder zuordnen.
4. Rücklesen: `duty_cycle=0`, `period=40000`, `enable=1`, `polarity=normal`,
   `GPIO18 = PWM0_CHAN2`, Low. Anschließend zehn Sekunden Auslaufzeit abwarten.

Die Stellvorgabe beträgt damit **0 % bei 25 kHz**. Sie ist nicht gleichbedeutend
mit bestätigtem mechanischem Stillstand. Der Nutzer wurde um Sichtbestätigung,
die noch fehlende Montagebeschreibung, den ausdrücklich gewünschten nächsten
PWM-Prüfwert und Angaben zu einem gegebenenfalls vorhandenen Tacho gebeten.
Aus der früheren Halbierung wird kein Sollwert abgeleitet. Bis zu dieser
Rückmeldung wird keine kontrollierte Stillstandsaufnahme begonnen.

Belege: `results/fan_control_20260909/control_events.jsonl` (UTC und monotone
Hostzeit je Ereignis, angeforderte Befehle, Rückgabestatus und Rücklesewerte)
sowie `preflight_after_shutdown.json`. Fehlende mechanische Zustands- oder
Drehzahlbelege sind dort ausdrücklich nicht als erfüllt markiert. Das Journal
unterscheidet Nutzerangabe, Steueranforderung, Ausführungsresultat und
Register-/Pinrücklesung. Keine Messaufnahme oder Modellbildung erfolgte dabei.

Vor der weiteren Wordbearbeitung wurde die zuletzt geprüfte Fassung als
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_steuerungsuebernahme_20260909.docx`
gesichert, SHA-256
`e3ecba898af615b8c6975801e97573e61cb68668b9a3a86305506db6297ac614`.
Die frühere Ausgangskopie und alle historischen Messprotokolle bleiben erhalten.

### Eingegangene Nutzerantwort nach dem Ausschalten

Der Nutzer hat den vollständigen Stillstand anschließend mit „ja“ per
Sichtprüfung bestätigt. Er benennt den Lüfter als ARCTIC P12 Pro PST (120 mm),
eine getrennte externe 12-V-Versorgung, GPIO18 als Steuersignal sowie
Jumper-/Adapterverbindungen. Der ADXL345 ist laut Beschreibung über I²C
verbunden und in unmittelbarer Nähe des Lüfters befestigt. Der gewünschte erste
Betriebspunkt wurde ausdrücklich mit **25 %** angegeben. Dies ist ein neuer
bestätigter Sollwert, kein rückwirkender Nachweis der früheren Halbierung.

Die konkrete Befestigungsart/-fläche, Achsenausrichtung und Lüfterfixierung
wurden durch die Komponentenbeschreibung noch nicht beantwortet und gezielt
nachgefragt. Auf die Tachofrage antwortete der Nutzer „Ja GPIO18“. Diese Angabe
wird unverändert als Nutzerangabe gespeichert, ist aber mit der Verwendung
von GPIO18 als PWM-Ausgang nicht als unabhängiger Tachoeingang vereinbar.
Das Herstellerblatt unterscheidet am Lüfterstecker Pin 4 (PWM) und Pin 3 (Tacho).
Der Nutzer wurde um bloßes Nachsehen der tatsächlichen Zuordnung gebeten,
ohne Umstecken oder Neuaufbau. Bis zur Klärung wird GPIO18 nicht als
Tachoeingang umkonfiguriert und der 25-%-Betriebspunkt noch nicht angefahren.
Der Stellwert bleibt 0 %. Die neue Stillstandsaufnahme wartet auf die
konkretisierte Montagebeschreibung.

### Weitere Softwarearbeit bei unverändertem Prüfstand

Der neue Hardware-PWM-Steuerweg `src/fan_pwm.py` prüft die lokale RP1-Zuordnung,
hält eine Prozesssperre und protokolliert Stellanforderungen samt Rücklesung.
Der vorhandene `FanController` und die TFLite-Abschaltdemonstration verwenden
nun denselben Steuerweg. Der Entwicklungsadapter fordert bei regulärem Ende
und Erfassungsfehlern 0 % mit weiterhin aktiviertem Kanal an und gibt die Sperre
frei. Unbestätigte Befehle führen zu unbekanntem Stellstatus, nicht zu einer
Stillstandsbehauptung. Die GUI-Einrichtung erfolgt erst am GUI-Programmeinstieg.

Die reine Software-Regression umfasst nun **106 bestandene Tests und zwölf
Untertests**; davon 28 neue Backend- und 17 Adapterprüfungen. Beleg:
`results/fan_control_20260909/software_tests_final_v3.xml`. Der anfängliche
Importkonflikt mit der GUI und die anschließenden erfolgreichen Läufe sind
in den vorherigen XML-Berichten desselben neuen Ordners erhalten. Diese
Prüfungen verwendeten keine echte Sensor- oder Lüfterhardware. Der neue
Backend-Steuerweg wurde am Pi bisher ausschließlich lesend auf die bestehende
0-%-Vorgabe geprüft; die tatsächlich zuvor ausgeführten Stellbefehle stehen
separat im unveränderten Steuerjournal.

Die nachfolgende Aufforderung „weitermachen“ beantwortete die offenen Fragen
zu konkreter Montage und PWM-/Tachosteckerzuordnung nicht. Sie wurde als Auftrag
zur weiteren unabhängigen Software- und Dokumentarbeit umgesetzt. Der Lüfter
wurde dabei nicht erneut eingeschaltet. Der Stillstand ist als Nutzerbeobachtung
bestätigt, D₁ ist mit 25 % festgelegt. Neue Pilotaufnahmen, Parameterentscheidung,
Trainings-/Validierungsdaten und Evaluation bleiben noch ausstehend.

Die zusätzliche unabhängige Adapterprüfung führte zu drei weiteren Korrekturen:
Auch ein Fehler beim Stoppen des Erfassungs-Threads überspringt die Aktor-/
Sensor-/Journal-Abschlussbehandlung jetzt nicht mehr; die Abschlussmeldung nennt
die tatsächlich angeforderte 0-%-Vorgabe; ein fehlgeschlagener realer Stopbefehl
wird im Ereignis nicht als Dry-Run bezeichnet. Die Ereignisse grenzen bestätigte
PWM-Befehle ausdrücklich von ungemessenem mechanischem Stillstand ab.
Die abschließende Regression umfasst **113 bestandene Tests und zwölf Untertests**,
darunter 28 Backend- und 24 Adapterprüfungen. Maßgeblicher Beleg ist
`results/fan_control_20260909/software_tests_final_v5.xml`; vorherige XML-Berichte
bleiben als Entwicklungsverlauf erhalten. Kapitel 6 wurde auf diesen Stand
aktualisiert. Keiner dieser Softwaretests betätigte die echte Hardware.

Die abschließende lesende Kontrolle des Prüfstandes bestätigte weiterhin
`period=40000 ns`, `duty_cycle=0 ns`, `enable=1`, normale Polarität und GPIO18 in
Funktion `a3/PWM0_CHAN2`. Es waren keine passenden Steuer-/Erfassungsprozesse und
keine offenen Zugriffe auf die geprüften I²C-/GPIO-Geräte erkennbar. Das ist eine
Momentaufnahme; sie ersetzt die erneute Prüfung unmittelbar vor der Aufnahme
nicht. Alle **293** im ursprünglichen Erhaltungsmanifest geführten Daten-, Modell-
und Ergebnisdateien sind weiterhin hashidentisch. Beleg:
`results/fan_control_20260909/preservation_and_state_final.json` mit UTC, Boot-ID,
Quellcodehashes und aktueller PWM-Rücklesung. Die neuen Softwarearbeiten erzeugten
keine Sensoraufnahme und kein Training. Die visuelle Stillstandsbestätigung ist
weiterhin als Nutzerangabe, nicht als Drehzahlmessung geführt.

### Abgeschlossene Word-Aktualisierung nach Steuerungsübernahme

Die überarbeitete Nutzerdatei `docs/Akz_Masterarbeit_Bericht(3).docx` wurde nach
Hashprüfung der gesicherten Vorfassung atomar ersetzt. Kapitel 6 dokumentiert
jetzt die Steuerungsübernahme, die visuelle Stillstandsbestätigung, den neu
gewählten Sollwert von 25 %, die weiterhin offenen Montage-/Tachoangaben und die
geprüfte Implementierung einschließlich der 113 Tests und zwölf Untertests.
Die beiden Ausgangskopien bleiben unverändert. Ziel-SHA-256:
`a1f5c1e52ccd0c0babb64d3cc4035e70323fb1fe564d960f1cf6bbb6cf78c995`.

Die neue Layout-PDF umfasst 55 Seiten; Kapitel 6 belegt die arabischen Seiten
29–40. Die 187 XML-Blöcke der Kapitel 1–5 und drei Formelobjekte sind unverändert.
Die fünf neuen Tabellen 6-1 bis 6-5, Überschriften 6.1 bis 6.7, Inhalts- und
Tabellenverzeichnis wurden strukturell und visuell geprüft. Alle fünf neuen
Tabellen stehen vollständig auf jeweils einer Seite; Zelltexte sind nicht
abgeschnitten. 76 Seitenverweise wurden aktualisiert; zwei Renderläufe liefern
identische Positionen für 109 Lesezeichen. Die Prüfung erfolgte mit LibreOffice
und eingebetteten Ersatzschriften, nicht in Microsoft Word selbst.

Belege: `results/fan_control_20260909/docx_final_verification.json`,
`docx_structure_check_final_v2.json` und `word_layout_final_v2/report.pdf` im
selben Ergebnisordner. Der Dokumentrenderer wurde danach beendet. Im
Evaluationskapitel wurden keine Mess- oder Güteergebnisse ergänzt. Ein neuer
Commit oder Push wurde nicht erstellt.

## Abschließende Hardwareklärung und weitere Softwareprüfung

Der Nutzer hat GPIO18 ausdrücklich als Anschluss zur Lüfteransteuerung bestätigt.
Der ADXL345 ist entsprechend der vorgesehenen I²C-Beschaltung angeschlossen und
an einer Ecke des Lüfterrahmens befestigt, um die dort auftretenden Vibrationen
zu erfassen. Diese Angaben werden als feste Randbedingungen übernommen. Die
bisherigen Rückfragen zu Steueranschluss und Sensorbefestigung sind damit erledigt;
ein erneuter Nachweis der Steckerzuordnung oder ein Neuaufbau wird nicht verlangt.
Die generische Montagekennung `fan_frame_corner_adxl345_gpio18_v1` bezeichnet
diesen Aufbau, ohne eine nicht mitgeteilte Ecke, Achsausrichtung oder konkrete
Befestigungsmittel zu erfinden.

Die Bestätigung beschreibt den Aufbau, nicht dessen bereits gemessene
Signalqualität. GPIO18 wird als Steueranschluss geführt; daraus entsteht kein
separater Tachokanal oder Drehzahlmesswert. Die frühere Antwort „Ja GPIO18“ bleibt
als historischer Wortlaut erhalten. Eine unabhängige Drehzahl liegt weiterhin
nicht vor; das Feld bleibt `null`. Dies ist eine Aussagegrenze der Auswertung
und kein erneutes Hardware-TODO zu den bestätigten Punkten.

Die geplante Pilotfolge sowie Training und Evaluation bleiben als nachfolgende
Messaufgaben erhalten. Der jetzige Auftrag betrifft ausdrücklich die weitere
Softwareprüfung und die Wordbearbeitung. Während dieser Arbeit werden keine
PWM-Stellbefehle, Sensoraufnahmen oder Trainingsläufe ausgeführt. Frühere
Messprotokolle werden nicht verändert und frühere Daten nicht rückwirkend als
kontrollierte Stillstandsreferenz eingestuft.

Vor der DOCX-Bearbeitung wurde die letzte geprüfte Fassung gesichert unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_hardwarebestaetigung_20260909.docx`.
Ihre SHA-256 lautet
`a1f5c1e52ccd0c0babb64d3cc4035e70323fb1fe564d960f1cf6bbb6cf78c995`.
Die aktuelle Nutzerangabe und der Sicherungsnachweis liegen gesondert unter
`results/hardware_confirmation_20260909/user_confirmation_and_backup.json`.

### Abgeschlossene Prüfung der FFT-Eingangskontrolle

Die rein softwareseitige Prüfung zeigte, dass `fft_pilot.analyze()` zuvor
unbekannte/leere Qualitätsflags, fraktionale Zeit-/Indexangaben und einen von
der CSV abweichenden Manifest-Samplezähler akzeptieren konnte. Ein nichtendlicher
Schlusswert außerhalb vollständiger FFT-Segmente führte erst nach Schreiben von
`spectra.csv` zum Fehler. Diese Fälle wurden ausschließlich an künstlichen
CSV-Dateien reproduziert; keine Bestandsaufnahme wurde verändert.

Die neue Vorprüfung liest CSV-Felder zunächst als Text, verlangt bekannte
fehlerfreie Flags, die vollständige Indexfolge ab null, passende Samplezahl,
ganzzahlige monotone Hostzeiten und endliche XYZ-Werte einschließlich Segmentrest.
Host-Nanosekunden werden ohne Float-Zwischenkonvertierung verarbeitet. ODR und
Segmentlänge werden ebenfalls geprüft. Ungültige Eingaben scheitern vor Anlage
des Ergebnisordners. Dies verbessert die technische Eingangskontrolle, ohne
bereits eine ausreichende Signalqualität der Messkette zu behaupten.

Die 81 FFT-Tests einschließlich 79 neuer Fälle bestanden. Der erste Gesamtlauf
zeigte drei GUI-Importfehler nach vorheriger FFT-Grafikausgabe. Die TFLite-GUI
wählt deshalb ihren interaktiven Grafikmodus nun erst im Hauptprogramm; ihre
Klassen lassen sich ohne Grafikmoduswechsel importieren. Der abschließende
Gesamtlauf bestand mit **192 Tests und zwölf Untertests**. Belege:
`results/hardware_confirmation_20260909/software_tests.xml` (erster Lauf) und
`software_tests_final.xml` (erfolgreicher Endlauf). Eine reale GUI-Sichtprüfung
oder Prüfung der mechanischen Messqualität wurde damit nicht durchgeführt.

## Fortsetzung der ursprünglich vereinbarten Messfolge

Nach Abschluss der Software- und Wordphase wurden die bestätigten
Hardwarebedingungen für die bereits beauftragte Stillstandsaufnahme übernommen.
Die rein lesende Vorprüfung bestätigte bei unveränderter Boot-ID weiterhin
0 % / 25 kHz / aktivierten PWM-Kanal und GPIO18 in Funktion a3. Es waren keine
konkurrierenden Gerätehalter erkennbar. Der Dokumentrenderer war vor der
Sensoraufnahme vollständig beendet. Die frühere visuelle Stillstandsbestätigung
wurde als weiterhin geltende Nutzerangabe geführt; kein nachfolgender Zustands-
oder Montagewechsel war mitgeteilt. Die Sensoraufnahme wurde ausdrücklich
angekündigt, ohne einen PWM-Stellbefehl auszuführen.

Am **09.09.2026 ab 20:08:39 UTC** wurde die neue 30-s-Aufnahme
`data/controlled_20260909/standstill_20260909_200838.csv` erstellt. Sie ist als
`pilot` und `controlled_standstill` gekennzeichnet. Label −1 bedeutet hier keine
Zuordnung zu einer Normal-/Anomalie-Trainingsklasse; die physische Referenz ist
Stillstand. Sie wird nicht für das Normaltraining des laufenden Lüfters verwendet.

| Größe | Tatsächlicher Befund dieser neuen Aufnahme |
|---|---|
| Status / Samples | completed / 6.193 |
| ODR-Vorgabe / beobachteter FIFO-Durchsatz | 200 Hz / 206,479669 Werte/s |
| Größte Hostzeitdifferenz / FIFO-Füllstand | 7,103851 ms / ein Eintrag |
| Gap / Overrun / Sättigung | jeweils null gesetzte Flags |
| AC-RMS X/Y/Z | 0,006465 / 0,005462 / 0,009024 g |
| Betrag des Achsenmittelwertvektors | 1,100864 g, ohne Offset-/Skalierungskorrektur |
| FFT-Segmentierung | 23 Segmente, Hann, 512 Samples, Schritt 256 |
| Frequenzstützstellenabstand | 0,403281 Hz aus beobachtetem Durchsatz |
| Größte PSD-Stützstelle X/Y/Z | 55,653 / 80,253 / 75,010 Hz; keine Rotationszuordnung |

CSV-SHA-256:
`1f2f5f24ff34ca1f6c1c863daa4d325ef9e98f2e929a66eaf47adb81c5ec25cb`.
Belege in `results/hardware_confirmation_20260909/`:
`standstill_20260909_200838_session.json`, zugehöriges Fan-Journal,
`standstill_quality.json` und `standstill_fft/`. Vor und nach der Aufnahme wurde
0 % zurückgelesen. Null Flags beweisen keine exakte Zahl physikalisch verlorener
Werte. Die Hintergrundaufnahme allein belegt weder Betriebs-SNR noch ausreichendes
Nutzband oder endgültige Messparameter. Die historischen Messprotokolle und Labels
bleiben unverändert.

Danach wurde **Lüfter AN, 25 % PWM bei 25 kHz, zunächst 30 s Einlaufzeit, danach
30 s Aufnahme** angekündigt. Der Nutzer antwortete ausdrücklich **„Ja, bereit“**.
Am **20:11:58 UTC** setzte `FanPWM.set_percent(25)` den Tastgrad auf 10.000 ns bei
40.000 ns Periode; die Rücklesung bestätigte aktivierten Kanal und Hardware-PWM-
Pinzuordnung. Dies war der erste reale Stellaufruf des neuen Backendmoduls.
Die mindestens 30-s-Einlaufphase ist abgeschlossen. Die Betriebsaufnahme wartet
noch auf die separat angefragte Sichtbeobachtung des tatsächlichen Laufs; ein
PWM-Readback wird dafür nicht als Drehzahl- oder Laufnachweis ausgegeben.
Der Steuerprozess hält dabei exklusiv die gemeinsame Sperre. Dies ist eine
Zustandsprüfung nach dem Einschalten, keine erneute Frage zur abgeschlossenen
Verkabelung oder Sensorbefestigung.

### Wordabschluss mit neuem Stillstandsbeleg und aktueller Messbereitschaft

Die Worddatei enthält nun die abschließend bestätigten Hardwarebedingungen,
die erweiterte Softwareprüfung (192 Tests und zwölf Untertests), die neue
kontrollierte Stillstandsaufnahme und den anschließend eingestellten 25-%-
Betriebspunkt. Die Betriebsaufnahme selbst ist weiterhin nicht begonnen; der
Steuerprozess wartet auf die Sichtbestätigung des tatsächlichen Laufs. Daraus
werden keine Betriebs-SNR-, Drehzahl-, Trainings- oder Evaluationsergebnisse
abgeleitet.

Die vor diesem Messnachtrag gespeicherte Wordfassung ist gesichert unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_stillstandsnachtrag_20260909.docx`
(SHA-256 `6d24b0263be60b3845be4e994b66e1bd54f94ef17991caa4e232662e22977f72`).
Die neue Zieldatei hat SHA-256
`b5fb09c6df5bd4020cc6786cd8057a19d6ebb513b780a56131f331e6722e8139`.
Die PDF-Layoutprüfung umfasst 57 Seiten; Kapitel 6 liegt auf den arabischen
Seiten 29–42. Kapitel 1–5 mit 187 XML-Blöcken und drei Formeln sind unverändert.
Fünf neue Tabellen, Überschriften und Verzeichnisse sind strukturell und visuell
geprüft; die Seitenpositionen beider Renderläufe stimmen überein. Prüfbelege:
`results/hardware_confirmation_20260909/standstill_word/word_update_final.json`
und die zugehörigen Render-/Auditdateien. Alle Dokumentrenderer sind beendet.

Für die Fortsetzung hält der laufende Steuerprozess exklusiv den PWM-Lock bei
25 %; keine Sensorerfassung läuft parallel. Der Zustand und die Fortsetzungssperre
sind in `results/hardware_confirmation_20260909/pending_operating_pilot.json`
festgehalten. Erst eine positive Sichtbeobachtung und die Aufnahmeansage geben
die Betriebsaufnahme frei. Die bereits bestätigten GPIO18-/Montageangaben werden
nicht erneut erfragt. Alle 293 im ursprünglichen Erhaltungsmanifest erfassten
Daten-, Modell- und Ergebnisdateien sind weiterhin hashidentisch. Kein Commit
oder Push wurde erstellt.
