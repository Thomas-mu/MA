# Live-Anpassung und endliche Messmatrix für das eingefrorene v4-Paket

Status: statische Softwareprüfung und vorbereiteter Nachweisplan. Kein Sensorzugriff, keine PWM-Änderung und kein neuer Ressourcenbenchmark in diesem Auftrag. Laufzeiten der explorativen Datei-Auswertung werden nicht als Inferenzbenchmark ausgegeben.

## Konkreter Implementierungsabstand

| Bereich | Im vorhandenen Code umgesetzt | Für das neue Paket noch erforderlich |
|---|---|---|
| Paketladen | [`pilot_method_comparison.load_bundle`](../../src/pilot_method_comparison.py:197) prüft Paket, Artefakte, Scaler, Schwellen und Implementierungshashes | eigener Live-Einstieg mit genau diesem Loader; das Paket nicht in ein altes `profile.json` umetikettieren |
| Legacy-Live-Konfiguration | [`resolve_live_configuration`](../../src/live_tflite_monitor.py:206) erwartet alte Profile oder `clean_comparison` | expliziter Paketpfad und Vertragsprüfung für v4; Legacy- und Pilotformat getrennt erhalten |
| Erfassungswerte | [`BufferedAcquisition`](../../src/live_pipeline.py:48) schreibt Rohdaten und bildet aktuell mit `np.array(...)` aus Float-Tupeln Float64-Fenster | Float64 verbindlich prüfen; vor der Reduktion F-Anordnung herstellen; keine voreilige Float32-Konvertierung. Der aktuelle Puffer ist nicht pauschal als Float32 zu beschreiben |
| Vorverarbeitung | [`scale_window`](../../src/live_tflite_monitor.py:393) konvertiert rohe Werte nach Float32 und skaliert sie; Fensterzentrierung fehlt | unverändert `center_raw_window` und `standardize_ac` des eingefrorenen Pakets verwenden, nicht die Legacy-Funktion |
| Fenstergrenzen | aktueller Live-Puffer zählt vom ersten erfassten Wert an in 128er-Gruppen | für [180,300) erste Gruppe ab dem ersten Sample mit Hostzeit ≥180 s bilden; nicht nur vor 180 s gebildete Fenster nachträglich filtern. Kein Fenster über Segment-/Aufnahmegrenzen, Roh-Anlauf trotzdem sichern |
| Qualitätsprüfung | aktuelle Live-Inferenz prüft aggregierte Gap-, Overrun- und Sättigungsflags | zusätzlich exakt die gemeinsame Testpolitik: monotone/konsistente Zeiten, Host-Lücken >160 ms, FIFO=32, Rohbereichsgrenzen und NaN/Inf; benötigte Diagnostik je Fenster erhalten |
| Methoden | Live-Monitor und GUI führen TFLite aus | RMS und IF als eigene Scorer mit denselben Eingaben/Metadaten aufnehmen; gemeinsame INVALID-Politik, keine erkennungsabhängige Steuerung im Vergleich |
| Timing | Fensterfertigzeit, Queuewartezeit, Vorverarbeitung und Entscheidungslatenz sind vorhanden | reine Modellaufrufzeit von Transfer/Fehlerberechnung/Schwellenvergleich trennen; aktuelle `infer_window`-Zeit enthält mehr als nur `invoke` |
| CPU/RAM | `ProcessMetrics` erfasst Prozess-CPU (100 %=ein Kern), RSS und Prozesshöchstwert | unabhängige periodische Abfrage auch ohne Entscheidungen; Prozessbaum/Kindprozesse definieren, Initialisierung und stationären Abschnitt trennen |
| Puffer | begrenzte Queue, `drop_newest`, Rohspeicherung, Drop-Ereignisse und Hochwasserstand vorhanden | verlustlose Bilanz über gebildete/ausgewertete/ungültige/verworfene/ausstehende Fenster je Methode; Endreste und geordnetes Leeren prüfen |
| GUI | [`run_live_inference`](../../src/live_tflite_gui.py:263) ruft den Legacy-Pfad; begrenzte Anzeigequeue und Zeichenzeitprotokoll existieren | an neuen Daten-/Scorevertrag anschließen; Anzeige-Drops von Entscheidungs-/Sensordrops trennen; Zusatzlast auf gleichem Material und tatsächlichem Display messen |
| Ressourcen-Skript | [`measure_resources.py`](../../src/measure_resources.py:32) ist auf alte `clean_comparison`-Daten, Keras/IF, 500 Hz und feste alte Ergebnisnamen ausgerichtet | eigener neuer Benchmarkadapter für eingefrorenes RMS/IF/TFLite-Paket und empirisches Fensterbudget; altes Skript nicht als aktuellen Nachweis starten |

