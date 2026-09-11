# Versuchsplan: kontrollierte äußere Luftstromveränderung bei 75 % PWM

Stand: 11.09.2026. **Planungsstatus: nicht durchgeführt.** Keine Anomalie wurde hergestellt und kein Modell trainiert. Ausgangspunkt ist die [Offline-Auswertung](auswertungsbericht.md) der drei Starts mit der neuen Montage. Alle Zeit-, Geometrie- und Wiederholungsangaben in diesem Plan sind Vorgaben, keine gemessenen Ergebnisse.

## 1. Fragestellung und Umfang

Geprüft werden soll, ob eine fest definierte, teilweise Abschirmung auf der Auslassseite bei konstant 75 % PWM eine reversible Änderung der gemessenen Vibration erzeugt, die gegenüber normaler Variation zwischen Starts bestehen bleibt. Die Abschirmung ist ein Laborstellvertreter für eine veränderte Luftströmungsbedingung. Sie ist weder ein nachgebildeter Lagerschaden noch ein bereits validiertes Fehlerbild. Eine Zunahme des RMS wird nicht vorausgesetzt; auch ein Abfall, eine spektrale Änderung oder kein erkennbarer Effekt sind mögliche Ergebnisse.

Die Sensorbefestigung mit zwei Schrauben am äußeren Lüfterrahmen bleibt unverändert. Die Platine wird weder gelöst noch neu ausgerichtet. Es wird nicht in den laufenden Rotor eingegriffen und nichts daran angebracht. Die Eignung des Protokolls für diesen Prüfstand hängt noch von der verfügbaren freien Fläche und einer unabhängigen festen Halterung ab.

## 2. Normalzustand und kontrollierte Veränderung

| Merkmal | N: Normalbetrieb | A: kontrollierte Veränderung |
|---|---|---|
| Lüfter/Sensor | Bestehende Aufbauversion `adxl345_mount_v2_provisional_20260911_072748`; feste Position und Unterlage | Identisch |
| Versorgung/PWM | Externe 12 V angeschlossen, Hardware-PWM 75 % bei 25 kHz | Identisch; keine Drehzahlregelung oder Rückkopplung durch Erkennung |
| Sensor | ADXL345, I²C 100 kHz, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, unveränderte Skalierung | Identisch |
| Unabhängige Halterung | Fest positioniert; Halter berührt weder Lüfter noch Sensor und liegt außerhalb der projizierten Auslassfläche | Identisch |
| Abschirmplatte | Starre, nichtleitende Platte 60 × 120 mm in markierter Parkposition; nächste Kante mindestens 120 mm seitlich außerhalb der projizierten Auslassfläche | Dieselbe Platte parallel zur Auslassfläche, 100 mm Abstand von der äußeren Auslassebene; Projektion bedeckt die festgelegte rechte Hälfte der 120 × 120-mm-Rahmensilhouette |
| Labels | `label=0`, `state=normal75_free_outlet`, `condition_id=N` | `label=1`, `state=external_outlet_screen_v1`, `condition_id=A` |

