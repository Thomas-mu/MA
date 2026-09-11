# Vorbereitung des Entwicklungsdatensatzes für Aufbau v4

Stand: 11.09.2026. Auftrag: Messparameter für einen ersten Modellversuch begründen und vorhandene Normalaufnahmen getrennt nach vollständigen Läufen aufbereiten. Es wurden keine neuen Messungen, PWM-Schreibbefehle, Trainingsläufe, Scaler-Anpassungen oder Schwellenkalibrierungen ausgeführt. Die Worddatei, alte Modelle, Originaldaten und historische Berichte bleiben unverändert.

## Ergebnis und Einordnung

Ein neues, geprüftes Datenpaket enthält **388 Trainingsfenster aus zwei vollständigen Aufnahmeidentitäten und 194 Validierungsfenster aus einer dritten Aufnahmeidentität**. Die einzelnen Quellen behalten ihre ursprünglichen Zustandsnamen und `purpose=pilot`. Original-CSV, Aufnahmejournal, Freigabe, Sitzungs- und Steuerjournal sind unverändert kopiert und über SHA256 auf ihre Herkunft zurückführbar. Fensterdateien enthalten Aufnahme-ID, Originalindex, Hostzeit und Zeit seit dem PWM-Stellbefehl.

Dies ist ein **vorbereiteter, unskalierter Entwicklungsdatensatz**, kein trainiertes Kalibrierungsprofil. Alle drei Läufe waren bereits Gegenstand der Pilotanalyse. Die Validierung ist deshalb Entwicklungsvalidierung; ein unabhängiger Abschlusstest fehlt. Die Fensterzahl ist keine Zahl unabhängiger Versuche.

## Auswahl und Trennung

Normalzustand: Aufbau `fan_upright_position_v4_20260911_103726`, aufrechter Lüfter in der nach der Positionsänderung bestätigten Stellung, keine Platte, feste bestehende Sensorbefestigung mit zwei Schrauben, 75 % PWM bei 25 kHz. Diese Angaben stammen aus den erhaltenen Freigaben und Aufnahmejournalen; in dieser Softwarearbeit wurde der Aufbau nicht erneut physisch geprüft.

Die Zuordnung folgt der zeitlichen Reihenfolge: erste zwei Normalaufnahmen Training, letzte Normalaufnahme Validierung. Sie wurde im [Pilotplan](pilot_plan.json) vor dem Export festgehalten. Es findet keine zufällige Aufteilung benachbarter Fenster statt. Die vollständige Aufnahmeidentität wird genau einer Gruppe zugeordnet; innerhalb jeder Datei wird nur das einheitliche Intervall `[180, 300)` Sekunden verarbeitet. Stillstand, Plattenzustand und ältere Aufbauversionen sind ausgeschlossen. Das Original einschließlich Anlauf bleibt vollständig erhalten.

| Originalzustand | Gruppe | XYZ im gesamten Lauf | XYZ in 180–300 s | Vollständige Fenster | Rest-XYZ ohne Modellfenster |
|---|---|---:|---:|---:|---:|
| `normal_before` | Training | 62.148 | 24.865 | 194 | 33 |
| `normal_after` | Training | 62.156 | 24.863 | 194 | 31 |
| `normal_followup` | Validierung | 62.151 | 24.861 | 194 | 29 |

Jedes Fenster umfasst 128 aufeinanderfolgende XYZ-Messpunkte, also 384 einzelne Achsenwerte. Ein 300-s-Lauf enthält ungefähr 62.150 XYZ-Messpunkte, nicht 62.150 einzelne Achsenwerte. Je Lauf werden 24.832 XYZ in vollständigen Modellfenstern genutzt. Reststücke von 33, 31 beziehungsweise 29 XYZ werden ausschließlich beim Ableiten der Modellfenster ausgelassen; es werden keine Originaldaten gelöscht. Fenster überschreiten weder Datei- noch Abschnittsgrenzen.

Die bekannte späte Normalvariation bleibt bestehen: Die früheren 5-s-Diagnostikmittelwerte liegen bei rund 27,737 mg, 33,148 mg und 39,128 mg. Der letzte, stärkere Normallauf bleibt Validierung und wird nicht nachträglich dem Training zugeordnet, um ein günstigeres Ergebnis zu erhalten. Alle drei Aufnahmen stammen aus derselben untersuchten Sitzung mit unterschiedlichen Auszeiten; sie decken keine mehrtägige Normalvariation ab.

