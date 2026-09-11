# Anbindung des vorbereiteten v4-Datensatzes an den Methodenvergleich

Stand: 11.09.2026. Die Softwareanbindung ist implementiert und ohne echtes Training geprüft. Ausgeführt wurden ausschließlich Softwareprüfungen und ein Audit der vorhandenen Messdaten. Es gab keine neue Aufnahme, keine PWM-Änderung, keine Anpassung eines Scalers an Messdaten und kein Modelltraining. Bestehende Dateien einschließlich Worddatei, Originalaufnahmen, früherer Berichte und Modelle bleiben unverändert.

## Ergebnis

Der neue Einstieg [pilot_method_comparison.py](../../src/pilot_method_comparison.py) verbindet den bereits aufbereiteten Datensatz mit der vorhandenen Autoencoder-/TFLite-Trainingsstufe und den vorhandenen RMS-/Isolation-Forest-/TFLite-Bewertungsfunktionen. Die bestehenden Programme wurden dafür nicht verändert. Die frühere Trainingsroutine wird nicht auf ein umetikettiertes Pilotprofil angewendet.

| Einstieg | Implementierte Funktion | In diesem Auftrag ausgeführt? |
|---|---|---|
| `audit` | Quellen und Fenster prüfen; alle originalen Float64-Rohfenster durch die gemeinsame AC-Vorverarbeitung schicken und mit vorbereiteten Arrays vergleichen | Ja, abschließend 582 Fenster exakt reproduziert |
| `train` | Nur Trainingsfenster zum Scaler-Fit; vorhandene AE-Trainings-/Konvertierungsstufe; IF aus denselben standardisierten Trainingsfenstern; RMS-/IF-P99 aus Normalvalidierung; eingefrorenes eigenes Paket erstellen | Nur mit vollständig ersetzten Trainings- und Modellfunktionen auf künstlichen Testdaten; kein echtes Training |
| `replay` | Bestehende Entwicklungsvalidierung mit demselben Paket wiederholen; weder Modelle/Scaler noch Schwellen anpassen | Mit künstlichen Daten und simulierten Modellantworten geprüft; noch kein Replay mit neu trainierten echten Modellen |

Damit gibt es einen konkreten Programmeinstieg für den später freigegebenen ersten Trainingspilot. Ein fertiges neues Modellpaket ist noch nicht vorhanden. Eine unabhängige Erkennungsleistung wurde nicht ermittelt.

## Gemeinsame Datenverarbeitung

Quelle ist ausschließlich [das vorbereitete Pilotpaket](../upright_v4_pilot_preparation_20260911_123511/dataset/manifest.json). Es enthält weiterhin 388 Trainingsfenster aus `normal_before` und `normal_after` sowie 194 Validierungsfenster aus `normal_followup`. Je vollständiger Aufnahmeidentität ist nur eine Gruppe erlaubt. Der Abschnitt bleibt `[180,300)` Sekunden ab PWM-Stellbefehlsbeginn, mit 128 XYZ pro Fenster und Schritt 128. Die Daten stammen von Aufbau v4 bei 75 % PWM und 25 kHz, nominell 200 Hz. Tatsächlicher Host-Durchsatz und offene Zeitbasisgrenzen stehen unverändert im [Vorbereitungsbericht](../upright_v4_pilot_preparation_20260911_123511/preparation_report.md).

Der Adapter lädt die geprüften `*_ac_g.npy` direkt. Er zentriert diese bereits zentrierten Float32-Werte nicht erneut. Beim neuen Rohdateneinstieg `center_raw_window` werden ursprüngliche Float64-Werte achsenweise je Fenster zentriert und erst danach nach Float32 umgewandelt. Float32-Rohfenster werden dort ausdrücklich zurückgewiesen: Bei vorheriger Float32-Rundung lässt sich die ursprüngliche Rechnung nicht mehr bitgenau reproduzieren.

Die gemeinsame Skalierung wird im späteren Trainingspfad genau einmal anhand der AC-Trainingsfenster angepasst. Die Validierung geht nicht in den Scaler-Fit ein. Der exportierte Float32-Transformationsweg wird gegen `StandardScaler.transform` verglichen. Für die Bewertung wird ein standardisiertes Fenster berechnet; jede Methode erhält eine eigene Kopie derselben Werte, damit eine Methode die Eingaben einer anderen nicht verändern kann.

