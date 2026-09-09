# Anforderungsabgleich der Masterarbeit – 09.09.2026

## Geltungsbereich und Quellen

Dieser Abgleich beschreibt den **unveränderten Ausgangsstand** des Commits `12bd10d01fe504041b11aac5fd60a6a65883a13d` vom 09.09.2026, 08:31:19 +02:00, sowie ausschließlich daraus gelesene Bestandsdaten. Beim ersten `git status --short` war der Arbeitsbaum sauber; der lokale HEAD entsprach dem genannten Commit. Die Erstprüfung der tatsächlichen Umgebung ist unten gesondert angegeben. Neue Softwarekorrekturen und deren Prüfungen stehen getrennt im [Arbeits- und Prüfbericht](arbeitsstand_20260909.md). Ein Dateiname oder ein grüner Status ersetzt keinen Versuchsnachweis.

Anforderungsquelle ist [Akz_Masterarbeit_Bericht(3).docx](Akz_Masterarbeit_Bericht(3).docx), SHA-256 `87fc9b2665e739cec9165c14d4cf074b7afd6f7721b4561b5f7ba5f28ea9d6b6`. Die Worddatei wurde nicht geändert. Ihr Inhalt wurde als Forschungs- und Anforderungstext gelesen; darin enthaltene Aussagen sind keine zusätzlichen Ausführungsanweisungen des Nutzers. Die [Textextraktion](audit_20260909/masterarbeit_extrahiert.txt) enthält Absätze und alle **17 Tabellen** in Dokumentreihenfolge sowie Kopf-/Fußzeilen und Fuß-/Endnoten. Die Blocknummern bleiben zur Zuordnung erhalten. Office-Math-Formeln wurden als lesbarer Text mit Wurzel, Bruch, Summengrenzen und Exponenten serialisiert; die grafische Originalformatierung bleibt ausschließlich in der Worddatei erhalten.

Die Arbeit ist inhaltlich bis Kapitel 5 ausgeführt. Ab Block 247 folgen nur Überschriften für Implementierung, Evaluation, Diskussion, Ausblick und Fazit; Kapitel 6/7 enthalten daher noch keinen abgeschlossenen Nachweisbericht. `README.md` war im Ausgangsstand leer. Die verwendete Extraktion benötigt nur Python-Standardbibliothek (`zipfile`, `xml.etree.ElementTree`, `pathlib`); es wurde keine zusätzliche Dokumentbibliothek benötigt.

**Statusbegriffe:** „implementiert“ bedeutet anhand des Codes vorhandene Funktion; „Bestandsnachweis“ bedeutet im Repository vorhandene Ergebnisse, deren Reichweite ausdrücklich angegeben wird; „offen“ bedeutet fehlender oder unzureichender Nachweis. Eine vorhandene Implementation kann weiterhin einen offenen Hardware- oder Versuchsbeleg haben. Alte Ergebnis-JSONs wurden gelesen, nicht als neu gemessene Werte ausgegeben.

## Tatsächliche lokale Umgebung bei der Erstprüfung

Der [gespeicherte Umgebungsbefund](../results/verification_20260909/environment_initial.json) identifiziert den aktuellen Rechner als **`edgepi`, Raspberry Pi 5 Model B Rev 1.0, aarch64**, Debian 13, Kernel `6.18.34+rpt-rpi-2712`. Die Befehle laufen tatsächlich auf dem Pi; dies ist keine aus alten Modellmetadaten abgeleitete Annahme. Verzeichnis: `/home/malik/masterarbeit-edge-ai`; der dort verwendete Interpreter ist `.venv/bin/python` (Python 3.13.5). Der geprüfte Remote-HEAD entspricht ebenfalls `12bd10…`.

Die aktuelle `.venv` enthält unter anderem TensorFlow 2.21.0, **ai-edge-litert 2.1.6**, NumPy 2.5.1, Pandas 3.0.3, scikit-learn 1.9.0, smbus2 0.6.1 und pytest 9.1.1. Damit unterscheidet sie sich von den historischen Profilangaben (unter anderem NumPy 2.5.2/Pandas 3.0.5 und kein eigenständiges LiteRT). Eine zweite `.venv_tf` ist vorhanden; ihre Prüfung und die konkret verwendeten Startbefehle sind im Arbeitsbericht dokumentiert. Alte Versionsangaben werden nicht stillschweigend auf neue Messungen übertragen.