## Begründete Pilotparameter

| Parameter | Festlegung | Begründung und Grenze |
|---|---|---|
| Sensor | ADXL345, I²C-Bus 1, konfigurierte Busfrequenz 100 kHz, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, 0,0039 g/LSB | Identisch zu den vorhandenen v4-Aufnahmen; keine neue Sensoreinstellung. |
| Registerrücklesung | BW_RATE `0x0b`, DATA_FORMAT `0x08`, INT_ENABLE `0x00`, FIFO_CTL `0x90`, POWER_CTL `0x08` | In allen ursprünglichen Aufnahmejournalen geprüft; nicht als neue Live-Rücklesung ausgegeben. |
| Zeitnullpunkt | Aufrufbeginn des PWM-Stellbefehls in Host-Monotonzeit | Nicht Befehlsabschluss, erster XYZ-Punkt oder Dateiname. Auswahl erfolgt mit ganzzahligen Nanosekunden vor einer Umrechnung in Sekunden. |
| Auswahl | 180 s einschließlich bis 300 s ausschließlich | Gemeinsamer bereits untersuchter später Abschnitt. 180 s bleiben ein Prüfkandidat; Resttrends werden nicht entfernt. Der Pilot trifft keine Aussage zur Erkennung während der ersten 180 s. |
| Fenster und Schritt | 128 XYZ, Schritt 128, keine Überlappung | Entspricht der bestehenden Autoencoder-Eingabeform 128 × 3. Nominell 128/200 = 0,64 s, beim beobachteten Durchsatz etwa 0,618 s. Der erste bis letzte Zeitstempel umfasst dagegen nur 127 Abstände. Kein Nachweis einer optimalen Fenstergröße. |
| Vorverarbeitung | Je 128er-Fenster den jeweiligen X-, Y- und Z-Mittelwert entfernen | Unterdrückt statische Achsenoffsets für einen vibrationsbezogenen Pilot. Amplituden werden erhalten. Keine Normierung jedes Fensters auf seine eigene Streuung oder seinen RMS. |
| Rechengenauigkeit | Zentrierung in Float64; Roh- und AC-Fensterexport in Float32 | Kompatible Eingabeform für spätere Methoden; unveränderte Original-CSV zusätzlich erhalten. |
| Filter / Abtastkorrektur | Kein neuer Filter, keine Interpolation oder Umabtastung | Der bisherige Zeitbasisbefund wird nicht durch ein künstliches 200-Hz-Raster verdeckt. Nutzbares Frequenzband und mögliche Aliasanteile bleiben offene Grenzen. |
| Spätere Skalierung | StandardScaler ausschließlich an AC-Trainingsfenstern, achsenweise über alle Trainingspunkte | Validierung und Test verändern diese Skalierung nicht. Noch nicht angepasst oder gespeichert. |
| Spätere Schwellen | Je Methode lineares empirisches 99. Perzentil der separaten Normalvalidierung | Vorhandene P99-Regel als Pilotkonvention; keine unabhängige Fehlalarmgarantie. Noch keine Schwelle berechnet. |

128 XYZ enthalten bei ungefähr 207 XYZ/s etwa 24 Perioden der gemeinsamen Komponente um geschätzte 39,45 Hz. Das unterstützt die Verwendung als kurzer technischer Pilot, ersetzt aber keinen Vergleich verschiedener Fensterlängen oder einen Nachweis nutzbarer Bandbreite. Die nominelle Frequenzachse würde dieselbe FFT-Komponente anders beschriften; tatsächliche Drehzahl wurde nicht gemessen.

## Drei ausdrücklich unterschiedliche Größen

Für die bisherigen 5-s-Grafiken gilt der Vektor-AC-RMS in g:

`R_AC = sqrt(sum_j(mean_i((a_ij - mean_i(a_ij))²)))`.