Der bisherige Live-Aktorpfad kann aus Erkennungen Abschaltungen auslösen. Er wird für diese Messmatrix nicht verwendet. Die getestete Betriebs-PWM bleibt konstant; ausschließlich der separat freigegebene Versuchsablauf setzt am Ende oder bei Fehlern 0 %. Eine mögliche spätere Abschaltdemonstration ist ein eigener Funktionstest, kein Methodenvergleich.

## Softwareabnahme vor Sensor-Livebetrieb

1. Einen separaten Pilot-Liveadapter erstellen, eingefrorene Quellen und Artefakte unverändert lassen. Paket-, Sensor- und Qualitätsvertrag prüfen, bevor ein Sensor geöffnet oder eine Steuerung aufgerufen wird. Ein reiner Replaymodus darf keine Hardwaremodule aktivieren.
2. Die heute geprüften Originalfenster durch Offline-, Replay- und zukünftigen Live-Fensterpfad führen. Quelle, Anfangs-/Endindex, Float64-Mittelwertentfernung, Float32-AC und skalierte Eingaben müssen exakt übereinstimmen. Scores und Entscheidungen bei gleichem Backend ebenfalls exakt; ein neues Backend benötigt einen separat vorab festgelegten Konvertierungs-/Paritätsnachweis, keine an Testergebnisse angepasste Toleranz.
3. Die Grenzfälle 179,999… s, 180 s und 300 s prüfen: erste zulässige Probe, Reststücke, Aufnahmewechsel. Ein Grenztest muss eine abweichende Fensterphase erkennen; bloß gleiche Fensterzahl genügt nicht.
4. Synthetische Fehler prüfen: FIFO-Vollstand, Zeitlücke, nichtmonotone Zeit, Rohsättigung, NaN/Inf, Inferenzfehler, volle Queue, langsame Verarbeitung, Stop mitten im Fenster, Schreibfehler. Kein solcher Fall darf stillschweigend NORMAL ergeben. Kein automatischer Wiederholungsstart. Bereits vollständige Rohdaten und Ereignisse bleiben erhalten.
5. Rohdaten und Ausgabebilanz prüfen: gebildete Fenster = aus der Queue entnommene + Queue-Drops + noch ausstehende; für jede entnommene Quelle je Methode genau eine gültige oder ungültige Entscheidung. Teilfenster sind gesondert. GUI-Updates dürfen fehlen, die protokollierten Entscheidungen nicht unbemerkt.

Die vorhandenen Softwaretests und die neue Diagnoseparität werden wiederverwendet. Zusätzliche Tests prüfen ausschließlich die tatsächlich neue Integration; es wird weder das Training wiederholt noch die frühere erfolgreiche Konvertierung ohne Anlass erneut ausgeführt.

## Messgrenzen und Metriken

Zeitbasis ist `monotonic_ns`/`perf_counter_ns` mit dokumentierter gemeinsamer Uhr. Je Fenster werden gespeichert:

* `t_first_sample`, `t_window_complete` (letzter XYZ-Leseabschluss), `t_dequeue`, Beginn/Ende Vorverarbeitung, Beginn/Ende reine Modellauswertung, `t_decision`, Zeitpunkt der Protokollierung. GUI zusätzlich Empfang, Zeichenbeginn und `draw_event`.
* Sammelzeit = vollständig − erster Samplezeitpunkt. Sie gehört **nicht** zu H2. Verarbeitungslatenz = Entscheidung − vollständig, einschließlich Wartezeit, Fenstermaterialisierung, Vorverarbeitung, Inferenz und Score-/Schwellenberechnung. Gesamtalter = Entscheidung − erster Samplezeitpunkt. CSV-Ausgabe nach der Entscheidung zählt nicht rückwirkend zur Entscheidungslatenz, kann aber nachfolgende Fenster verzögern.
* Modellzeit separat: RMS-Kernrechnung, IF-`score_samples`, TFLite-`invoke`; Tensortransfer und MSE/Entscheidung zusätzlich ausweisen. Alle drei Methodenzeiten dürfen nicht unter unterschiedlich weit gezogenen Messgrenzen verglichen werden.
* Mittel, Median, P95, P99, Maximum, Zahl/Anteil Fristüberschreitungen. Empirisches H2-Budget **128 / beobachtete XYZ-Rate des jeweiligen Laufs**, ungefähr 0,618 s bei 207 XYZ/s; nominell wären es 0,640 s. Nicht die Sammelspanne von nur 127 Abständen als Schrittbudget einsetzen. Bei Gleichheit ist die strikte H2-Ungleichung nicht erfüllt.
* P99 gültiger Entscheidungen getrennt von ungültigen und fehlenden Entscheidungen berichten. Zusätzlich deren Latenzen, sofern verfügbar, sowie vollständige Fenster ohne gültige Ausgabe zählen. Ein kleines P99 darf Drops oder INVALID nicht verdecken. Nachbarfenster sind keine unabhängigen Ressourcenreplikate; vollständige Prozesse/Läufe werden getrennt berichtet.
* CPU-Zeitdifferenz / Wandzeit mit 100 %=ein Kern; optional separat auf alle Kerne normiert. RSS in MiB, Prozess-/Prozessbaum-Höchstwert, Modell-Dateigröße. Abtastung beispielsweise alle 100 ms; kurze RSS-Spitzen können damit verfehlt werden, `ru_maxrss` enthält auch Initialisierung. Keine Gleichsetzung der Modelldateigröße mit Laufzeitspeicher.
* Host-Leseabstände, Sample-Indizes, FIFO-Belegung, Sensorflags, erfasste Samples, Queue-Drops, Rückstand/Hochwasserstand und Entwicklung über die Zeit, ungültige Ergebnisse, GUI-Nachrichtenverluste und Rohschreibfehler. Exakte physische Sensorverluste bleiben unbekannt, wenn nur Indikatorflags vorliegen. Ein Rückstand darf nicht nur am Ende nach Leeren beurteilt werden.

Messbedingungen: Raspberry Pi 5, exakter Paket-/Code-/Datenhash, Python-/NumPy-/scikit-learn-/LiteRT-Version, ein LiteRT-Thread und IF `n_jobs=1`, festgelegte übrige Threadumgebung, Speicher und Softwarestand, Hintergrundlast, CPU-Frequenz-/Thermal-/Throttlingzustand soweit auslesbar, Versorgung/Kühlung. Kalte Initialisierung, Modell-Warmup und stationäre Messphase getrennt. Vorab z. B. 20 synthetische Inferenzaufrufe je Methode zum Runtime-Warmup; diese sind keine Genauigkeitsdaten. Die mechanischen 180 s sind davon unabhängig.

## Drei klar getrennte Nachweise