Der hardwareseitige Lesebefund vor Änderungen lautet: DEVID `0xE5`, BW_RATE `0x0A`, POWER_CTL `0x00`, DATA_FORMAT `0x00`, FIFO_CTL `0x00`; die konfigurierte Bus-1-Taktrate aus dem Device Tree ist 100.000 Hz. Die Register zeigen zum Zeitpunkt der Erstprüfung Standby, nominell 100 Hz, festen ±2-g-Modus und deaktivierten FIFO. Die Busangabe ist eine Systemkonfiguration, keine elektrische Messung des I²C-Takts. **Der aktuelle Registerzustand beweist nicht, welcher Zustand während der alten Augustaufnahmen vorlag.** Ein neuer Sensortest wird ausschließlich mit seinen eigenen protokollierten Einstellungen beurteilt.

## Forschungsfragen und Hypothesen

| Bezug | Festlegung der Worddatei | Einordnung des Ausgangsstands |
|---|---|---|
| FF1, Blöcke 72, 146, 168 | Anforderungen und Auswahl von Aufbau, Sensor, Hardware und Verfahren begründen. | Kapitel 4/5 liefern Anforderungs- und Auswahlargumentation einschließlich Sensitivitätsbetrachtung. Die Nutzwerte sind Entwurfsurteile, keine Leistungsnachweise. Praktische Eignungsprüfungen bleiben offen. |
| FF2, Block 73 | Precision, Recall, F1 und Fehlalarmrate auf denselben Testfenstern mit einheitlicher Normaldatenkalibrierung vergleichen. | Clean-Vergleich für AE und IF vorhanden; RMS fehlt dort. Alte RMS-Kennzahlen stammen aus anderer Datenaufteilung/Darstellung und dürfen nicht daneben als gemeinsamer Vergleich verwendet werden. |
| FF3, Block 74 | Speicher, Rechenleistung und Überschreitungen des Zeitbudgets der lokalen Pipeline. | Keras-/IF- und gesonderte TFLite-Mikrobenchmarks vorhanden. Vollständige Verarbeitung mit Erfassung, Skalierung, Wartezeit, GUI und Rückständen wurde damit nicht nachgewiesen. |
| FF4, Block 75 | Fehlalarmrate bei geänderter Normalbedingung und unveränderter Vorverarbeitung, Modell und Schwelle. | Zwei separat trainierte Profile `fan_25`/`fan_50` sind zwei Referenzen und ersetzen den kontrollierten Betriebspunktwechsel nicht. |
| H1, Block 77 | AE erzielt höheren F1 als RMS; F1-Differenz auf identischer Testmenge, Fehlalarme und übersehene Anomalien bewerten. | **Nicht bestätigt und nicht widerlegt:** Der erforderliche gemeinsame Vergleich fehlte; neue unabhängige Tests fehlen. Bestehende Entwicklungsdaten bleiben explorativ. |
| H2, Block 78 | Empirisches P99 der Latenz vom vollständigen Fenster bis Entscheidung liegt unter `S / f_s`; zusätzliche Fristüberschreitungen zählen. | **Nicht bestätigt und nicht widerlegt:** Eine Inferenzzeit unter nominell 256 ms genügt nicht. Tatsächliche Zeitstempelrate und neue Sensorwerte getrennt prüfen; Vorverarbeitung und Warten einschließen. |
| H3, Block 79 | FPR steigt unter der gewählten geänderten Normalbedingung bei unveränderter Pipeline. | **Nicht bestätigt und nicht widerlegt:** Kontrollierter Versuch mit identischen Artefakten fehlt. Einen beobachteten Unterschied nur bei kontrollierter Montage, Temperatur und weiteren Einflüssen dem Betriebspunkt zuordnen. |

Block 76 und Block 246 erklären bereits zur Entwicklung verwendete Daten ausdrücklich als explorativ. Unabhängige Bestätigung benötigt neue Testaufnahmen und ein **vor deren Auswertung festgelegtes** Protokoll. Ein nachträgliches Entfernen schwieriger Testzustände oder Verändern von Schwellen anhand ihrer Ergebnisse würde diese Unabhängigkeit aufheben.

## Anforderungen aus Kapitel 4 (Tabelle 4-1, Block 165)

