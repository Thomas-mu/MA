# GUI-Codeprüfung zum Dokumentationsstand

Prüfdatum: 13. September 2026. Grundlage ist der im Arbeitsverzeichnis vorhandene Quell- und Artefaktstand. Diese Prüfung verändert weder Implementierung noch Modelle. Es wurden keine GUI gestartet, keine Sensor- oder PWM-Funktionen aufgerufen und keine Modellinferenz ausgeführt. Pfade sind relativ zum Repository. Die Prüfung gespeicherter Lauf- und Testnachweise wird im begleitenden Nachweisaudit ergänzt.

## Zusammenfassender Befund

`src/live_tflite_gui.py` ist eine implementierte, profilgebundene Tkinter-/Matplotlib-Oberfläche für den TFLite-Autoencoder. Eine Darstellung als bloß geplante oder nicht umgesetzte GUI wäre falsch. Ihre Verwendung des bisherigen Profil- und Vorverarbeitungswegs unterscheidet sich jedoch konkret vom eingefrorenen v4-Paket. Die vorhandene Oberfläche kann dieses Paket nicht über ihre bestehende Schnittstelle unverändert und mit identischer Vorverarbeitung einsetzen. Diese Aussage beruht auf Code und Konfiguration, nicht allein auf fehlenden Messprotokollen.

Die Bezeichnung „früherer Prototyp“ ist vertretbar, wenn sie als **profilgebundener Entwicklungsstand außerhalb des finalen v4-Datenwegs** erläutert wird. Sie darf vorhandene Funktionen oder frühere Softwareprüfungen nicht negieren. Die Formulierung im GUI-Modulkommentar, es werde ein „validated“ Sensor-/Inferenzschema wiederverwendet, ist selbst kein experimenteller Nachweis für v4.

## Implementierte Funktionen

| Funktion | Konkrete Implementierung und Grenze | Codebeleg |
|---|---|---|
| Bedienung | Start, Stop und Exit; nach Öffnen automatischer Erfassungsstart; Stop beendet den Erfassungsworker kooperativ. Es handelt sich um Mess-/Anzeigebedienung, nicht um eine Lüftersteuerung. | `src/live_tflite_gui.py:336–348`, `:443–457`, `:536–563`, `:682–697` |
| Status und Kennzahlen | NORMAL, ANOMALY, ERROR und STALE/VERALTET; Profil, MSE, Schwelle und Schwellenquelle, beobachtete Host-Empfangsrate, Inferenzzeit, Fensternummer, Zeitstempel sowie Latenz-/Pufferinformation. Ungültige numerische Entscheidungen werden als ERROR angezeigt. | `src/live_tflite_gui.py:113–122`, `:356–457`, `:583–647`; `src/live_pipeline.py:191–198` |
| Diagramm | Verlauf der letzten höchstens 100 Rekonstruktionsfehler mit Schwellenlinie. Die x-Achse zeigt die Fensternummer; dargestellt wird der Modellscore, nicht der rohe XYZ-Schwingungsverlauf und nicht der physische Vektor-AC-RMS. | `src/live_tflite_gui.py:63–64`, `:394–422`, `:649–664` |
| Entkopplung | Sensorerfassung in eigenem Thread, Inferenz im Worker, Tkinter/Matplotlib im Hauptthread. Erfassungsqueue standardmäßig vier Fenster; bei Überlast wird das neueste Entscheidungsfenster verworfen und separat journalisiert, seine Rohwerte bleiben erhalten. GUI-Queue mit acht Messnachrichten: Bei Überlast wird die älteste Anzeigemeldung entfernt und gezählt. Kontrollmeldungen werden separat vorgehalten. | `src/live_pipeline.py:56–85`, `:92–147`; `src/live_tflite_gui.py:160–211`, `:307–314` |
| Erfassungs- und Entscheidungsprotokolle | Roh-CSV, Entscheidungs-CSV, Ereignisjournal und Run-Manifest; unter anderem Artefakthashes, Qualitätsflags, Prozess-CPU und RSS. GUI setzt `gui_enabled=True`. Diese Instrumentierung ermöglicht zukünftige Messungen, belegt aber keine bereits erfolgte Vergleichsmessung. | `src/live_tflite_gui.py:263–284`; `src/live_tflite_monitor.py:512–544`, `:547–691` |
| GUI-spezifische Instrumentierung | `.gui.csv` protokolliert gezeichnete Entscheidungen, Abschluss des Draw-Callbacks, Entscheidung-/Fenster-zu-Draw-Zeit und Zahl verworfener GUI-Nachrichten. Durch zusammengefasste/verworfene Anzeigen ist nicht jedes Modellfenster zwingend ein separat gezeichnetes Ereignis. | `src/live_tflite_gui.py:565–577`, `:699–720` |
| Synthetischer Selbsttest | Simulierte MSE-Werte ober-/unterhalb der Profilgrenze; Assertions für beide Statusanzeigen, 100-Punkte-Historie, Schwellenlinie und Abschluss. Weder Sensoraufnahme noch echte Rekonstruktion in diesem Modus. | `src/live_tflite_gui.py:230–261`, `:722–785`, `:788–824` |
| Konfiguration | Profil verpflichtend; Standard ist gespeicherte P99-Schwelle, optional temporärer CLI-Override mit Anzeige „MANUAL“. Keine laufzeitliche Methodenwahl RMS/Isolation Forest/AE in dieser Oberfläche; nur AE. | `src/live_tflite_gui.py:739–801` |

