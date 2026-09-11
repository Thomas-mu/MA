# Normal → Luftstrom verändert → Normal: neue Sitzung

Status: vorbereitet; noch keine Aufnahme gestartet. Maßgeblich ist die aktuelle Nutzeranweisung: keine Fragen zum sichtbaren Lauf, keine Antwortfristen, keine automatischen Wiederholungsstarts. Nach jedem Lauf wird auf 0 % gestellt, rückgelesen und bis zur nächsten ausdrücklichen Freigabe pausiert. Die bereits abgeschlossenen drei früheren Normalstarts werden nicht wiederholt oder als Daten dieser Folge ausgegeben.

## Freigaben und Ablauf

1. `normal_before`: Erst nach „Normalaufbau bereit, Versorgung angeschlossen, erster Lauf freigegeben.“ starten.
2. `airflow_modified`: Erst nach abgeschlossenem ersten Lauf, Nullvorgabe und „Umbau fertig, nächster Lauf freigegeben.“ starten.
3. `normal_after`: Erst nach abgeschlossenem zweiten Lauf, Nullvorgabe und einer neuen Nachricht „Umbau fertig, nächster Lauf freigegeben.“ starten.

Jede Freigabe wird nach tatsächlichem Eingang in einer eigenen `*_release.json` mit Originaltext, Phase, UTC, monotoner Annahmezeit und Boot-ID dokumentiert. Jetzt wird keine Freigabedatei angelegt. Ein bereits existierendes Sitzungsjournal verhindert einen zweiten Start derselben Phase, auch nach einem Fehler. Es gibt keinen Hintergrundprozess, der auf Nachrichten wartet oder selbstständig die Folge fortsetzt.

Jeweils 60 s zusätzliche Auszeit ab Annahme der Freigabe, anschließend ein Start auf 75 % bei 25 kHz und 300 s Erfassung möglichst ab Stellbefehl. Der tatsächliche erste XYZ-Zeitpunkt wird relativ zum Befehlsaufruf und -abschluss angegeben. Die Gesamt-Auszeit zwischen den Läufen wird separat gemessen; für den ersten Lauf ist eine vorherige durchgehend verifizierte Auszeit unbekannt. 0 % bedeutet ausschließlich Stellvorgabe, keine automatisch gemessene mechanische Ruhe.

Der Nutzer übernimmt das Trennen der externen 12-V-Versorgung, das Warten auf vollständigen Stillstand und das Einsetzen bzw. Entfernen der Platte. Die phasenbezogene Freigabe dokumentiert die im aktuellen Auftrag vereinbarte Bereitschaft; es wird keine zusätzliche Beobachtung während des Laufs erfunden. Sensor und Lüfter werden nicht umgesetzt.

## Geometrie und Messkette

Der [vorbereitete Versuchsplan](../mount_v2_review_20260911_085505/versuchsplan.md) gilt für die Sollgeometrie: Platte 60 × 120 mm, parallel zum Auslass, 100 mm Abstand von der äußeren Auslassebene, Projektion über der rechten Rahmenhälfte beim Blick auf den Auslass. In N ist die Platte außerhalb des Auslasses; planmäßig liegt ihre nächste Kante mindestens 120 mm seitlich außerhalb der projizierten Auslassfläche. Halterung bleibt separat und kippsicher, ohne Berührung von Sensor oder Lüfter.

Die tatsächlichen Maße, das Material und die Halterungsdetails sind noch nicht berichtet. Sie stehen in `geometry.json` deshalb auf `null`, getrennt von den Sollwerten. Ein Freigabesatz allein wird nicht als Vermessung ausgegeben. Geometrieangaben aus späteren Nutzernachrichten werden mit ihrer Herkunft und dem zugehörigen Zustand separat protokolliert. Unbekannte Details verhindern keine normale Aufnahme ohne eingesetzte Platte; Abweichungen der Vorrichtung müssen vor einem veränderten Zustand beurteilt werden, wenn sie bekannt werden.

Unverändert: Aufbauversion `adxl345_mount_v2_provisional_20260911_072748`, ADXL345 mit zwei Schrauben am äußeren stationären Rahmen, Platine schräg; I²C-Bus 1/Adresse 0x53, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, Softwarefaktor 0,0039 g/LSB. Sensorerkennung und Registerrücklesen erfolgen beim freigegebenen Lauf mit der vorhandenen Software. Heute wurde noch kein zusätzlicher Sensorpilot ausgeführt.

## Daten und spätere Auswertung

Eigene CSV/JSON-Dateien mit `state` und `anomaly_type` exakt `normal_before`, `airflow_modified` bzw. `normal_after`. Numerisch 0 für die beiden vorgesehenen normalen Zustände und 1 für die kontrollierte Luftstromveränderung. Diese Labels bezeichnen die Versuchskonfiguration, keinen nachgewiesenen Defekt oder erfolgreichen Modellalarm. Alle drei Aufnahmen gehören zum Entwicklungspiloten, nicht zum unabhängigen Abschlusstest.

Die Auswertung umfasst Rohdatenhashes, Zeitmonotonie, nominelle ODR und beobachtete XYZ/s getrennt, Host-Leseabstände und Lesedauern, FIFO- und Gap-/Overrun-/Sättigungsflags. 60 aufeinanderfolgende 5-s-Abschnitte werden auf den Stellbefehl bezogen, jeweils mit eigener Achsenmittelwertentfernung und Vektor-AC-RMS. Der erste Abschnitt enthält wegen des gemessenen Startversatzes möglicherweise etwas weniger als 5 s Daten; es wird nichts aufgefüllt. Primär werden 24 Fenster von 180–300 s einschließlich zeitlicher Steigungen und Mittelwertunterschieden verglichen. 180 s bleibt vorläufig.

Nach allen drei Zuständen folgen ein separater Messbericht und Grafiken: vollständiger Verlauf, später Abschnitt, Rückkehr von `normal_after` zum beobachteten Bereich von `normal_before`, sowie Abstände von `airflow_modified` zu beiden Normalreferenzen. Eine einzige Folge beweist weder allgemeine Reproduzierbarkeit noch Anomalieerkennung. Worddatei, vorhandene Modelle, Quellcode und historische Dateien bleiben unverändert; `baseline.json` sichert 888 bereits vorhandene Dateien mit SHA256.