| ID / Priorität | Implementiert im Ausgangsstand | Vorhandener Nachweis und Grenze | Noch offen |
|---|---|---|---|
| A1 MUSS – Messqualität | XYZ in g, relative Zeitstempel und Dateikennung; ADXL345-ID-Prüfung und Messmodus in `src/adxl345.py`. | 16 Profilaufnahmen mit je 30.000 CSV-Zeilen, monotonen Zeitstempeln; Hashintegrität geprüft. Profilmetadaten weisen unkonfigurierte ODR selbst aus. Identische Folgetupel und große lokale Zeitlücken vorhanden, siehe Tabelle unten. | ODR/Bandbreite/Messbereich lesen und explizit setzen; neue Werte über Sensorstatus/FIFO nachweisen; Zeitstempelbedeutung, Verluste, Sättigung, Rauschboden/SNR und Montage prüfen. Akzeptanzgrenzen vor Tests. |
| A2 MUSS – Aufnahmegetrennte Datenbasis | `prepare_clean_comparison_data.py` ordnet komplette Dateien vor Fenstern zu; `calibrate_and_train.py` trennt Profilaufnahmen und passt StandardScaler an normale Trainingsdaten an. | Clean-Manifest: 2 Training / 1 Validierung / 3 Test; Profile: 6/2 bzw. 7/1. Dateien zwischen diesen jeweiligen Splits disjunkt. | Alte `processed_real`-Pipeline arbeitet fensterweise und verletzt die Aufnahmegruppierung; nicht für abschließenden Vergleich nutzen. Neue Testdateien vor Auswertung fest zuordnen; Herkunft vollständig dokumentieren. |
| A3 MUSS – Einheitlicher Vergleich | Clean-AE und IF verwenden gemeinsame standardisierte 128×3-Fenster, Schritt 128; IF flach in C-Reihenfolge; P99 Normalvalidierung. | Clean-Test: 702 Fenster aus denselben drei Aufnahmen. | RMS auf exakt diesen Fenstern und derselben Skalierung ergänzen; bei neuen Läufen explizite Quantilmethode, Labels und unvollständige Fenster festschreiben. |
| A4 MUSS – Automatisch lokal | Live-TFLite-Monitor, GUI und Profilauflösung; keine Cloud-Inferenz im Code. | Historische Live-CSV enthalten Score, Schwelle, Klassifikation und Teilzeiten. | NaN/Inf/fehlerhafte Rekonstruktionen müssen INVALID/ERROR sein. Im Ausgangscode kann `int(nan > threshold)` NORMAL liefern. Datenerfassung/Verarbeitung unter realer Last zusammen prüfen. |
| A5 MUSS – Zuordnung | Profilhashes, Split-Manifeste, Modell-/Scaler-/Schwellendateien und Paketangaben vorhanden. | Hashes der 16 Rohdateien sowie beider Scaler, Keras-, TFLite- und Schwellendateien stimmen mit Profilmetadaten überein. | Live-CSV benötigen maschinenlesbare Lauf-/Code-/Profil-/Modell-/Scalerstände, tatsächliche Schwelle samt Herkunft, Messkonfiguration und Rohdatenzuordnung. Alter Profilname belegt weder PWM-Verlauf noch RPM. |
| A6 MUSS – Zielkompatibilität/Konvertierung | Float32-TFLite mit Builtin-Operationen; Form-/Datentypprüfungen; Profilkonsistenzvergleich Keras/TFLite. | Gespeicherte Konsistenzberichte für beide Profile: Grenzen Rekonstruktion 1e-3, MSE 1e-4, 0 unterschiedliche Entscheidungen eingehalten; Werte unten. Historische Metadaten nennen Pi 5/aarch64. | Neue Umgebung und tatsächlich ausgeführtes Modell prüfen; historischer Metadateneintrag belegt nicht den aktuellen Ausführungsrechner. Vor neuen Tests Prüfdaten und Akzeptanzgrenzen fixieren. |
| A7 MUSS – P99 < S/f_s | Vorhandene Inferenzstoppuhren und Offline-Perzentile. | Separate Keras-, IF- und TFLite-Zeiten, jedoch mit bereits skalierten Fenstern und nominellem 500-Hz-Budget. | Vollständige Latenz ab letzter Fenstermessung einschließlich Pufferwartezeit/Skalierung/Score/Entscheidung; P95/P99, Überschreitungen und Erfassungspausen. Kein H2-Nachweis aus den vorhandenen Teilzeiten. |
| A8 MUSS – Stabiler Ressourcenbedarf | Separater Benchmarkprozess pro Modell, RSS/CPU-Sampling, Warm-up und Modellgröße vorhanden. | Historische Ressourcenwerte berücksichtigen Framework-RSS; TFLite benötigt dort kompletten TensorFlow-Import. | RMS aufnehmen; vollständige Vorverarbeitung, reale Erfassung, Pufferfüllstand, verworfene Fenster und RSS/CPU über dokumentierte längere Dauer prüfen. Begrenzter Puffer verhindert nur unbeschränkten Speicherverbrauch, garantiert keine Verlustfreiheit. |
| A9 MUSS – Erkennungsqualität | Clean-AE/IF-Konfusionsmatrizen und Kennzahlen gesamt/je Aufnahme; TFLite-Entscheidungsvergleich. | AE/TFLite F1 0,989270 und IF F1 0,988159 auf 702 Entwicklungsfenstern gespeichert. Keine H1-Aussage zu RMS möglich. | Gemeinsames RMS-Ergebnis; neue unabhängige Tests, Klassenanteile, Aufnahmezahlen, je Aufnahme Auswertung; undefinierte Kennzahlen kennzeichnen. Fenster innerhalb einer Aufnahme nicht als unabhängige Messläufe behandeln. |
| A10 MUSS – Normalbedingungswechsel | PWM-Vorgabe im Monitor, mehrere trainierte Profile. | Getrennte Profile vorhanden; kein belegter fester Referenzlauf mit kontrolliertem Wechsel. | Vorher/nachher-FPR bei identischem Modell, Scaler, Schwellen und Montage; tatsächliche Drehzahl separat erfassen; neue normale Betriebspunktaufnahme mit Label 0. Nachkalibrierung allenfalls eigener Versuch. |
| A11 MUSS – Reproduzierbarer Aufbau | PWM-gesteuerter Lüfter und Sensorzugriff im Code; Nutzer bestätigt aufgebauten Prüfstand. | Datenlabels `normal`, `tapping_shaking`, `unbalance` vorhanden; Clean-Manifest dokumentiert ausgeschlossene falsch gelabelte Aufnahme. | Aufbau/Montage, konkrete reproduzierbare und rücksetzbare Zustände, RPM und Versuchsablauf festhalten. Globales Aufnahmelabel ist kein Beleg dafür, dass in jedem Fenster kontinuierlich eine Störung bestand. Keine Zustandsänderung ohne Rückmeldung des Nutzers herstellen. |
| A12 KANN – GUI; bei Umsetzung prüfen | Start/Stopp, Score/Schwelle/Entscheidung und PROFILE/P99 bzw. MANUAL vorhanden. | Historische GUI-CSV existieren. | Letzten Ergebniszeitpunkt, Fehler und Veralterung sichtbar machen; Anzeige mit gespeicherten Werten vergleichen; Zusatzlast mit/ohne GUI bei sonst gleichen Bedingungen messen. |
| A13 MUSS – Geordnetes Beenden | Start/Stopp und exklusiv erzeugte Live-Logs, `finally` für Bus vorhanden. | Bestandslogs enthalten vollständige Zeilen, jedoch kein gezielter Beleg aller Abbruchfälle. | Aufnahmeschleifen sammeln im Ausgangscode im RAM; Ctrl+C vor Rückgabe kann Daten verlieren. Vollständige Rohmessungen laufend sichern, Teillauf kennzeichnen, ausstehende Fenster sichern/abarbeiten und Stopp/Abbruch testen. |