## Tatsächlicher Datenweg und Unterschiede zu v4

GUI → `live_tflite_monitor.iter_live_measurements` → ADXL345-FIFO-Frischwerte → `BufferedAcquisition` → 128 XYZ-Punkte → `scale_window` → Float32-TFLite-Autoencoder → MSE/Schwellenvergleich → Protokolle und Anzeige.

Die aktuelle gemeinsame ADXL345-Erfassung ist bereits auf FIFO-Frischwerte und explizite ODR umgestellt. Ein pauschaler Satz „die aktuelle GUI fragt den Sensor softwareseitig mit 500 Hz ab“ wäre daher falsch. Die **Profilmetadaten** stammen aus der früheren 500-Hz-Softwareabfrage. Diese beiden Stände müssen getrennt beschrieben werden.

| Aspekt | Vorhandene GUI | Eingefrorener v4-Datenweg |
|---|---|---|
| Artefaktzugriff | `--profile`; erwartet `profiles/<name>/profile.json`, `status=ready` und dortige Modell-/Scaler-/Threshold-Dateien; prüft deren Hashes und P99-Metadaten. Keine CLI-Option für `pilot_bundle.json`. | Eigenes Bundleformat, `status=ready_development_only`, eigener eingefrorener Vertrag und Artefaktbestand. `load_bundle` prüft Vertrag, Hashes und Übereinstimmung von Vorverarbeitungs-/Scoringquelltext. |
| Vorverarbeitung | Rohachsen zunächst Float32, anschließend `StandardScaler.transform`; keine Entfernung des jeweiligen Achsenmittelwerts im 128er-Fenster. | Ursprüngliche Float64-XYZ; je 128er-Fenster und Achse Mittelwert entfernen; erst danach Float32 und gespeicherte Standardisierung. |
| Zeit- und Fensterbezug | Aufeinanderfolgende 128er-Fenster ab Erfassungsbeginn ohne expliziten PWM-Zeitursprung oder Auswahl `[180,300)`. | Auswahl `[180,300)` s bezogen auf den dokumentierten PWM-Aufruf; 128er-Fenster ab erstem ausgewählten Punkt, Schrittweite 128, keine Überlappung. |
| Methoden | Ein AE mit einer Schwelle, MSE-Verlauf. | RMS, Isolation Forest und TFLite-AE; gemeinsame vorbereitete Fenster und getrennte eingefrorene Schwellen. |
| Qualitätsbehandlung | Lücken-, Überlauf- und Sättigungsflags führen zu ungültiger Entscheidung; Rohdaten bleiben erhalten. | Zusätzlich explizite Vertrags-/Strukturkontrollen und aus Rohdaten abgeleitete Ungültigkeitsgründe; gemeinsame Gültigkeit und Fensterindizes für alle Methoden. |
| Nominale Rate | Alle vier vorhandenen Profile nennen 500 Hz; aktuelle Erfassung standardmäßig 200 Hz. Mismatch wird ohne ausdrücklichen Entwicklungs-Override zurückgewiesen. | Vertrag explizit 200 Hz, ±2 g, volle Auflösung und FIFO-Stream. |

Belege: `src/live_tflite_gui.py:45–58`, `:263–284`, `:739–801`; `src/live_tflite_monitor.py:206–286`, `:393–442`, `:479–509`, `:547–691`; `src/live_pipeline.py:92–147`; `src/pilot_method_comparison.py:24–52`, `:187–215`; `src/independent_normal_test.py:107–147`; `src/pilot_stream_final.py:23–75`; `src/pilot_runtime_final.py:54–95`.