„Rechts“ ist beim Blick auf den Auslass in Richtung Lüfter definiert und vorab in einer Skizze zu markieren. 60 × 120 mm entspricht der halben rechteckigen Rahmensilhouette, **nicht** einem nachgewiesenen halbierten Luftdurchsatz oder der Hälfte der freien Rotorfläche. Die Maße sind ein vorsichtiger Entwurf für eine außerhalb des Lüfters liegende Veränderung; ihre Wirksamkeit ist erst zu prüfen. Die 25-kHz-Vorgabe entspricht der Herstellerangabe zur PWM-Frequenz. [ARCTIC, P12 Pro PST Support](https://support.arctic.de/de/p12-pro-pst).

Die Platte muss an einer eigenen kippsicheren Halterung durch zwei feste Klemmstellen und einen mechanischen Anschlag gehalten werden. Sie darf auch unter Luftlast nicht in Richtung Rotor gelangen oder mit dem Prüfstand in Kontakt kommen. Lose Folie, lose Pappe, an den Rotor geklebte Gewichte, gelockerte Schrauben und handgehaltene Gegenstände gehören nicht zu diesem Versuch. Wenn dieser Abstand und eine unabhängige Halterung räumlich nicht möglich sind, wird vor einem Start eine andere äußere Geometrie geplant; es wird nicht improvisiert.

Die vorhandene Sensor-Aufbauversion bleibt bestehen. Die zusätzliche, separat positionierte Vorrichtung erhält eine eigene `fixture_version=outlet_screen_v1` einschließlich Material, tatsächlicher Maße, Klemmung, Abstand, Parkposition sowie dokumentierter Lüfterunterlage. Die drei bereits ausgewerteten Normalstarts bleiben Entwicklungsdaten ohne diese Vorrichtung. Sie ersetzen deshalb nicht die unmittelbaren N-Referenzen mit der neuen, geparkten Halterung.

## 3. Kleinster Pilot und Wiederholungen

Zunächst **N1 → A1 → N2**, jeweils ein eigener Lüfterstart und eine vollständige 300-s-Aufnahme. Dies ist die kleinste Folge, die einen zeitnahen Ausgangszustand, die Veränderung und die Rückkehr prüft. Sie beantwortet noch keine Reproduzierbarkeitsfrage abschließend.

Wenn die Vorrichtung sicher unverändert bleibt, die Datenqualität ausreicht und die Rückkehr zu N interpretierbar ist, folgen nach gemeinsamer Auswertung zwei weitere A-Anwendungen mit N-Rückkehr:

| Reihenfolge | Zustand | Wiederholung/Zweck | Aufnahme | Vorgesehene Nutzung |
|---|---|---|---|---|
| P01 | N1 | Ausgangsreferenz mit geparkter Vorrichtung | 300 s ab Stellbefehl | Entwicklungspilot |
| P02 | A1 | Erste Anwendung | 300 s ab Stellbefehl | Entwicklungspilot |
| P03 | N2 | Erste Rückkehr | 300 s ab Stellbefehl | Entwicklungspilot |
| P04 | A2 | Zweite unabhängige Anwendung, erst nach Bewertung P01–P03 | 300 s ab Stellbefehl | Entwicklungspilot |
| P05 | N3 | Zweite Rückkehr | 300 s ab Stellbefehl | Entwicklungspilot |
| P06 | A3 | Dritte unabhängige Anwendung | 300 s ab Stellbefehl | Entwicklungspilot |
| P07 | N4 | Dritte Rückkehr | 300 s ab Stellbefehl | Entwicklungspilot |

Damit entstehen im vollständigen Pilot drei A- und vier N-Aufnahmen. Die Normalreferenzen zwischen A-Läufen werden bei benachbarten Vergleichen geteilt; die drei Kontraste sind daher nicht statistisch unabhängig. Es werden keine automatischen Wiederholungsstarts eingerichtet. Ein Fehler oder uneindeutiger Befund bleibt als solcher erhalten und führt nicht zum stillen Ersetzen einer Aufnahme.

## 4. Ablauf jedes einzelnen Starts

1. Software prüft Steuerprozesse, exklusiven Sensorzugriff, Pin-Funktion und Rücklesung der Stellvorgabe. Lüfter zunächst **0 % PWM bei 25 kHz**. Vor jedem Start folgt eine ausdrückliche Sichtbestätigung des vollständigen mechanischen Stillstands.
2. Nur bei einem erforderlichen Wechsel N/A: externe 12-V-Versorgung bei bestätigtem Stillstand trennen, ausschließlich die Platte an ihrer eigenen Halterung umsetzen und wieder festklemmen. Sensor, Lüfter, Kabel und Unterlage bleiben unberührt. Freien Rotor, Abstand, feste Halterung und Kabelführung prüfen; dann 12 V wieder verbinden, während die Softwarevorgabe 0 % bleibt. Diese Handlungen werden auch als Zeitpunkte erfasst.
3. Nach abgeschlossener Vorbereitung und bestätigtem Stillstand beginnt eine **zusätzliche Auszeit von 60 s** ab softwareseitiger Annahme der Bestätigung. Auch die gesamte Auszeit seit der letzten Nullvorgabe wird dokumentiert. Unterschiedliche Handhabungs- oder Antwortzeiten werden nicht als gleiche gesamte Kühlzeit ausgegeben.
4. Software kündigt genau einen Start auf **75 % PWM, 25 kHz, 300 s Aufnahme** an. Erfassung und Stellbefehl erfolgen ohne absichtliche Einlaufverzögerung. Aufruf, Befehlsabschluss, Aufnahmeuhr und erste XYZ-Lesung erhalten UTC- und monotone Zeitstempel. Ihr tatsächlicher Versatz wird ausgewiesen. Das primäre Fenster wird künftig auf den protokollierten Befehlsaufruf bezogen.
5. Während des Laufs bleibt die gesamte Anordnung unverändert. Der Nutzer beobachtet von außen, ohne sie zu berühren. Eine nachträgliche Laufbeobachtung wird ohne Antwortfrist erfragt. Die Aufnahme benötigt keine rechtzeitige Chatantwort und löst bei deren Fehlen keinen Ersatzstart aus.
6. Nach 300 s wird im Abschlussblock **0 % PWM** gesetzt und rückgelesen; auch bei Softwarefehlern wird dies nach Möglichkeit versucht. Unvollständige Daten und Fehlerstatus bleiben erhalten. Scheitert die Abschaltung, wird der tatsächlich auslesbare Zustand gemeldet und der Nutzer zum Trennen der externen Versorgung aufgefordert. Kein selbstständiger Neustart.
7. Vor Umsetzen der Platte oder dem nächsten Start wird wieder die mechanische Stillstandsbestätigung abgewartet. 0 % PWM allein genügt dafür nicht. Bei einer unerwarteten Lockerung, Berührung oder auffälligem Betrieb wird beendet; Änderungen an der Vorrichtung erfolgen erst stromlos und im Stillstand.

Erkennungsabhängige PWM-Änderungen sind in sämtlichen Vergleichsaufnahmen deaktiviert. Eine Drehzahl wird nur mit bestätigter separater Messmethode eingetragen; GPIO18 bleibt der Steueranschluss. Ein Tachoanschluss wird nicht aus der Steuerleitung abgeleitet.

## 5. Speicherung und Labels

Jede Aufnahme erhält ein eigenes neues Verzeichnis bzw. einen exklusiv angelegten Dateinamen mit UTC-Zeitstempel und Zustandskennung. Mindestangaben:

- `recording_id`, `start_id`, `session_id`, `comparison_block_id`, Montage- und Vorrichtungsversion, vorab vorgesehener Split;
- eingestellte PWM/Frequenz, sämtliche Steuerzeitpunkte und Rücklesungen, Sichtbestätigungen getrennt von Messwerten;
- geplante und tatsächliche Dauer, erste/letzte monotone XYZ-Zeit, nominelle ODR, beobachteter Durchsatz, XYZ-Punktzahl und Registerkonfiguration;
- Gesamt-/Zusatz-Auszeit, angeschlossene Versorgung, tatsächlich beobachtete Auffälligkeiten; Temperatur und RPM nur als Messwerte mit Methode, sonst `null`;
- Roh-XYZ, Sampleindex, Hostzeit, FIFO-Füllstand, Host-Leseabstand, Lesedauer, Gap-/Overrun-/Sättigungsflags, Quellcode- und Rohdatenhashes.

`label` beschreibt die **bestätigte physische Versuchskonfiguration**, keinen Modellalarm und keine Schadensdiagnose. Unbestätigte oder während eines Fehlers unklare Zustände erhalten `label=-1` bzw. einen gesonderten Gültigkeitsstatus. Eine A-Aufnahme behält das A-Label auch bei fehlendem RMS-Unterschied. Sie wird nicht nachträglich zu N umetikettiert.

Zusätzlich wird `phase` getrennt gespeichert: `startup_candidate` für [0,180) s und `comparison_candidate` für [180,300) s. Diese Phasenbezeichnung bestätigt keine abgeschlossene Einlaufphase. Die gesamte Datei bleibt einem einzigen Split zugeordnet. Noch nicht gemessene Dateien, Zeitpunkte und Messwerte werden nicht vorweg eingetragen. [planned_recordings.csv](planned_recordings.csv) enthält ausschließlich gekennzeichnete Planungseinträge.

## 6. Vorab festgelegte Auswertung und Entscheidung

Primär werden [180,300) s anhand von 24 nicht überlappenden 5-s-Fenstern verglichen. Für jedes Fenster werden die drei Achsenmittelwerte neu entfernt und der Vektor-AC-RMS berechnet. Die tatsächlichen Hostzeitstempel begrenzen die Fenster. Die kompletten 300 s bleiben zur Beurteilung von Anlauf und etwaiger später Restdrift erhalten.

Zuerst werden Konfiguration, Dauer, Zeitstempel, beobachtete Rate, Host-Leseabstände, FIFO und Qualitätsflags geprüft. Überlauf, Sättigung, nicht monotone Zeit oder ein Eingriff kennzeichnen eine betroffene Aufnahme als für den primären Vergleich ungeeignet; sie wird nicht gelöscht. Ein einzelner längerer Hostabstand ohne FIFO-Verlusthinweis führt nicht automatisch zum Ausschluss. Für alle Zustände gelten dieselben Regeln, keine Auswahl nach gewünschter Effektgröße.

Berichtet werden pro Start Mittelwert, Median, Standardabweichung, Spannweite und gerichteter Verlauf der Fenster-RMS-Werte. Für A wird jeweils der Unterschied zu beiden umgebenden N-Starts sowie zu deren mittlerem Niveau dargestellt. Die N-Startmittel und ihre Veränderungen werden separat gezeigt. Eine über alle Fenster gepoolte große Stichprobe ersetzt nicht die Zahl unabhängiger Starts.

Die erste Folge N–A–N entscheidet zunächst über Machbarkeit, Signalqualität und erkennbare Rückkehr, nicht über Erkennungsgenauigkeit. Erst die vorgesehenen drei A-Anwendungen erlauben eine erste Prüfung, ob die Zustandsänderung in vergleichbarer Richtung wiederkehrt. Überlappende Fensterbereiche oder unterschiedliche N-Startmittel sind allein weder Erfolg noch Misserfolg. Wenn der Effekt in der Größenordnung der normalen Verschiebungen liegt oder die Rückkehr unklar bleibt, wird genau dieser Befund berichtet; es werden keine Schwellen passend gemacht.

Falls ein nach 180 s verbleibender Trend den Zustandskontrast dominiert, lautet die konkrete Zusatzfrage, ob er nach 300 s weiterbesteht. Dann wäre ein einzelner 600-s-Normalstart die kleinste erste Ergänzung. Ohne diesen Befund sind zusätzliche lange Normalserien nicht erforderlich. Die vorgesehene N–A–N-Folge liefert ohnehin neue, zeitnahe Normalvariabilität.

## 7. Spätere Trennung von Training, Validierung und Test

Die jetzt bereits untersuchten drei Normalläufe und der gesamte geplante Geometriepilot gelten als **Entwicklungsdaten**. Sie haben die Fensterwahl bzw. Versuchsplanung beeinflusst und werden nicht als unberührter Abschlusstest ausgegeben. Alte Montageversionen bleiben getrennt.

Nach Festlegung der Geometrie und Auswertung des Piloten ist folgender konkrete Startumfang für einen späteren Methodenvergleich vorgesehen; dies ist noch keine statistische Fallzahlbegründung:

| Teilmenge | Vollständige neue Aufnahmen | Zweck |
|---|---|---|
| Training | 6 N × 300 s, auf mindestens zwei getrennte Sitzungen verteilt | Normalvariabilität lernen; Skalierung ausschließlich hier anpassen |
| Validierung | 3 weitere N × 300 s in einer separaten Sitzung | Vorab vereinbarte Schwellenregel und Normal-Fehlalarme prüfen |
| Gesperrter Test | 3 neue N + 3 neue A, jeweils 300 s, drei gepaarte Blöcke in späteren Sitzungen | Vergleich aller Methoden nach vollständigem Einfrieren |

Die Testreihenfolge wird vor der Aufnahme festgelegt: Block T1 N–A, T2 A–N, T3 N–A. Jede Teilaufnahme beginnt mit eigenem Start nach Stillstand und derselben Zusatz-Auszeit. Ein kompletter Vergleichsblock und möglichst eine Sitzung gehören immer nur zu einer Teilmenge. Sämtliche Fenster eines `recording_id` bleiben zusammen; überlappende oder direkt benachbarte Fenster werden niemals zufällig über Splits verteilt. Es werden keine Fenster über Datei- oder Startgrenzen gebildet.

RMS, Isolation Forest und TFLite erhalten im späteren gemeinsamen Vergleich dieselben zugelassenen Aufnahmequellen und dieselben festgelegten Zeitfenster. Das diagnostische 5-s-AC-RMS ist dabei nicht stillschweigend identisch mit sämtlichen bisherigen Modell-Eingabegrößen. Die gemeinsame Vorverarbeitung einschließlich Fensterlänge, Zeithandhabung und Skalierung wird vor Training und Test ausdrücklich festgelegt und geprüft.

Skalierung und Modelle werden nur aus Trainingsdaten bestimmt. Eine mögliche gemeinsame Regel ist P99 der jeweiligen normalen Validierungsscores; Regel, Quantilberechnung und Alarmaggregation werden vor dem Test festgelegt. Drei Validierungsstarts liefern nur eine vorläufige Schätzung der Fehlalarmrate, keine garantierten 1 % Fehlalarme in künftigen Aufnahmen. Testdaten dürfen weder Normalisierung noch Modellwahl, Schwelle oder Zeitfenster nachträglich beeinflussen.

Vor dem ersten Test werden Quellcode, Modelle, Skalierer, Schwellen, Qualitätsregeln und Splitmanifest gemeinsam mit Hashes eingefroren. Jede Anpassung nach Sichtung eines Tests macht diesen zu Entwicklungsdaten; ein neuer unabhängiger Test wäre nötig. Ein späterer zweiter normaler PWM-Betriebspunkt verwendet dasselbe eingefrorene Paket ohne erneutes Skalieren, Trainieren oder Schwellenanpassen. Momentan werden keinerlei Trainings- oder Testaufträge ausgeführt.

## 8. Konkrete Vorbereitung durch den Nutzer

Für die Planung bleibt der Lüfter bei **0 % PWM**. Es ist jetzt kein Start und keine Anomalieherstellung vorgesehen. Bitte zunächst eine starre, nichtleitende 60 × 120-mm-Platte, eine eigene kippsichere Halterung mit zwei Klemmstellen und ein Lineal bereitlegen. Prüfen, ob auf der Auslassseite 100 mm Abstand und die seitliche Parkposition möglich sind, ohne Lüfter, Sensor oder Kabel zu versetzen. Wenn dafür am Aufbau hantiert werden muss: erst vollständigen Stillstand feststellen und die externe 12-V-Versorgung trennen.

Sensorverschraubung und Lüfterunterlage bleiben unverändert. Vor dem späteren Pilot genügt eine Beschreibung der vorgesehenen unabhängigen Halterung, des verfügbaren Abstands und der bestehenden Unterlage; die Sensorbefestigung und GPIO18 müssen nicht erneut als offene Hardwarefragen geklärt werden. Die Platte jetzt noch nicht in die Auslassposition setzen. Erst nach Prüfung der konkreten Vorrichtung wird der nächste Versuch schrittweise angekündigt; die Softwaresteuerung übernimmt weiterhin der Assistent.