## Entscheidungen aus Kapitel 5

- Prüfstand: PWM-Lüfter; konkrete Entwurfsvariante **ARCTIC P12 Pro PST** (Block 192). Dies ist eine Dokumentfestlegung, kein im Audit unabhängig identifizierter Hardwaretyp. PWM ist eine Stellgröße; RPM muss gemessen werden. Der zweite normale Betriebspunkt soll bei unveränderter Montage untersucht werden.
- Sensor: ADXL345 mit I²C als zu prüfende Ausgangswahl. Ein Wechsel zu ADXL355/IEPE ist nur bei nachgewiesener unzureichender Messqualität begründet und derzeit kein offener Implementierungsauftrag. Die in Block 199 genannten I²C-Grenzen sind Anforderungs-/Datenblattbezug, kein Nachweis der aktuellen Busfrequenz.
- Plattform: Raspberry Pi 5; Nutzwert 3,70 begründet die Auswahl, nicht die Laufzeit. Kein zusätzlicher Plattformvergleich für den Kernversuch erforderlich.
- Gemeinsame Eingabe: dreiachsige Zeitfenster; Standardisierung je Achse ausschließlich anhand normaler Trainingsdaten. Autoencoder rekonstruiert diese Fenster; IF verarbeitet dieselben Werte flach in fester Reihenfolge. **RMS = `sqrt(mean(square(X_standardisiert)))` über alle `3H` Werte**, dimensionslos (Block 223). Das ist nicht der RMS der Beschleunigungsnorm in g aus der alten Baseline.
- Schwellen: je Methode `score > P99` anomal, Gleichheit normal. Kapitel 5 fordert die Dokumentation der genauen Quantilregel; der Bestands-Code verwendet lineare empirische Quantilsinterpolation. Diese Regel vor neuen Tests explizit festschreiben. Große Werte bedeuten für alle Verfahren auffälliger; IF nutzt negierte `score_samples`. Kalibrierung auf separaten normalen Validierungsaufnahmen, Testdaten danach unverändert auswerten.
- Neuronaler Pfad: TensorFlow/Keras → **Float32-TFLite, ohne Quantisierung** (Blöcke 239/240). Die Software-Nutzwertmatrix weist Gleichstand separater Inferenzwege aus; keinen unbelegten Vorteil in Geschwindigkeit oder RAM daraus ableiten.
- FFT: ergänzende Offline-Pilotanalyse (Blöcke 218/219), keine vierte Modellvariante. Vorhandener Ausgangspunkt ist `calculate_features()` in `src/preprocessing.py`: Mittelwertentfernung, `rfft`, Frequenzstützstellen und dominante Frequenz. Bisher nutzt er nominell 500 Hz, keine dokumentierte Fensterfunktion/Amplitudennormierung und keine geprüfte Frischwertfolge. Damit ist die Auswahl von Bandbreite/Fensterdauer noch nicht begründet.
- GUI ist optional; nach Umsetzung sind Aktualität, Logübereinstimmung und Zusatzlast zu prüfen. Eine Detektion darf im Kernvergleich den Versuchszustand nicht unbemerkt verändern. `live_monitor.py` enthält amplitudeabhängige Abschaltung; `live_tflite_fan_control.py` eine bestätigungsabhängige Abschaltung. Diese Steuerexperimente getrennt kennzeichnen und nicht als neutralen Vergleichsbetrieb verwenden.