Alle vorhandenen Profil- und Modellpaare unterscheiden sich in den gespeicherten Artefakthashes vom v4-Modell. Geprüfte Profile: `profiles/home/profile.json`, `profiles/home_v001/profile.json`, `profiles/fan_25/profile.json`, `profiles/fan_50/profile.json`. Der eingefrorene Vergleichsanker ist `results/upright_v4_training_pilot_20260911_130614/run_001/frozen/pilot_bundle.json`, SHA-256 `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`.

Ein temporärer Schwellen- oder Sampling-Override stellt keine v4-Kompatibilität her. Auch ein bloßer Austausch der Modell-/Scalerdateien ließe die fehlende Achsenmittelwertentfernung und den abweichenden Zeit-/Fensterbezug bestehen. Die Profilangabe 500 Hz darf nicht als unterstützte aktuelle Sensor-ODR interpretiert werden: `src/adxl345.py:27` und `:122–129` definieren diskrete ODRs ohne 500 Hz und prüfen zusätzlich die I²C-Konfiguration.

## Gezielte Prüfung ohne Hardware

`check_gui_contract.py` extrahiert ausschließlich ausgewählte reine Konfigurations- und Vorverarbeitungsfunktionen per Python-AST aus den tatsächlichen Quelldateien. Das Verfahren vermeidet GUI-, Sensor- und Modellruntimeimporte. Es lädt nur den vorhandenen Scaler und liest JSON-/Artefaktdateien. Vollständige Ergebnisse: `gui_contract_check.json`.

Nachgewiesen wurden:

1. Alle vier vorhandenen Profile lassen sich mit den gespeicherten Modell-/Scaler-/Schwellenhashes auflösen.
2. Der 200-Hz-Standard wird gegen die vier 500-Hz-Profile ohne Entwicklungs-Override erwartungsgemäß zurückgewiesen. Ein Override passiert nur diese Konfigurationsprüfung; er ist kein Integrationsnachweis.
3. Der gespeicherte v4-Scaler stimmt exakt mit den Parametern im Bundle überein.
4. Ein ausdrücklich **synthetisches**, konstantes Fenster mit 128 Wiederholungen von `[0,125; −0,25; −1,0] g` ergibt mit demselben v4-Scaler unterschiedliche Eingaben: Die Legacy-Funktion behält standardisierte konstante Offsets; der v4-Weg entfernt den Gleichanteil bis auf die gespeicherten kleinen Scaler-Mittelwerte. Beide Ergebnisse besitzen die Form 128×3 und den Datentyp Float32. Form-/Datentypgleichheit genügt daher nicht für Vorverarbeitungsgleichheit.

Dieser Gegenbeleg ist keine Sensoraufnahme, kein Modellscore, kein GUI-Funktionstest und kein Laufzeitbenchmark. Er quantifiziert keine tatsächliche Erkennungsleistung. Die Prüfung unterstützt ausschließlich die konkrete Inkompatibilität der aktuellen Vorverarbeitungswege.

## Dokumentationsfolgerung und verbleibende Integration

Im Implementierungskapitel sollten Oberfläche, Entkopplung, Status-/Scoreanzeige, Bedienelemente und vorhandene Protokollierung als umgesetzt beschrieben werden. Der GUI-Plot ist ein MSE-Verlauf. Die GUI hat keine Aktuatorintegration. Profilprüfungen sind vorhanden, beziehen sich jedoch auf die älteren Profile.

Für eine spätere unveränderte Nutzung des v4-Pakets fehlen die Anbindung an dessen Bundle-Vertrag, kanonische Vorverarbeitung und Zeit-/Fensterbildung sowie die Weitergabe seiner Entscheidungen/Qualitätszustände an die Anzeige. Anschließend wären Eingabe-/Score-/Gültigkeitsparität gegen den nachgewiesenen v4-Weg und Vergleichsmessungen mit und ohne GUI unter gleichen Bedingungen erforderlich. Das bloße Eintragen eines neuen Profilnamens wäre dafür unzureichend. In diesem Dokumentationsauftrag wird keine solche Integration implementiert.

Die Existenz von CPU-, RSS- und Draw-Zeitfeldern erlaubt keine Aussage über ihre gemessene Größe. Vorhandene v4-Latenzwerte dürfen der GUI erst zugeordnet werden, wenn die jeweiligen Prozess-/Startprotokolle ihre tatsächliche Beteiligung belegen. Der Vergleich mit und ohne GUI bleibt ohne ein solches zusammengehöriges Messpaar nicht erbracht.