Die neuen Modellfenster entfernen ebenfalls je Achse ihren eigenen Mittelwert, sind jedoch **128 XYZ lang, nicht 5 Sekunden**. Ihre Kennung ist `xyz_window128_axis_mean_removed_unscaled_v1`. Die später gemeinsam standardisierten Fenster sollen allen drei Methoden als identische Datenbasis dienen. Für den Methodenvergleich bleibt der RMS-Score `sqrt(mean(z²))` über alle standardisierten Zeit- und Achsenwerte vorgesehen. Er ist dimensionslos. Auf unskalierten AC-Daten wäre diese Matrix-RMS-Größe um den Faktor √3 kleiner als der Vektor-AC-RMS. Nach achsenweiser Skalierung gibt es keine einzige Umrechnung in mg. Die bisherigen Grafikwerte sind deshalb keine Modellschwellen.

Die bisherige StandardScaler-Pipeline entfernt nur einen globalen Trainingsmittelwert. Sie führt die neue Mittelwertentfernung je Fenster nicht aus. Deshalb wird kein scheinbar kompatibles altes Profil mit umgeschriebenen Zustandsnamen erzeugt.

## Erneute Datenqualitäts- und Zeitbasisprüfung

| Aufnahme | XYZ/s ganzer Lauf | XYZ/s Auswahl | Max. Hostabstand ms gesamt / Auswahl | Abstände >10 ms gesamt / Auswahl | Max. FIFO gesamt | Erster XYZ nach Stellbefehl ms |
|---|---:|---:|---:|---:|---:|---:|
| `normal_before` | 207.164957 | 207.201497 | 13.467 / 6.897 | 3 / 0 | 2 | 72.938 |
| `normal_after` | 207.188733 | 207.190601 | 9.483 / 9.483 | 0 / 0 | 2 | 78.118 |
| `normal_followup` | 207.171012 | 207.177441 | 8.217 / 6.330 | 0 / 0 | 1 | 74.583 |

Alle drei vollständigen Quellen haben streng steigende Hostzeitstempel, fortlaufende Softwareindizes, endliche XYZ-Werte und keine gesetzten Lücken-, Überlauf- oder Sättigungsflags. CSV-Zählungen und Journalzähler stimmen überein. Relative CSV-Zeit und Host-Monotonzeit wurden gegeneinander geprüft; die separate nominale Sensorzeit entspricht weiterhin `sample_index / 200`.

Die drei Hostabstände über 10 ms im ersten vollständigen Normallauf liegen außerhalb der Auswahl; sie werden weder verschwiegen noch allein als nachgewiesene Sensorverluste gezählt. Der Import überprüft die ganze Aufnahme vor dem Ausschneiden und würde gesetzte Qualitätsflags auch außerhalb von 180–300 s zurückweisen. Die bestehende 160-ms-Grenze entspricht nominell 32 FIFO-Plätzen bei 200 Hz und ist eine grobe Verlustwarnung, kein Nachweis einer idealen Zeitbasis. Fehlende Flags belegen keine exakt verlustfreie Sensorkonversion; die exakte Zahl verlorener Sensorwerte bleibt unbekannt.

**Gesichert:** Aus den Original-Hostzeitstempeln und XYZ-Zählungen ergibt sich über die vollständigen Läufe etwa 207,16–207,19 XYZ/s, obwohl die Register nominell 200 Hz konfigurieren. Die Auswahl verwendet die Hostzeit und keine aus 200 Hz abgeleitete Punktzahl. Es wird weder auf 200 Hz umgerechnet noch 207 Hz als neu eingestellte Sensorfrequenz bezeichnet.

**Offen:** Die genaue Ursache der Abweichung ist mit diesen Daten nicht isoliert. Sensorinterne Taktabweichung, Zeitreferenz und Leseablauf sind dadurch nicht unabhängig kalibriert. Host-Leseabstände sind keine direkten Sensor-Konversionsabstände. Der neue Import löst diese Messkettenfrage nicht; Details bleiben im getrennten [Spektralbericht](../upright_v4_spectral_review_20260911_114502/spectral_report.md) dokumentiert.

## Implementierung und tatsächlich ausgeführte Prüfungen

Neu angelegt wurden [Offline-Importer](../../src/prepare_pilot_dataset.py) und [Tests](../../tests/test_prepare_pilot_dataset.py). Bestehende Trainings-, Vergleichs- und Hardwaremodule wurden nicht verändert. Der Import enthält keine Hardware- oder Trainingsaufrufe. Ein vorhandenes Ausgabeziel wird abgewiesen. Original-CSV und Journale werden weder umbenannt noch intern umetikettiert; lediglich unveränderte Kopien liegen im neuen Paket unter `sources/`.