## Bestandsprofile und reproduzierte Integritätsprüfungen

| Merkmal | fan_25 | fan_50 |
|---|---:|---:|
| Normalaufnahmen | 8 | 8 |
| Training / Validierung | 6 / 2 | 7 / 1 |
| Trainingsfenster / Validierungsfenster | 1.404 / 468 | 1.638 / 234 |
| Fenster / Schritt, Messpunkte | 128 / 128 | 128 / 128 |
| Gespeicherte AE-P99-Schwelle | 0,18673839128379896 | 0,22105744905736202 |
| P99 aus gespeicherten Validierungs-MSE erneut berechnet | exakt gleich | exakt gleich |
| Größte gespeicherte Abweichung Keras/TFLite-Rekonstruktion | 3,0994415283203125e-6 | 2,9802322387695312e-6 |
| Größte gespeicherte Abweichung Keras/TFLite-MSE | 4,904852554665773e-8 | 4,925008961764732e-8 |
| Gespeicherte Entscheidungsabweichungen | 0 | 0 |

Geprüft wurden alle 16 Rohdatei-Hashes gegen `profile.json` und je Profil Scaler, Keras-, TFLite- und Schwellendatei. Die genannten Konvertierungsabweichungen sind **historisch gespeicherte Resultate**, keine in diesem Audit neu ausgeführte Modellinferenz. Die P99-Nachrechnung wurde tatsächlich aus `validation_reconstruction_errors.csv` durchgeführt: sortierte Scores, Index `0,99 * (n-1)`, lineare Interpolation zwischen den Nachbarwerten. Die Werte stimmen exakt mit `selected_threshold` überein.

Die numerisch ähnlichen Profilresultate dürfen nicht mit `models/clean_comparison` verwechselt werden: Dessen AE-Schwelle ist **0,2185792346784422**, IF-Schwelle **0,4776322723194337**; andere Rohdaten, Modelle und Skalierung. Ein Profilwechsel ist keine reine Änderung der PWM-Vorgabe.

### Zeitstempel und identische Folgetupel der Rohaufnahmen

Neu berechnete Bestandsprüfung mit Python-`csv`: `f_poll = (n-1)/(t[-1]-t[0])`; Gleichheit aller drei gespeicherten Achswerte zweier Nachbarzeilen; `dt = diff(timestamp_s)`. Alle Dateien haben 30.000 Zeilen und strikt steigende Zeitstempel. Die Zahl `dt > 4 ms` ist eine **explorative Zählgrenze** von zweimal dem nominellen Pollingintervall und kein vorab festgelegtes Akzeptanzkriterium für die neue Testserie.

