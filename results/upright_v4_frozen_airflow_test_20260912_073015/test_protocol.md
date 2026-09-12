# Vorab festgelegter Plattenpilot mit dem eingefrorenen v4-Modellpaket

Diese neue Folge untersucht einen kontrolliert veränderten Luftstromzustand. Sie ist kein Defektnachweis. Die unterbrochene Folge vom 11.09.2026 und frühere Normaltests bleiben eigenständige Versuche; ihre Daten werden hier nicht als neue Referenzen verwendet. Die neue Folge wurde nach der Unterbrechung ausdrücklich mit dem Nutzer vereinbart. Alte Fehlerdateien und Versuchssperren bleiben erhalten.

## Umfang und unveränderter Vergleich

| Phase | Aufbauzustand | CSV-Zustand / numerisches Zustandslabel | Vorgabe | Dauer |
|---|---|---|---|---|
| `normal_before` | ohne Platte | `normal` / 0 | 75 % PWM, 25 kHz | 300 s |
| `airflow_modified` | separat befestigte Platte vor dem Auslass | `airflow_modified` / 1 | 75 % PWM, 25 kHz | 300 s |
| `normal_after` | Platte wieder entfernt | `normal` / 0 | 75 % PWM, 25 kHz | 300 s |

Das Label 1 bezeichnet ausschließlich die kontrollierte Luftstromveränderung und keinen nachgewiesenen Schaden. Das Modellpaket ist unverändert `results/upright_v4_training_pilot_20260911_130614/run_001/frozen/pilot_bundle.json`, SHA256 `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`. Modelle, StandardScaler, RMS-/Isolation-Forest-/TFLite-Schwellen und Vorverarbeitung bleiben eingefroren. Es gibt keine Anpassung anhand der neuen Ergebnisse und keine erkennungsabhängige Lüftersteuerung.

Aufbauversion: `fan_upright_position_v4_20260911_103726`. Die bereits bestätigte sichere aufrechte Lüfterposition und die ADXL345-Befestigung mit zwei Schrauben am feststehenden Rahmen werden übernommen. Lüfter und Sensor bleiben während der gesamten Folge unverändert. Sensor: nominell 200 Hz, ±2 g, Full Resolution, 0,0039 g/LSB, FIFO-Stream, I²C-Bus 1 bei konfigurierten 100 kHz. GPIO18 ist BCM GPIO18 beziehungsweise physischer Pin 12; Hardware-PWM verwendet `PWM0_CHAN2` mit 40.000 ns Periode.

## Zeitliche Durchführung und manuelle Freigaben

Jede Phase hat eine eigene aktuelle Freigabe. Die aktuelle Bereitschaft wird in einer separaten Freigabedatei dokumentiert; nur diese gilt für den ersten Start. Die allgemein erteilte Arbeitsanweisung ersetzt diese Zustandsbestätigung nicht.

Nach jeder Freigabe folgen 60 Sekunden zusätzliche Auszeit bei 0 % PWM. Anschließend kündigt beziehungsweise vollzieht die Software den vereinbarten einzelnen Start auf 75 % und zeichnet möglichst unmittelbar ab dem Stellbefehl 300 Sekunden auf. Befehlsaufruf, Befehlsabschluss, Beginn der Erfassung und erster XYZ-Leseabschluss werden getrennt dokumentiert. Es gibt keine Chatantwort während der Aufnahme, keine Antwortfrist und keinen automatischen Wiederholungsstart.

Nach jeder Aufnahme stellt die Software 0 % ein und liest PWM-Kanal und Pin-Funktion zurück. Anschließend pausiert sie. Erst nach dieser Meldung trennt der Nutzer zum manuellen Plattenumbau die externe 12-V-Versorgung und wartet auf vollständigen mechanischen Stillstand. Er setzt beziehungsweise entfernt ausschließlich die Platte, hält Lüfter und Sensor unverändert, schließt die Versorgung wieder an und meldet die Bereitschaft für genau die nächste Phase. Fehlende oder unklare Angaben sind keine Freigabe.