Die Überprüfung rekonstruiert **alle** Roh- und AC-Fenster erneut aus den ursprünglichen CSV-Zeilen, vergleicht Werte und Quellindizes exakt und kontrolliert Datei-/Journalhashes, vollständiges Exportinventar, Float32-/Int8-Datentypen und Manifestzählungen. Die 46 Offline-Tests bestehen; sie enthalten auch synthetische Fehlersituationen und Zeitgrenzen oberhalb der exakten Float64-Ganzzahldarstellung. Diese synthetischen Testdaten sind keine Messungen und fließen nicht in das Pilotpaket ein.

Der größte verbleibende Betrag eines AC-Fensterachsenmittelwerts nach Float32-Export beträgt 3.583e-10 g. Die Zentrierung erfolgt vor der Float32-Konvertierung; dieser kleine numerische Rest ist kein gemessenes Vibrationsmerkmal.

Belege: [Testprotokoll](test_results.xml), [vollständige Datasetprüfung](dataset_verification.json), [Manifest](dataset/manifest.json), [Plan](pilot_plan.json), [abschließende Erhaltungsprüfung](verification.json). Die archivierte `dataset/preparation_source.py` ist der Stand beim Erzeugen des Pakets; `verified_preparation_source.py` enthält zusätzlich danach ergänzte Verifikationsprüfungen für Datentypen und gemeinsame Boot-ID. Die Datenberechnung wurde dabei nicht geändert und nochmals vollständig gegen die Quellen geprüft.

## Benutzung und konkreter nächster Schritt

Die folgende Prüfung ist ausschließlich lesend und startet keine Aufnahme oder Modellbildung:

```bash
.venv/bin/python src/prepare_pilot_dataset.py --verify results/upright_v4_pilot_preparation_20260911_123511/dataset
```

`load_prepared_pilot(dataset_path)` liefert nach vollständiger Prüfung die gemeinsamen unskalierten AC-Eingaben in den Formen `(388,128,3)` und `(194,128,3)`. `train_raw_g.npy` und `validation_raw_g.npy` dienen der Nachvollziehbarkeit; sie sind nicht die gewählte AC-Modelleingabe. Die Werte in `*_labels.npy` sind ausschließlich normale Labels 0. `*_windows.csv` enthält die vollständige Fensterprovenienz.

**Die angefragte Parameter- und Datenvorbereitung ist abgeschlossen.** Als nächster Implementierungsschritt vor einer Trainingsausführung ist die bestehende Trainings-/Vergleichsroutine an diesen geprüften Eingang anzubinden. Sie muss die vollständigen ursprünglichen 300-s-Dateien nicht erneut ungefiltert einlesen, sondern dieselben ausgewählten AC-Fenster für RMS, Isolation Forest und Autoencoder verwenden. Dazu gehören ein nur am Training angepasster Scaler, dieselbe Vorverarbeitung bei Replay und später im Livepfad sowie eine neue Profilkennung. Der vorhandene Legacy-Aufruf `calibrate_and_train.py --train-only` ist für dieses neue Paket noch kein unterstützter direkter Einstieg.

Ein nachfolgender ausdrücklich freigegebener technischer Trainingspilot kann prüfen, ob Modellbildung, TFLite-Konvertierung und gemeinsame Bewertung korrekt laufen und wie sich der zurückgehaltene Normallauf verhält. Er ersetzt keinen neuen unabhängigen Test und belegt keine Anomalieerkennung. Vor Tests am zweiten normalen PWM-Betriebspunkt bleiben Modelle, Skalierung und Schwellen eingefroren. Weiterhin gilt die Nutzervorgabe, noch keine Modelle zu trainieren.

Für die Vorbereitung war keine Nutzerhandlung am Aufbau nötig. Die softwareseitige PWM-Vorgabe wurde nur gelesen: 0 % bei 25 kHz, aktiviert, normale Polarität. Ein vollständiger mechanischer Stillstand nach dem letzten Hardwarelauf wird daraus nicht behauptet. Für weitere Softwarearbeit kann der Aufbau unverändert bleiben; neue Messungen erfordern eine eigene Versuchsfreigabe.