| Profil / Aufnahme | Mittlere Pollingrate Hz | Identische Folgetupel % | dt > 4 ms | Größtes dt ms |
|---|---:|---:|---:|---:|
| fan_25 / normal_001 | 499.999557 | 79.413 | 1 | 4.7477 |
| fan_25 / normal_002 | 499.999554 | 79.456 | 1 | 81.5604 |
| fan_25 / normal_003 | 499.999552 | 79.439 | 0 | 2.0545 |
| fan_25 / normal_004 | 499.999551 | 79.429 | 0 | 2.0542 |
| fan_25 / normal_005 | 499.999552 | 79.409 | 0 | 2.0557 |
| fan_25 / normal_006 | 499.999550 | 79.449 | 1 | 4.2563 |
| fan_25 / normal_007 | 499.999542 | 79.396 | 0 | 3.6971 |
| fan_25 / normal_008 | 499.999550 | 79.413 | 0 | 2.0559 |
| fan_50 / normal_001 | 499.999557 | 79.423 | 6 | 6.2190 |
| fan_50 / normal_002 | 499.999500 | 79.416 | 3 | 78.6723 |
| fan_50 / normal_003 | 499.999547 | 79.393 | 0 | 2.0814 |
| fan_50 / normal_004 | 499.999565 | 79.379 | 14 | 5.4342 |
| fan_50 / normal_005 | 499.999318 | 79.366 | 112 | 9.6216 |
| fan_50 / normal_006 | 499.999553 | 79.359 | 6 | 6.3587 |
| fan_50 / normal_007 | 499.999549 | 79.399 | 2 | 5.4801 |
| fan_50 / normal_008 | 499.999542 | 79.329 | 0 | 2.4422 |

Knapp 79,4 % identische Nachbar-XYZ-Werte sind mit wiederholtem Lesen alter Ausgaberegister vereinbar. Gleiche Werte können aber auch aufgrund der Quantisierung bei **neuen** Messungen auftreten. Deshalb weder die Zahl der Änderungen als exakte Sensorrate ausgeben noch aus einer angenommenen Einschaltkonfiguration rückwirkend 100 Hz als gemessene ODR behaupten. Die vorhandenen Dateien dokumentieren keine DATA_READY-/FIFO-Ereignisse oder Registerstände. Die größten Zeitlücken zeigen zusätzlich, dass ein Mittelwert um 500 Hz die zeitliche Regelmäßigkeit nicht belegt. Die gemessenen g-Minima/Maxima liegen bei diesen 16 Dateien insgesamt innerhalb −1,326 bis +0,1131 g; dies belegt ohne dokumentierten Messbereich und Rohzählwerte keine formal bestandene Sättigungsprüfung.

### Abweichende Live-Schwellen

| Profil / CSV unter `results` des Profils | Wirksame Schwelle | Fenster |
|---|---:|---:|
| fan_25 / `live_tflite_gui_20260825_161256_644777.csv` | 0.3 | 5073 |
| fan_25 / `live_tflite_gui_20260826_103431_951170.csv` | 0.3 | 78 |
| fan_25 / `live_tflite_gui_20260826_140730_902708.csv` | 0.3 | 10244 |
| fan_25 / `live_tflite_gui_20260826_145133_447866.csv` | 0.3 | 82 |
| fan_25 / `live_tflite_gui_20260826_145235_456535.csv` | 0.9 | 7209 |
| fan_50 / `live_tflite_gui_20260824_111345_708897.csv` | 0.3 | 88 |
| fan_50 / `live_tflite_gui_20260824_111418_322717.csv` | 0.3 | 4948 |

Diese Dateien werden bewahrt und als Entwicklung mit abweichender Schwelle eingeordnet. Die historischen CSVs enthalten die tatsächlich verwendete Zahl, aber keine maschinenlesbare Herkunft `MANUAL` und keine Artefakthashes. Eine Abweichung vom P99 ist belegt; ihre konkrete Bedienhandlung lässt sich aus der CSV allein nicht nachträglich beweisen. Schwelle **0,9** ist ein zusätzlicher Befund gegenüber den in der Anfrage genannten 0,3-Läufen. Für den abschließenden P99-Vergleich dürfen solche Ergebnisse nicht mit unveränderten P99-Entscheidungen vermischt werden.