| Stufe | Konkreter geplanter Umfang | Was sie belegt | Was sie nicht belegt |
|---|---|---|---|
| Offline-Paritätsreplay | dieselben vorhandenen Float64-Aufnahmen/Fenster; ungepaced; alle Methoden | Eingaben, Scores, Labels, Grenz- und Fehlerbehandlung des neuen Adapters | Sensorerfassung unter Last oder echte Ankunfts-/Wartelatenz |
| Gepacetes Offline-Replay | erste normale Aufnahme vom 12.09., Original-Ankunftsfolge relativ zur Replayuhr; drei neue Prozesse je Methode, je 300 s = 45 min insgesamt | CPU/RAM, Verarbeitungs- und Queuelatenz auf identischem Material; Vergleich bei gleicher Last | I²C-/FIFO-Durchsatz; originale Hostzeitstempel dürfen nicht direkt von der aktuellen Uhr abgezogen werden |
| Sensor-Live, ohne GUI | drei unabhängige 300-s-Normalläufe je Methode bei 75 %, neun Läufe insgesamt; 60 s zusätzliche Auszeit nach jeder Freigabe | gesamte jeweilige Pipeline einschließlich Sensor, Rohschreiber und Inferenz; Ressourcen und Verluste im geprüften Zeitraum | unbegrenzte Dauerstabilität oder punktgenau identische Signale zwischen den Methodenläufen |
| GUI-Zusatzlast, falls Teil des finalen Systems | zuerst dieselben gepaceten Replays mit/ohne Anzeige; danach drei 300-s-TFLite-Live-Läufe mit GUI gegen die drei bereits gemessenen Headless-Läufe | Anzeigeübereinstimmung, Stale-/Drop-Anzeige, Mehrbedarf und Wirkung auf Erfassung | gleiche Signalquelle für physisch getrennte Starts oder sichtbarer Pixelzeitpunkt allein durch `draw_event` |

Die Sensor-Live-Methodenreihenfolge wird vorab ausgewogen festgelegt: Block 1 RMS–IF–AE, Block 2 IF–AE–RMS, Block 3 AE–RMS–IF. Jedes Mal neues Prozess- und Laufprotokoll, keine automatische Neustartschleife. Damit werden Reihenfolgeeinflüsse verteilt, nicht beseitigt. Ein erster Lauf je Methode ist ein Integrationscheck; erst die vorab geplanten Wiederholungen bilden den vollständigen Ressourcenvergleich.

Im Ressourcenlauf wird die gesamte 300-s-Aufnahme gesichert; nach Runtime-Warmup werden Ressourcenverläufe über die komplette Aufnahme und primär [180,300) berichtet. Die Modelleingaben für die primäre Genauigkeitsauswertung beginnen exakt am ursprünglichen 180-s-Segmentanfang. Anlaufwerte und mögliche gesonderte frühe Diagnoseentscheidungen zählen nicht als neue primäre Testfenster. Die bereits gespeicherten älteren Testergebnisse werden nicht ersetzt. Kurze 300-s-Läufe erlauben nur eine Aussage über genau diesen Zeitraum; ein Langzeitnachweis müsste separat begründet werden, nicht als endlose Nachforderung entstehen.

Pro Methode ein separater Prozess vermeidet, dass die nacheinander ausgeführten drei Methoden den jeweiligen Latenz-/CPU-Vergleich gegenseitig verzerren. Ein zusätzlicher gemeinsamer Schattenbetrieb mit allen drei Scorern wäre eine andere, separat zu kennzeichnende Systemlast. GUI-Zeichnen darf nicht auf dem Sensorlesethread laufen. Die aktuelle Rohdatenschreibung findet im Erfassungsthread statt; ihre mögliche Blockierung ist im Sensor-Livebetrieb ausdrücklich mitzuprüfen.

## Bewertung statt Ergebnisoptimierung

H2 wird nur für das tatsächlich geprüfte Paket, die jeweiligen Bedingungen und beobachteten Latenzen beurteilt. P99 ≥ Budget bleibt eine Nichterfüllung; Daten-/Entscheidungsverluste und ungültige Fenster bleiben sichtbar, auch bei günstigem P99. A8 erfordert zusätzlich nachvollziehbar begrenzten Rückstand und Speicherverlauf im Messzeitraum. Kein Schwellenwechsel und keine nachträgliche Auswahl schneller oder genauerer Fenster.

Eine benötigte GUI-Sitzung mit tatsächlichem Displayzugriff ist derzeit für diesen neuen Nachweis nicht bestätigt. Dieser fehlende Punkt wird dokumentiert; alle Headless- und Replayaufgaben können ohne ihn vorbereitet werden. Die vorhandene Legacy-GUI ist keine automatisch validierte Anzeige des neuen Pilotpakets. Wird sie in den finalen Funktionsumfang übernommen, ist der Zusatzlastnachweis nach A12 erforderlich.