| Methode | Gemeinsame Eingabe | Score |
|---|---|---|
| RMS | Standardisiertes AC-Fenster, 128 × 3 | Wurzel des Mittelwerts aller quadrierten Komponenten |
| Isolation Forest | Dasselbe Fenster, in C-Reihenfolge zu 384 Werten abgeflacht | Negatives `score_samples` |
| TFLite-Autoencoder | Dasselbe Fenster als Float32-Tensor 1 × 128 × 3 | Mittlerer quadratischer Rekonstruktionsfehler, Mittelwert in Float64 |

Diese Scores sind keine Vektor-AC-RMS-Werte in mg aus den 5-s-Pilotgrafiken. Die entsprechende Unterscheidung des Vorbereitungsplans gilt weiter. Nichtendliche Ergebnisse und Erfassungs-/Formfehler führen nicht zu einer NORMAL-Entscheidung. Ein Fehler bei einer Methode wird als INVALID protokolliert und verfälscht nicht die Eingabe der anderen Methoden. Fehlerhafte Schwellen oder eine unvollständige Methodenkonfiguration werden zurückgewiesen.

## Trainings- und Schwellenanbindung

`training_payload` bildet die Datenstruktur für die vorhandene Funktion `calibrate_and_train.write_training_stage`: gemeinsame Features, getrennte Labels und Fenstermetadaten, trainierter Scaler, Herkunftsmanifest und ehrlich als 180–300-s-Auswahl bezeichnete Zeitbasisstatistiken. Die ursprünglichen Zustands-/Aufnahmefelder bleiben erhalten; zusätzliche Felder `recording` und `state` stellen die Kompatibilität mit der bestehenden Ergebnisgruppierung her.

Die vorhandene AE-Stufe übernimmt bei einer späteren echten Ausführung Modelltraining, Early Stopping, Float32-TFLite-Konvertierung und numerischen Vergleich. Der IF verwendet die vorhandenen Parameter: 200 Bäume, `max_samples=auto`, `contamination=auto`, `max_features=1.0`, kein Bootstrap, ein Worker, Seed 42. RMS und IF erhalten je eine lineare P99-Schwelle aus derselben separaten Normalvalidierung.

Die AE-Schwelle bleibt die bereits in der Keras-Stufe bestimmte Normalvalidierungs-P99. Sie wird beim Wechsel zur ausgewählten TFLite-Laufzeit nicht nachgezogen. Der Adapter prüft zusätzlich die Unterschiede der individuellen Rekonstruktionsfehler, die Entscheidungen an der eingefrorenen Schwelle und die P99-Abweichung gegen die vorhandene Konvertierungstoleranz. Bei einem Widerspruch wird kein fertiges Modellpaket freigegeben.

Die Normalvalidierung dient weiterhin sowohl Early Stopping als auch Schwellenkalibrierung. Es gibt keinen dritten Kalibrierungssplit und keinen unabhängigen Test. Die bekannte Normalvariation und die geringe Zahl von Starts bleiben Einschränkungen des technischen Piloten.

## Eingefrorenes Paket und Wiederholung

Das neue Paket heißt ausdrücklich `pilot_bundle.json`, nicht `bundle.json`. Dadurch kann die alte Vergleichs-CLI es nicht versehentlich ohne AC-Vorverarbeitung laden. Die eigene Ladefunktion verlangt die vollständige v4-Vorverarbeitung, Fensterform, Sensor- und Aufbauzuordnung sowie eine konsistente Datasetreferenz. Sie prüft Paketfingerabdruck, vollständiges Artefaktinventar, Modell-/Scaler-/Schwellenhashes und die Übereinstimmung des ausgeführten Vorverarbeitungs-/Bewertungscodes mit dem archivierten Stand.

Beim Wiederholen bleiben Modelle, Scaler, Schwellen und Verarbeitung unverändert. Der `replay`-Befehl akzeptiert ausschließlich den zugehörigen bereits bekannten Entwicklungsdatensatz und bezeichnet die Ausgabe als Entwicklungsvalidierung. Er ist kein Ersatz für einen späteren unabhängigen Testleser. Der gemeinsame Bewertungskern kann dafür wiederverwendet werden; der konkrete Import neuer Testaufnahmen mit eigener Herkunfts- und Splitprüfung bleibt Teil der späteren Testphase.

Die Regel für den zweiten normalen PWM-Punkt ist im Paket verankert: keine Modell-, Scaler-, Schwellen- oder Vorverarbeitungsänderung. Ein zweiter PWM-Punkt wurde hier weder ausgewählt noch gefahren. Es ist kein erkennungsabhängiger Lüftersteuerpfad enthalten.