### Weitere Widersprüche und Reichweite gespeicherter Ergebnisse

1. **Alte RMS-Daten sind nicht der Clean-Vergleich.** `results/baseline_metrics.json` enthält 92 Testfenster mit 85 normalen und 7 anomal gelabelten Fenstern; der Clean-Vergleich enthält 702 mit 234 normalen und 468 anomal gelabelten Fenstern. RMS wird dort aus der Beschleunigungsnorm `signal` und 500er-Fenstern gebildet, während Kapitel 5 128×3 standardisierte Ausgangsfenster verlangt. Seine F1=0,833333 ist daher kein zulässiger direkter Vergleich mit Clean-AE F1=0,989270.
2. **Aufnahmegruppen sind in der alten Pipeline tatsächlich geteilt.** `data/processed_real`: `normal_20260817_100640.csv` kommt in Training und Validierung vor; `normal_20260817_111818.csv` in Validierung und Test; `anomaly_20260725_185423.csv` in Training und Test. Letzteres bedeutet, dass normale Fenster einer teilweise anomal gelabelten Datei ins Training gelangten; es beweist keine Anomalielabels im Training. Ganze Aufnahmen sind gleichwohl nicht getrennt. Die neuere Clean-/Profilaufteilung behebt diese Gruppierungsfrage für ihre eigenen Daten.
3. **Dateinamen sind kein RPM-Beleg.** Profile heißen `fan_25`/`fan_50`, aber die 16 Aufnahme-Metadatensätze enthalten keine gemessene Drehzahl und keinen protokollierten PWM-Zeitverlauf. Der vorhandene CLI-Schalter `live_monitor.py --fan-pwm` ist implementiert; die übrigen Messprogramme lesen daraus nicht automatisch einen gesicherten Betriebspunkt.
4. **Benchmarks messen verschiedene Grenzen.** `results/resource_comparison.csv` enthält Keras-AE P99=48,89266026 ms und IF P99=28,55421636 ms; `results/tflite_resource_metrics.json` enthält TFLite P99=0,13963107 ms. Diese historischen Werte stammen aus Teilmessungen an bereits standardisierten Fenstern, ohne Live-Erfassung, ohne nachfolgende Fensterwartezeit, ohne GUI. Sie werden nicht als neue Vollkettenmessung oder H2-Bestätigung übernommen.
5. **TFLite-Dateigröße ist nicht Prozess-RAM.** Gespeicherter TFLite-Bericht: 13,75390625 KiB Modelldatei, etwa 599,40625 MiB gesampelter Peak-RSS; Laufzeitbackend `tensorflow.lite.Interpreter` mit vollständigem TensorFlow-Import. Dessen RSS ist nachvollziehbar enthalten. Der Ressourcenteil dauert dort nur 0,137228369 s mit 14 Messpunkten, keine Langzeitstabilitätsprüfung. Keras/IF und TFLite wurden nacheinander in verschiedenen Messphasen ausgeführt, Hintergrundlast nicht kontrolliert.
6. **Fehler können normal wirken.** Der ursprüngliche `infer_window()` prüft nicht die Endlichkeit von Rekonstruktion und MSE. Der Vergleich `NaN > threshold` ergibt falsch und wird zu Label 0. Formprüfung allein genügt daher nicht.
7. **Sequentielle Erfassung lässt Pausen unsichtbar.** `collect_window()` sammelt 128 Pollingwerte, wartet den nominellen Fenstertakt ab, danach folgen Skalierung und Inferenz. Die Zeitstempel werden zu einer mittleren Rate verdichtet und gehen verloren. Während der Auswertung erfolgt kein fortlaufender Sensorabruf; die pro Fenster berichtete Rate zeigt diese Zwischenpausen nicht.
8. **Schutzabschaltung kann die Vergleichsbasis ändern.** Der ursprüngliche `live_monitor.py` hat im Code eine Stoppschwelle von 1,7 g, während `config.yaml` 2,0 g nennt; der Monitor lädt diese YAML nicht. Der effektive Codewert ist maßgeblich. `live_tflite_fan_control.py` verändert den Lüfterzustand nach bestätigter Erkennung. Solche Läufe dürfen nicht unbemerkt als unveränderte gemeinsame Testbasis ausgewertet werden.
9. **GUI-Beschriftung ist nur ein Teilnachweis.** PROFILE/P99 bzw. MANUAL ist implementiert; gespeichert wurden in den alten Logs weder diese Herkunft noch Startkonfiguration, Softwarestand, Rohdaten oder eine Prüfung der Anzeigealterung. Eine lange CSV mit 10.244 Fenstern belegt keine verlustfreie Erfassung, wenn Verluste gar nicht gezählt werden.