Die Plattenphase setzt zusätzlich die unten genannten tatsächlichen Geometrieangaben voraus. Falls sie bei der Umbaufreigabe noch fehlen, bleibt der Lüfter ausgeschaltet und nur diese Angaben werden geklärt. Es wird nicht versucht, sie aus früheren Aufnahmen abzuleiten.

Zusätzliche Auszeit ab erfasster Freigabe und gesamte Softwarezeit seit dem vorherigen 0-%-Befehlsabschluss werden separat angegeben. Für die erste Phase darf das gehashte Abschlussjournal des dritten unabhängigen Normallaufs ausschließlich als Zeitreferenz verwendet werden. Dies ist keine Übernahme seiner Messwerte als neue Normalreferenz. Die gesamte Auszeit ist nicht mit der unbekannten mechanischen Auslauf- oder Abkühlzeit gleichzusetzen; identische gesamte Auszeiten werden nicht behauptet.

## Geplante und tatsächliche Plattengeometrie

Die neue Sollgeometrie ist in [geometry_plan.json](geometry_plan.json) festgelegt: 120 × 120 mm, mittig vor dem Luftauslass, parallel zur Auslassebene, 100 mm Abstand. Der Abstand wird senkrecht von der stationären äußeren Auslassrahmenebene bis zur dem Lüfter nächstgelegenen Plattenfläche angegeben. Die Platte hat eine eigene kippsichere Halterung und berührt weder Lüfter noch Sensor.

Die Maße 120 × 120 mm und 100 mm stammen aus früheren Nutzerangaben; die mittige Anordnung ist für diesen neuen Versuch vorgesehen. Der ältere Vorschlag einer 60 × 120-mm-Platte vor der rechten Rahmenhälfte wird nicht als Istgeometrie übernommen. Die tatsächliche Auslassseite, Bezugsebenen, mittige und parallele Anordnung sowie separate Halterung sind noch nicht für diesen Versuch bestätigt. Die Luftstromrichtung ist von der Rotationsrichtung zu unterscheiden; der Nutzer dokumentiert die am Aufbau verwendete Identifikation der Auslassseite.

Tatsächliche Angaben werden vor der Plattenaufnahme separat in der Freigabe als Nutzerbeobachtung gespeichert. Sie sind keine unabhängige Vermessung durch die Software. Abweichungen von der vorgesehenen Geometrie werden vor dem Start geklärt. Der Lüfter wird hierfür nicht verschoben. Bei den Normalphasen ist die Platte aus dem Luftstrom entfernt; es wird keine anwesende Plattengeometrie behauptet.

## Speicherung und vorab festgelegte Auswertung

Jede vollständige Aufnahme erhält eine neue ID mit Phase, PWM, Dauer und UTC-Zeitstempel. CSV, Metadaten, Nutzerfreigabe, Steuerjournal, Sitzung und Auswertung werden getrennt im neuen Versuchsverzeichnis gespeichert. Keine vorhandene Datei wird überschrieben. Bereits vorhandene Roh- und Ergebnis-CSV-Dateien einschließlich früherer Trainings-, Validierungs- und Testquellen werden anhand Pfad, ID und SHA256 ausgeschlossen. Quellen- und Modellhashes werden beim Import und nach der Auswertung kontrolliert.

Für alle drei Methoden gilt ausschließlich der Abschnitt **[180,300) Sekunden seit Aufruf des 75-%-Stellbefehls**. 180 Sekunden bleiben ein Prüfkandidat für die Einlaufzeit. Je Modellfenster 128 vollständige XYZ-Punkte, Schrittweite 128, keine Überlappung und kein Fenster über Aufnahmegrenzen. Endreste werden nicht aufgefüllt. Pro Achse und Fenster wird der Float64-Mittelwert entfernt, anschließend nach Float32 konvertiert und der gespeicherte Scaler angewandt. Die numerische Anordnung und die wertgleichen Methodeneingaben entsprechen dem geprüften Trainingsweg.

Die beiden normalen Phasen werden anhand gültiger und ungültiger Fenster, Fehlalarmzahl und Fehlalarmrate unter den gültigen normalen Fenstern bewertet. Für `airflow_modified` werden gültige und ungültige Fenster sowie Anzahl und Anteil der Schwellenüberschreitungen berichtet. Dieser Alarmanteil ist keine Defekt-Recall- oder allgemeine Erkennungskennzahl. Ungültige Fenster zählen für keine Phase als NORMAL oder im Nenner der gültigen Fenster. F1 und allgemeine Defekterkennungsleistung werden nicht berechnet.