Bestehende Ausgaben werden nicht überschrieben. Bei einem Fehler im zukünftigen Trainingsablauf werden Fehlerart und Ursache dokumentiert; es gibt keinen automatischen Neustart. Bereits geschriebene Modellartefakte bleiben zur Fehleranalyse erhalten. Falls ein Abschlussfehler erst nach dem Schreiben von Paketmarkern auftritt, werden diese als `uncommitted_*` erhalten und sind nicht mehr als fertiges Paket ladbar.

## Tatsächlich nachgewiesen

- Der abschließende Audit hat alle **582** Fenster aus originalen Float64-CSV-Zeilen über den gemeinsamen Rohdateneinstieg exakt reproduziert: **388 Training und 194 Validierung**.
- **131 Tests bestanden**: 46 bestehende Tests des neuen Pilotimporters, 77 Tests der Vergleichsanbindung und 8 Tests der Trainingsübergabe. Laufzeit der gemeinsamen Testausführung: 10,62 s.
- Tests prüfen unter anderem identische Methodeneingaben, numerische Reihenfolge der AC-Bildung, ungültige Scores, Quellen-/Code-/Artefaktänderungen, Metadatenübergabe, ausschließlich trainingsbezogenes Fit-Routing, eingefrorene Schwellen, Überschreibschutz und frühe beziehungsweise späte Fehlerfälle.
- Der simulierte Gesamtablauf Training → Paketbildung → Wiederholung läuft auf künstlichen Aufnahmen mit vollständig ersetzten Trainingsabhängigkeiten. Dieser Beleg betrifft die Softwarelogik; er belegt keine echte TensorFlow-Optimierung, TFLite-Konvertierung, neue Erkennungskennzahl oder Laufzeit auf einem neu trainierten Modell.

Belege: [abschließender Audit](final_audit/adapter_audit.json), [JUnit-Testprotokoll](test_results.xml), [Erhaltungsprüfung](verification.json), [Vergleichstests](../../tests/test_pilot_method_comparison.py), [Tests der Trainingsübergabe](../../tests/test_pilot_training_bridge.py). Der erste Audit unter `audit/` bleibt als Zwischenstand erhalten; `final_audit/` enthält den geprüften finalen Implementierungsstand.

## Nächster konkreter Schritt

Der nächste fachliche Schritt ist ein ausdrücklich freigegebener **erster technischer Trainingspilot** mit den vorhandenen Normaldaten. Dafür sind keine neuen Messungen oder manuellen Änderungen am Aufbau erforderlich. Der neue `train`-Einstieg ist implementiert; er wurde in diesem Auftrag nicht auf die Messdaten angewendet, weil die Nutzervorgabe „noch keine Modelle trainieren“ fortbesteht.

Eine sichere erneute Prüfung ohne Training wäre beispielsweise:

```bash
.venv/bin/python src/pilot_method_comparison.py audit --dataset results/upright_v4_pilot_preparation_20260911_123511/dataset --output results/upright_v4_adapter_audit_NEUE_KENNUNG
```

Das Ausgabeziel muss neu sein. Die konkreten späteren Trainings- und Wiederholungseinstiege sind über `train --help` und `replay --help` dokumentiert. Für einen echten Trainingslauf ist `train` ausdrücklich als eigener Befehl erforderlich; der Audit startet ihn nicht.

Für späteren Livebetrieb ist die Übergabe ursprünglicher Float64-XYZ an den neuen AC-Einstieg erforderlich. Die vorhandene Livepuffer-/GUI-Strecke verwendet bereits Float32-Rohfenster und ist noch nicht für dieses neue Paket freigegeben. Es wurde hier kein Hardware-Livestart implementiert oder ausgeführt. Das ist von der abgeschlossenen Offline-Trainings-/Vergleichsanbindung zu trennen.

Weiterhin offen sind die echte Ausführung des neuen Trainings, die Modell-/TFLite-Konsistenz mit diesen Daten, unabhängige Normal-/veränderte Tests, ein zweiter PWM-Punkt mit eingefrorenem Paket und spätere Laufzeit-/Liveprüfungen. Die 180-s-Einlaufzeit bleibt vorläufig; die 200-/207-Hz-Abweichung und eine tatsächliche Drehzahlmessung werden durch die Softwareanbindung nicht geklärt. Es wird keine erfolgreiche Anomalieerkennung behauptet.