## Offene Nachweise und Reihenfolge der nächsten Versuche

1. **Aktuellen Ausführungsrechner prüfen:** Hardwaremodell/Architektur, Git-HEAD/Dirty-Status, Python-Binary und importierbare Pakete, I²C/PWM-Zugang dokumentieren. Die im Repository gespeicherten Pi-Metadaten sind historisch. Ein Lauf auf einem Entwicklungsrechner darf nicht als Pi-Benchmark bezeichnet werden.
2. **Messketten-Pilot am aufgebauten Sensor:** unveränderte Montage fotografisch/textlich zuordnen; Sensorregister lesen und protokollieren, geplante ODR/Bereich/Busgeschwindigkeit abstimmen; neue Messungen über Sensorstatus/FIFO identifizieren; Host-Lesezeit und geschätzte Sensorzeit unterscheiden; Rohzählwerte, Einheiten, Datenlücken, Overruns und Sättigung prüfen. Keine aus Hardware-ODR interpolierten Zeiten als direkt gemessene Sensortimestamps ausgeben.
3. **Rausch- und Normalpilot:** Nutzer stellt den dokumentierten Zustand her und bestätigt ihn. Ruhe/Rauschen und normalen Betrieb getrennt erfassen; PWM-Vorgabe getrennt von tatsächlicher Drehzahl und deren Messmethode protokollieren. Ohne Tachorückmeldung/RPM-Messung `nicht gemessen` dokumentieren, keine Umrechnung PWM→RPM erfinden.
4. **FFT-Pilot:** nur zeitlich geeignete Abschnitte mit überprüfter Erfassung auswerten; Achsen, Mittelwertentfernung, Fensterfunktion, Amplitudennormierung, Fensterlänge und nutzbare Frequenzbandbreite angeben. `Δf=f_s/H` beschreibt Stützstellenabstand; behebt weder Aliasing noch Lücken. Alte Pollingdaten können explorativ visualisiert werden, begründen aber keine geprüfte 500-Hz-Messkette. Bei unregelmäßigen Zeiten Verarbeitung/Verwerfung begründen und Rohzeiten erhalten.
5. **Protokoll vor unabhängiger Testserie fixieren:** Messparameter und Akzeptanzgrenzen aus Pilotdaten ableiten; ganze neue Aufnahmen mit IDs/Zustandsdefinition/Labelbereich, Normalbetriebspunkt, kontrollierten Anomalien, Rücksetzen, Dauer/Wiederholungszahl und Reihenfolge vorab festlegen. H1/H3 nicht anhand nachträglich ausgewählter Testfenster optimieren. Die finalen Fensterparameter/Modelle/Scaler/Schwellen mit Hashes festschreiben. Eine Software-ODR-Korrektur verändert die Datengrundlage; alte Profile nicht stillschweigend als entsprechend neu trainiert ausgeben.
6. **Gemeinsamer Qualitäts- und Ressourcenlauf:** alle drei Methoden auf identischen Fenstern, Schwellen aus Normalvalidierung und keine erkennungsgesteuerte Änderung des Versuchszustands; P95/P99/Fristüberschreitungen ab vollständigem Fenster, Erfassungs- und Pufferverluste, CPU/RSS über definierte Dauer. GUI-Versuch bei gleichen Bedingungen mit/ohne Anzeige separat. Keras-Konvertierungsprüfung getrennt vom finalen TFLite-Ressourcenvergleich.
7. **FF4/H3:** dieselbe eingefrorene Pipeline auf neuem normalem Referenzbetriebspunkt und zweitem normalem Betriebspunkt; ausschließlich der vorher definierte Betriebspunkt wird verändert. Alle Labels bleiben für diesen Versuch normal. FPR je Aufnahme und zusammen vergleichen. Nachkalibrierung/anderes Profil nicht in diesen Hauptvergleich einmischen.

Neue Ergebnisse gehören in neue Laufverzeichnisse; bestehende Daten, Profile und Worddatei bleiben erhalten. Softwaretests und Wiederberechnungen bereits vorhandener Dateien sind hilfreiche Nachweise für die Implementation, ersetzen aber weder den Pilotversuch am Sensor noch die unabhängige Testserie. Solange diese Nachweise fehlen, bleiben H1–H3 offen und die entsprechenden MUSS-Anforderungen teilweise unerfüllt.