Zusätzlich wird der physische Vektor-AC-RMS in aufeinanderfolgenden 5-s-Abschnitten innerhalb [0,300) berechnet. Je Abschnitt werden die drei jeweiligen Float64-Achsenmittelwerte entfernt; danach gilt `sqrt(mean(ax_ac² + ay_ac² + az_ac²))` in g. Punktzahl und tatsächlich erfasste Zeitspanne je Abschnitt bleiben sichtbar; insbesondere fehlt dem ersten Abschnitt die kurze Zeit vor dem ersten XYZ-Leseabschluss. Qualitätsfehler werden nicht stillschweigend entfernt. Diese RMS-Werte sind vom standardisierten RMS-Modellscore zu unterscheiden.

Die vollständigen Verläufe und die 24 gleich langen Abschnitte in [180,300) werden zwischen den Phasen verglichen. Mittelwerte, Streuung, Wertebereiche und zeitliche Veränderungen innerhalb jeder Aufnahme werden von Unterschieden zwischen Aufnahmen getrennt. Die Plattenphase wird gegen beide Normalreferenzen verglichen. Die Rückkehr wird deskriptiv anhand der Differenz der Normalmittel und der Überlappung beobachteter Bereiche beurteilt; daraus wird keine universelle Rückkehrschwelle abgeleitet. Benachbarte Fenster und Abschnitte sind keine unabhängigen Versuchsreplikate.

## Qualitätsregeln und Grenzen

Zeitstempel, fortlaufende Sample-Indizes, XYZ-Punktzahl, nominale Sensorzeitschätzung, Host-Leseabstände, FIFO-Füllstände sowie Lücken-, Überlauf- und Sättigungsflags werden geprüft. Nominelle 200 Hz und tatsächlich beobachteter Durchsatz `(N−1)/Hostzeitspanne` werden getrennt ausgewiesen. Hostzeitstempel bezeichnen Leseabschlüsse und keine gemessenen Wandlungszeitpunkte; genaue physische Verluste und Drehzahl bleiben unbekannt.

Die bisherige Fensterqualität bleibt unverändert: gesetzte Lücken-, Überlauf- oder Sättigungsflags, FIFO-Füllstand 32, Host-Leseabstand über 160 ms, rohe Sättigungswerte oder nichtendliche XYZ-Werte machen betroffene Modellfenster ungültig. Für die vollständige Aufnahme gelten mindestens 299,8 s Hostzeitspanne, weniger als 1 s Verzögerung bis zum ersten XYZ-Punkt und konsistente Herkunfts- und Zeitjournale. Strukturell unzuverlässige Aufnahmen werden mit erhaltenen Rohdaten ausdrücklich als nicht auswertbar dokumentiert und nicht automatisch ersetzt.

Die vorausgegangene Normalitätsprüfung ergab bereits normale Fehlalarme bei RMS und Isolation Forest. Diese Ergebnisse bleiben erhalten. Einzelne Alarme während der Plattenphase belegen daher keine eindeutige Zuordnung zur Platte. In der separaten Normalaufnahme vom 11.09. traten auch beim Autoencoder 9/194 normale Alarme auf. Keine Methode hat damit bereits eine nachgewiesene Empfindlichkeit gegenüber dem veränderten Zustand. Eine einzelne neue Folge belegt weder allgemeine Wiederholbarkeit noch eine erfolgreiche allgemeine KI-Erkennung.

Bei einem Softwarefehler versucht die Steuerung nach Möglichkeit 0 % PWM einzustellen und zurückzulesen. Tatsächlicher Steuerstatus und Fehler werden gespeichert; es gibt keinen automatischen Neustart. Auch am Ende bleibt 0 % eingestellt. Ein mechanischer Stillstand wird nur bei entsprechender Nutzerbeobachtung als bestätigt bezeichnet. Worddatei, bestehende Modelle, historische Protokolle und Originaldaten bleiben unverändert.
