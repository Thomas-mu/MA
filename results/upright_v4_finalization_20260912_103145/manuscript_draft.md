# Implementierung

Dieses Kapitel beschreibt den am 12. September 2026 belegten Stand der lokalen Mess- und Verarbeitungskette. Die Anforderungen aus Kapitel 4 und die Vorauswahl aus Kapitel 5 werden in konkrete Komponenten, Datenregeln und Prüfungen übersetzt. Maßgeblich ist das eingefrorene Pilotpaket für Aufbau v4. Implementierte Funktionen, experimentelle Ergebnisse und verbleibende Nachweislücken werden getrennt behandelt. Die Ergebnisse stehen in Kapitel 7; die Reproduktionsunterlagen sind im Anhang zugeordnet.

## Prüfstand, Aufbauversionen und Zustandsnachweise

Der Prüfstand besteht aus einem Raspberry Pi 5, einem über I²C angeschlossenen ADXL345 und einem ARCTIC P12 Pro PST mit externer 12-V-Versorgung. Der Sensor ist nach Nutzerangabe mit zwei Schrauben an einer Ecke des äußeren, feststehenden Lüfterrahmens befestigt. Seine Platine steht schräg. Die endgültig untersuchte Aufstellung v4 ist aufrecht; die sichere Befestigung und die Rotorfreiheit wurden vom Nutzer geprüft. Eine metrische Vermessung der Sensororientierung und der gesamten mechanischen Übertragungsstrecke liegt nicht vor. Aus einer festen Befestigung allein wird keine ausreichende Messqualität abgeleitet.

Während der Entwicklung wurden Sensorbefestigung und Lüfteraufstellung verändert. Jede solche Änderung erhielt eine eigene Aufbauversion. Frühere liegende Aufnahmen und die zuvor aufrechte, später noch verschobene Position werden deshalb nicht mit v4 zu einer Normalreferenz zusammengeführt. Die verbindliche Aufbaukennung lautet fan_upright_position_v4_20260911_103726. Training, Kalibrierung und die hier bewerteten unabhängigen Versuche gehören ausschließlich zu dieser Version. Bei einer weiteren mechanischen Änderung wäre die Übertragbarkeit neu zu prüfen.

Eine nachträgliche Nutzerangabe erläutert, dass der Lüfter während eines früheren Arbeitsdurchlaufs ausgeschaltet war. Außerdem sei eine damalige PWM-Vorgabe halbiert worden. Die genauen historischen Ausgangs- und Zielwerte bleiben unbekannt. Diese Aussage ergänzt die Arbeitsdokumentation, verändert aber keine ursprünglichen Messprotokolle. Sie macht frühere Aufnahmen ohne zeitgleiche Bestätigung von Auslauf und Messbedingungen nicht nachträglich zu kontrollierten Stillstandsreferenzen.

Tabelle 6-1: Prüfstand und Bedeutung der dokumentierten Größen

| Bestandteil | Belegter Stand | Aussagegrenze |
|---|---|---|
| Zielrechner | Raspberry Pi 5, ARM64, vier CPU-Kerne; lokale Python-Ausführung | Keine Messung an Mikrocontrollern oder anderer Edge-Hardware |
| Prüflüfter | ARCTIC P12 Pro PST, externe 12-V-Versorgung | Versorgung angeschlossen nach Nutzerangabe; Spannung nicht kontinuierlich gemessen |
| Sensor und Montage | ADXL345, zwei Schrauben am äußeren Lüfterrahmen, Platine schräg; aufrechter Aufbau v4 | Orientierung und mechanische Übertragungsfunktion nicht kalibriert |
| Stellanschluss | BCM-GPIO18, physischer Pin 12; Hardware-PWM | Rückgelesene Einstellung ist keine elektrische Signal- oder Drehzahlmessung |
| Primärer Betriebspunkt | 75 % Tastgrad, 25 kHz | Keine gemessene konstante Drehzahl |
| Zweiter Normalbetriebspunkt | 50 % Tastgrad, 25 kHz; Aufbau unverändert | Normalbedingung; kein Fehlerlabel |
| Plattenzustand | Separate Platte, 120 × 120 mm, 100 mm vor dem Luftauslass, parallel ausgerichtet | Geometrie aus Nutzerangaben; keine Luftstrom- oder Druckmessung |
| Drehzahlerfassung | Kein eindeutig bestätigter separater Tachoeingang; RPM-Feld bleibt leer | Der in Kapitel 5 vorgesehene Drehzahlnachweis ist nicht erfüllt |

Die tatsächliche Plattenbreite von 120 mm weicht vom frühen Vorschlag einer 60 × 120 mm großen Platte ab. Für die abgeschlossene v4-Folge gilt die später dokumentierte Istgeometrie. Die Platte war separat befestigt und berührte nach Nutzerangabe weder Lüfter noch Sensor. Der veränderte Luftstrom wird als kontrolliert veränderter Betriebszustand bezeichnet. Ein Defekt des Lüfters wurde damit weder erzeugt noch nachgewiesen.

## Hardware-PWM und Ablaufsteuerung

Der verwendete Anschluss wird in BCM-Nummerierung angegeben: GPIO18 liegt am physischen Pin 12. Der physische Pin 18 gehört zu GPIO24. Der während der Entwicklung verwendete Befehl pinctrl set 18 op dh stellt GPIO18 auf einen gewöhnlichen Digitalausgang mit High-Pegel. Für Zwischenwerte wurde die vorhandene Hardware-PWM-Funktion wiederhergestellt. Sie erscheint auf GPIO18 als Funktion a3 mit der Bezeichnung PWM0_CHAN2. Der zugehörige Linux-Pfad ist pwmchip0/pwm2 am RP1-Controller.

Bei 25 kHz beträgt die Periodendauer 40.000 ns. Eine Vorgabe von 75 % entspricht einer Tastzeit von 30.000 ns; 50 % entspricht 20.000 ns. Bei 0 % wird eine Tastzeit von 0 ns bei weiterhin aktiviertem PWM-Kanal gesetzt. Das Modul fan_pwm.py prüft Gerätezuordnung, Kanal, Periode, Polarität und Pin-Funktion. Jeder Stellbefehl erhält monotone Zeitstempel, UTC-Zeit und eine Rücklesung. Das Öffnen und Schließen des Steuerkontexts allein verändert die Stellvorgabe nicht; die Rückstellung erfolgt ausdrücklich im Abschlusszweig des Messprogramms.

Ein exklusiver Prozess-Lock koordiniert Programme, die diesen Steuerweg verwenden. Vor Hardwareläufen werden zusätzlich mögliche konkurrierende Steuer- und Sensorprozesse geprüft. Fremde Programme können diese Sperre umgehen; der Lock ist deshalb kein elektrischer Verriegelungsmechanismus. Die Messläufe halten die vorgegebene PWM konstant. Modellentscheidungen verändern sie während des Methodenvergleichs nicht. Damit hängt der beobachtete Betriebszustand nicht von dem jeweils untersuchten Verfahren ab.

Nach jedem Betriebsversuch wird 0 % angefordert und zurückgelesen. Auch bei einem Erfassungsfehler oder einer Unterbrechung wird dieser Abschluss nach Möglichkeit ausgeführt. Ein misslungener Stellbefehl führt zu einem Fehlerstatus. Es erfolgt kein automatischer Wiederholungsstart. Softwaretests prüfen diese Pfade einschließlich Erfassungsfehler und Programmabbruch; reale Stelljournale dokumentieren die tatsächlich ausgeführten Befehle. Vollständiger mechanischer Stillstand wird nur dort als bestätigt bezeichnet, wo eine entsprechende Nutzerbeobachtung vorliegt. Die Herstellerangabe zum 0-rpm-Betrieb ersetzt diese Beobachtung nicht (ARCTIC, o. J.).

Die manuell begleiteten Versuche warten an den Umbaugrenzen auf eine ausdrückliche Freigabe. Der Nutzer trennt vor einem Plattenumbau die externe Versorgung und wartet den Auslauf ab. Nach der später erteilten Erlaubnis zum unbeaufsichtigten Softwarebetrieb wurden die festgelegten Normal- und Laufzeitfolgen ohne zusätzliche Chatabfragen ausgeführt. Hier wird die softwareseitige Auszeit dokumentiert; eine neue Sichtbestätigung für jeden automatischen Start wird nicht behauptet.

## Sensorerfassung, Zeitbasis und Qualitätskennzeichnung

Die frühere Software fragte Ausgaberegister ab, ohne die interne Sensorausgaberate und den Messbereich für jede Aufnahme vollständig zu dokumentieren. Eine damalige Schleifenfrequenz von 500 Abfragen pro Sekunde belegt daher keine 500 neuen XYZ-Messungen pro Sekunde. Der korrigierte Erfassungsweg konfiguriert den Sensor ausdrücklich und liest die Register zurück. Er verwendet den FIFO im Stream-Modus und übernimmt vollständige XYZ-Datensätze aus dem Sensorpuffer. Häufigere Host-Abfragen allein erzeugen keine zusätzlichen Sensormessungen.

Tabelle 6-2: Unveränderte Sensorkonfiguration der v4-Messkette

| Parameter | Einstellung bzw. Rücklesung | Bedeutung |
|---|---|---|
| Schnittstelle | I²C-Bus 1; konfigurierter Bustakt 100 kHz | Keine elektrische Messung der SCL-Taktfrequenz |
| Nominelle ODR | 200 Hz; Register BW_RATE = 0x0B | Sollwert der Sensorausgaberate |
| Messbereich | ±2 g; DATA_FORMAT = 0x08 | Full-Resolution-Modus |
| Umrechnung | 0,0039 g je LSB | Nomineller Faktor; keine eigene Empfindlichkeitskalibrierung |
| Betriebsmodus | POWER_CTL = 0x08 | Messbetrieb |
| FIFO | FIFO_CTL = 0x90 | Stream-Modus mit konfiguriertem Schwellwert |
| Interruptfreigabe | INT_ENABLE = 0x00 | Gepollte FIFO-Erfassung |
| Zeitstempel | Monotone Host-Zeit nach dem XYZ-Lesevorgang | Kein Zeitstempel der physikalischen Wandlung |

Die 200-Hz-Konfiguration entspricht der im ADXL345-Datenblatt empfohlenen maximalen ODR bei 100-kHz-I²C. Sie ist eine begründete Obergrenze für diese Buskonfiguration, jedoch kein Nachweis einer ausreichenden Bandbreite für beliebige Schäden (Analog Devices, 2022, S. 17). Der Messbereich ±2 g wird im Full-Resolution-Modus mit dem nominellen Faktor 0,0039 g je LSB verwendet; Sättigung wird in jedem Lauf überprüft. Die Einstellungen wurden für v4 eingefroren, obwohl die vollständige physikalische Charakterisierung der Messkette nicht abgeschlossen war. Das Modellpaket ist deshalb ausdrücklich ein Entwicklungspilot.

Vor Beginn einer Aufnahme wird der FIFO neu gestartet. Nicht aufgezeichnete Vorlaufwerte werden an dieser Grenze bewusst verworfen. Die Rohdatei enthält X, Y und Z in g, Sampleindex, Host-Zeitstempel, relative Zeit, eine aus Sampleindex/200 berechnete Sensorzeitschätzung, FIFO-Füllstand, Lesezeit und Qualitätsflags. Hinzu kommen Label und Aufnahmezuordnung. Ein XYZ-Messpunkt enthält drei einzelne Achsenwerte. Die Punktzahl wird nicht durch die Zahl der Achsen geteilt, wenn bereits vollständige CSV-Zeilen gezählt werden.

Die beobachtete Rate wird als (N − 1)/(t_N − t_1) aus den Host-Zeitstempeln bestimmt. Sie liegt in den v4-Läufen ungefähr bei 207 XYZ/s. Die Sensorzeitschätzung aus Sampleindex/200 bleibt davon getrennt: Sie ist eine Rechnung mit dem Nominalwert und keine zweite unabhängige Uhr. Host-Leseabstände dürfen schwanken, weil der Sensor puffert und die Software den FIFO ausliest. Ein auffälliger Leseabstand beweist daher allein weder eine fehlerhafte Sensorausgaberate noch einen Verlust.

Ein gesetztes Gap-, Overrun- oder Sättigungsflag kennzeichnet betroffene Daten. Zusätzlich werden nicht endliche Zahlen, ein voller FIFO und Host-Abstände über 160 ms geprüft. Die 160 ms entsprechen der nominellen Zeitkapazität von 32 FIFO-Punkten bei 200 Hz. Ein als kritisch erkennbarer Abschnitt bleibt gespeichert und wird bei der Modellbewertung ungültig. Ein Nullbefund aller Flags bedeutet, dass die implementierten Kriterien keinen Fehler anzeigen. Die genaue Anzahl möglicherweise verlorener physikalischer Sensorwerte bleibt unbekannt.

## Gemeinsame Fensterbildung und Vorverarbeitung

Die Rohaufnahmen werden vor der Fensterbildung vollständig Training, Validierung oder Test zugeordnet. Es erfolgt keine zufällige Verteilung benachbarter Fenster auf verschiedene Teilmengen. Für das v4-Pilotpaket ist der Abschnitt [180,300) Sekunden seit Aufruf des PWM-Stellbefehls festgelegt. Die ersten 180 Sekunden bleiben als Rohdaten erhalten. Die Abschnittswahl ist ein vorläufiger Einlaufkandidat und kein bereits bewiesener Zeitpunkt stationären Verhaltens.

Ab dem ersten XYZ-Punkt innerhalb dieses Abschnitts werden Gruppen mit H = 128 Punkten und Schrittweite S = 128 gebildet. Die Fenster überlappen nicht und überschreiten keine Aufnahmegrenzen. Eine unvollständige Restgruppe wird separat gezählt und weder aufgefüllt noch mit einer Folgeaufnahme verbunden. Bei ungefähr 207 XYZ/s enthält der 120-s-Abschnitt typischerweise 194 vollständige Modellfenster. Die nominelle Fensterdauer beträgt 0,64 s; das aus dem beobachteten Durchsatz abgeleitete Intervall liegt ungefähr bei 0,618 s.

Für jede Achse wird zunächst der Mittelwert des jeweiligen 128er-Rohfensters in Float64 berechnet und abgezogen. Erst danach wird das Ergebnis in Float32 überführt. Der gespeicherte, ausschließlich auf den Trainingsdaten angepasste Scaler wird anschließend unverändert angewendet. Die genaue Reihenfolge ist Teil des Paketvertrags. Ein zuvor nach Float32 gerundeter Rohdatenexport darf nicht als Ersatz für die ursprünglichen Float64-Werte erneut zentriert werden. Auch die Reduktionsreihenfolge der achsenweisen Mittelwertbildung wird im Import- und Liveweg beibehalten.

Die gemeinsame Standardisierung verwendet die gespeicherten Skalen s_X = 0,00940231 g, s_Y = 0,01110453 g und s_Z = 0,02685052 g. Die zusätzlich gespeicherten Trainingsmittelwerte liegen nahe null und werden dennoch angewendet. Für die Analyse gilt schematisch z_ij = (a_ij − μ_j)/s_j, wobei a_ij bereits den achsenweise zentrierten Beschleunigungswert bezeichnet. Scaler, Modelle und Schwellen werden im Testweg niemals neu angepasst.

Die drei Methoden erhalten dieselben standardisierten 128 × 3-Werte. Der gemeinsame Offline-Vergleich verwendet Kopien desselben Eingabefensters, sodass ein veränderlicher Arbeitsbuffer eines Verfahrens die nächste Methode nicht beeinflusst. Ungültige Eingaben erzeugen keine normale Entscheidung. Die Prüfung der Rechengenauigkeit verbindet vorbereitete Trainingsdaten, den Import neuer Aufnahmen, Offline-Replay und den Liveadapter.

## Modellpaket, Training und Kalibrierung

Das eingefrorene Paket run_001 enthält die Modellartefakte, den Scaler, die Schwellen, den Vorverarbeitungsvertrag, ein Manifest der Ursprungsaufnahmen und die zugehörigen SHA-256-Prüfsummen. Das Training verwendete zwei vollständige normale 300-s-Aufnahmen; eine dritte normale Aufnahme diente der Validierung und Schwellenkalibrierung. Nach der festgelegten Abschnittsauswahl ergeben sich 388 Trainings- und 194 Validierungsfenster. Der Scaler wurde auf 49.664 XYZ-Punkten aus den kanonischen Trainingsfenstern angepasst. Keine unabhängige Testaufnahme war daran beteiligt.

Die neuronale Architektur ist ein kleiner eindimensionaler Faltungsautoencoder. Der Encoder verarbeitet die drei Achsen mit zwei Conv1D-Schichten und zwei Poolingstufen. Der Decoder rekonstruiert die zeitliche Auflösung durch Upsampling und weitere Faltungen. Alle Faltungen außer der linearen Ausgangsschicht verwenden ReLU. Das Modell hat 507 trainierbare Parameter. Diese geringe Größe ist eine bewusste Pilotentscheidung und kein Beleg für eine optimale Architektur oder ausreichende Fehlerempfindlichkeit.

Tabelle 6-3: Architektur des ausgeführten Autoencoders

| Stufe | Operation | Ausgabeform ohne Batchdimension |
|---|---|---|
| Eingabe | Standardisierte XYZ-Werte | 128 × 3 |
| Encoder 1 | Conv1D, 8 Filter, Kernel 5; MaxPooling 2 | 64 × 8 |
| Encoder 2 | Conv1D, 4 Filter, Kernel 3; MaxPooling 2 | 32 × 4 |
| Decoder 1 | Conv1D, 4 Filter, Kernel 3; Upsampling 2 | 64 × 4 |
| Decoder 2 | Conv1D, 8 Filter, Kernel 3; Upsampling 2 | 128 × 8 |
| Rekonstruktion | Conv1D, 3 Filter, Kernel 5; linear | 128 × 3 |

Das protokollierte Training lief mit Batchgröße 32 und festgelegten Zufallsinitialisierungen 42 über 100 Epochen. Die beste gespeicherte Epoche war zugleich die letzte. Eine vorgesehene Early-Stopping-Patience von zehn Epochen beendete diesen Lauf nicht vorzeitig. Der letzte Trainingsverlust betrug rund 0,37920, der Validierungsverlust rund 0,42963. Diese Werte beschreiben die Optimierung auf Entwicklungsdaten. Sie belegen weder Konvergenz noch eine spätere Erkennungsleistung. Weitere Architekturversuche oder ein Nachtraining anhand der Testergebnisse wurden nicht durchgeführt.

Tabelle 6-4: Scores und eingefrorene Entscheidungsschwellen

| Methode | Berechnung bzw. Modell | Schwelle |
|---|---|---:|
| RMS | Quadratwurzel des Mittelwerts aller 384 quadrierten standardisierten Werte | 1,2747695377 |
| Isolation Forest | 200 Bäume; 384 Werte in fester Reihenfolge; negatives score_samples | 0,5045395247 |
| TFLite-Autoencoder | Mittlerer quadratischer Rekonstruktionsfehler über alle 128 × 3 Werte | 0,5443579661 |

Die RMS-Baseline ist dimensionslos. Sie ist nicht mit dem physikalischen Vektor-AC-RMS in g gleichzusetzen. Der Isolation Forest verwendet die Fensterwerte als einen 384-dimensionalen Vektor; er besitzt keine explizite zeitliche Nachbarschaftsstruktur. Seine Parameter umfassen 200 Bäume, max_samples = auto, einen Ausführungsthread und den Zufallsstartwert 42. Die Richtung des Scores wird so vereinheitlicht, dass größere Werte für alle drei Verfahren stärkere Auffälligkeit bedeuten.

Alle Schwellen folgen dem empirischen 99. Perzentil normaler Validierungsscores mit der dokumentierten linearen Quantilsinterpolation. Ein Fenster wird nur bei Score > Schwelle als auffällig bewertet. Gleichheit genügt nicht. Auf 194 Kalibrierungsfenstern lagen bei jeder Methode zwei Scores oberhalb der eigenen Schwelle. Dieser aus der Kalibrierung resultierende Anteil von rund 1,03 % ist keine unabhängige Fehlalarmmessung und garantiert keine spätere Fehlalarmrate von 1 %.

Der Autoencoder wurde ohne Quantisierung in ein Float32-TFLite-Modell konvertiert. Die Prüfung gegen die Keras-Ausführung umfasste die 194 normalen Validierungsfenster. Die maximale absolute Rekonstruktionsabweichung lag bei rund 1,79 · 10⁻⁶, die maximale Abweichung des mittleren quadratischen Fehlers bei rund 6,15 · 10⁻⁸. Es trat kein Entscheidungsunterschied auf. Die ursprüngliche Autoencoder-Schwelle blieb erhalten; die Konvertierung führte zu keiner erneuten Kalibrierung. Der geprüfte Interpreter auf dem Pi ist ai-edge-litert 2.1.6. Das Paket behält den Status ready_development_only, weil technische Kompatibilität die offenen physikalischen Nachweise nicht ersetzt.

## Lokaler Datenweg und Ressourceninstrumentierung

Die Software trennt Sensorzugriff, Fensterbildung, Modellauswertung, Stellsteuerung und Berichtserzeugung. Für die unabhängigen Tests wird das eingefrorene Paket ausschließlich geladen. Neue Aufnahme-IDs, Dateipfade und Hashes werden gegen bereits für Training, Validierung und Parameterwahl verwendete Daten geprüft. Fehlerhafte Provenienz oder eine veränderte Paketkennung führen zur Zurückweisung der Aufnahme. Historische Daten und Berichte bleiben erhalten.

Tabelle 6-5: Komponenten des geprüften Datenwegs

| Aufgabe | Zentrale Module | Funktion |
|---|---|---|
| Erfassung | adxl345.py; collect_real_data.py; pilot_sensor_source.py | Sensor konfigurieren, FIFO auslesen, Rohdaten und Qualität speichern |
| Aktuator | fan_pwm.py; Messablaufprogramme | Hardware-PWM prüfen, setzen und ausdrücklich auf 0 % zurückstellen |
| Datenaufbereitung | prepare_pilot_dataset.py | Aufnahmeweise Zuordnung und kanonische Float64/Float32-Fenster |
| Gemeinsamer Vergleich | pilot_method_comparison.py; common_comparison.py | Gespeicherte Skalierung, drei Scores und feste Schwellen |
| Unabhängiger Import | independent_normal_test.py; controlled_airflow_test.py; second_pwm_normal_test.py | Herkunft, Zeitabschnitt, Zustandslabel und Datenqualität prüfen |
| Lokale Ausführung | pilot_stream_final.py; pilot_runtime_final.py; pilot_recorder_final.py | Begrenzte Queue, unveränderter Modellweg und getrennte Zeitmessung |
| Laufzeitversuch | run_final_runtime_evidence.py | Ein protokollierter Prozess je Methode und Lauf; kein Wiederholungsstart nach Fehler |

Im Sensor-Livebetrieb liest ein Erfassungsthread die XYZ-Punkte, schreibt die Rohdaten und bildet die vollständigen Fenster. Eine auf vier Fenster begrenzte Queue übergibt sie an die Modellauswertung. Bei voller Queue wird das neu eintreffende Entscheidungsfenster als verworfen protokolliert. Die Rohdaten bleiben erhalten. Die Bilanz unterscheidet gebildete, ausgegebene, verworfene und beim Abbruch unverarbeitete Fenster. Ungültige Entscheidungen werden nicht als normal gezählt.

Die Instrumentierung trennt Fensteraufbau einschließlich Mittelwertentfernung, Wartezeit in der Queue, Standardisierung, Verfahrensaufruf und verfügbare Entscheidung. Beim Autoencoder werden Eingabeübertragung, Interpreter.invoke, Ausgabeübertragung und anschließende Fehlerberechnung getrennt erfasst. Für Isolation Forest bezeichnet der Rechenkern den Aufruf score_samples, für RMS die Kennwertberechnung. Die gesamte Verarbeitungslatenz endet mit der verfügbaren Entscheidung, bevor diese ins Entscheidungsjournal geschrieben wird. Fensterfüllzeit und die vor dem Host-Zeitstempel liegende Sensorauslesezeit gehören nicht zu dieser Latenz.

Ein Monitor schreibt Prozess-CPU, Resident Set Size (RSS), Prozessspitzenwert und Queue-Füllstand im Abstand von ungefähr 100 ms in eine separate Datei. 100 % CPU entsprechen der Auslastung eines logischen Kerns. Der Speicher umfasst auch Python, Bibliotheken, Erfassung und Protokollierung. Die kleinen Modelldateien sind daher nicht mit dem Prozessspeicher gleichzusetzen. Kaltstart, Laden und zwanzig vorbereitende Modellaufrufe werden außerhalb des eigentlichen Messabschnitts dokumentiert.

Der Ressourcenvergleich verwendet je Methode einen eigenen Prozess. Im Sensorbetrieb werden neue Normaldaten aufgenommen; im Offline-Replay wird dieselbe gespeicherte Aufnahme mit ihren ursprünglichen Host-Abständen wiedergegeben. Die Wiedergabe hält die Eingabedaten vorab im Speicher. Ihre RSS-Werte sind deshalb nicht unmittelbar als Speicherbedarf der Sensorerfassung zu interpretieren. Die beiden Betriebsarten erhalten getrennte Ergebnistabellen. Eine grafische Oberfläche ist im nachgewiesenen Kern nicht enthalten. Der vorhandene frühere GUI-Prototyp ist damit keine validierte Bedienoberfläche des neuen Pakets.

## Festgelegte Versuche und Nachweisgrenzen

Die unabhängigen Normaltests umfassen drei separate Starts bei 75 % PWM. Der kontrolliert veränderte Testzustand wird in einer vollständigen Folge Normal → Platte → Normal bei gleicher PWM untersucht. Ein weiterer Versuch verwendet drei normale Starts bei 50 % PWM mit unverändertem Paket. Die Modelle bewerten durchgehend dieselbe Art von 128er-Fenstern im zuvor festgelegten Abschnitt [180,300). Hohe Fehlalarmraten werden als Ergebnisse erhalten. Die Abschnittsauswahl, Skalierung und Schwellen werden nach Sichtung der Testdaten nicht geändert.

Ergänzend werden die Beschleunigungen in gleich langen 5-s-Abschnitten diagnostisch ausgewertet. Innerhalb jedes Abschnitts wird der jeweilige Achsenmittelwert entfernt. Der physikalische Vektor-AC-RMS lautet R_AC = √[mean((X − X̄)² + (Y − Ȳ)² + (Z − Z̄)²)]. Er wird in g beziehungsweise mg angegeben; 1 mg entspricht 0,001 g. Er besitzt weder dieselbe Fensterlänge noch dieselbe Skalierung wie die drei Modellscores. Diese Trennung gilt auch für die explorative Fehleranalyse.

Die Softwareprüfung des abschließenden Livewegs umfasst 18 gezielte Tests. Sie prüft die Übereinstimmung der Scores auf realen eingefrorenen Referenzfenstern sowie Fehlerpfade für Datenqualität, Überlast und geordnetes Beenden. Die zusätzlichen Hardwareläufe liefern den Nachweis der tatsächlichen lokalen Verarbeitung. Eine nachgewiesene Defektklasse, eine unabhängige Drehzahlmessung und eine vollständig kalibrierte physikalische Zeitbasis gehören weiterhin zu den offenen Nachweisen. Kapitel 7 bewertet die Anforderungen deshalb einzeln und setzt eine erfolgreiche Programmausführung nicht mit der vollständigen Erfüllung aller MUSS-Anforderungen gleich.

# Evaluation und Ergebnisse

Die Evaluation betrachtet Erfassung, numerische Konsistenz, Fehlalarme, Reaktion auf den Plattenzustand und technischen Aufwand getrennt. Alle hier verglichenen Erkennungsergebnisse verwenden das eingefrorene v4-Paket mit unveränderten Modellen, Skalierungen, Schwellen und Testabschnitten. Die Dateiverweise im Anhang führen zu Rohdaten, Metadaten, vorab festgelegten Protokollen und maschinenlesbaren Ergebnissen. Nachträgliche Ursachenuntersuchungen sind als explorative Fehleranalyse gekennzeichnet.

## Datenbasis und Auswertungseinheit

Tabelle 7-1: Aufnahmen für Entwicklung und unabhängige Erkennungsprüfung

| Gruppe | Vollständige Aufnahmen | Verwendung | Vollständige 128er-Fenster |
|---|---:|---|---:|
| Normales Training, 75 % | 2 × 300 s | Modell- und Scaleranpassung | 388 |
| Normale Validierung, 75 % | 1 × 300 s | Entwicklungsprüfung und Schwellen | 194 |
| Erste unabhängige Normaltests, 75 % | 3 × 300 s | Fehlalarmprüfung | 582 |
| Zusätzliche Normalreferenz vom 11.09., 75 % | 1 × 300 s | Eigenständiger Test; anschließender Plattenstart abgebrochen | 194 |
| Folge vom 12.09.: Normal → Platte → Normal, 75 % | 3 × 300 s | Zwei Normalreferenzen und ein veränderter Zustand | 582 |
| Zweiter Normalbetriebspunkt, 50 % | 3 × 300 s | Unverändertes Paket unter geänderter Normalbedingung | 582 |

Die ersten beiden Normalaufnahmen der Entwicklungsfolge und der zusätzliche normale Entwicklungsstart wurden später für Training beziehungsweise Validierung verwendet. Sie werden im Testvergleich nicht nochmals als unabhängige Bestätigung gezählt. Die früheren Aufbauversionen bleiben ausgeschlossen. Der zusätzliche Normaltest vom 11. September bleibt erhalten, obwohl der damals geplante anschließende Plattenlauf vor einer Aufnahme an einer nicht passenden Pin-Funktion scheiterte. Es wurde kein fehlender Lauf als erfolgreich protokolliert und keine Datei durch einen Ersatz überschrieben.

In der unabhängigen Erkennungsprüfung liegen damit neun normale Aufnahmen und eine Aufnahme des kontrolliert veränderten Zustands vor. Jede ergibt 194 gültige Fenster im festgelegten Abschnitt; ungültige Bewertungsfenster wurden in diesen Abschnitten nicht festgestellt. Das ergibt 1.746 normale und 194 veränderte Fenster. Die Fenster dienen der zeitlichen Auflösung und zählen nicht als ebenso viele unabhängige Versuchsreplikate. Insbesondere ist eine einzelne Plattenfolge keine statistisch belastbare Reproduzierbarkeitsprüfung.

Die zusätzlich aufgenommenen Laufzeitversuche werden gesondert behandelt. Sie dienen der Prüfung des lokalen Datenwegs und des technischen Aufwands. Die vorab ausgewählte Datenbasis für den Vergleich der Fehlalarmraten wird durch diese späteren Versuche nicht nachträglich erweitert oder neu gewichtet.

## Erfassungsqualität und physikalische Zeitbasis

Die v4-Aufnahmen enthalten vollständige XYZ-Punkte mit steigenden monotonen Host-Zeitstempeln und fortlaufenden Softwareindices. Die drei neuen 50-%-Normalaufnahmen enthalten 62.142, 62.133 und 62.133 XYZ-Punkte. Ihre beobachteten Raten betragen 207,1442, 207,1118 und 207,1145 XYZ/s. Der erste Punkt liegt jeweils rund 95–98 ms nach dem Aufruf des Stellbefehls. Die längsten Host-Leseabstände betragen 8,576, 9,790 und 9,427 ms. Gap-, Overrun- und Sättigungsflags sind in allen drei Rohaufnahmen null; nicht endliche Werte oder nicht monotone Zeitstempel wurden nicht gefunden.

Die abgeschlossene Plattenfolge zeigt ebenfalls einen Durchsatz von ungefähr 207 XYZ/s. Die Messdauer wird durch Host-Zeitstempel begrenzt, nicht durch eine fest angeforderte Zahl von 60.000 Punkten. Die rund 62.100 Punkte je 300 s sind daher keine versehentliche Addition der Achsenwerte. Entsprechend waren die früher diskutierten 6.205 Werte einer 30-s-Datei vollständige XYZ-Zeilen und somit 18.615 einzelne Achsenwerte. Die Abweichung von nominell 200 Hz ist wiederholt beobachtet und nicht durch eine Bezeichnungskorrektur beseitigt.

Gesichert sind die programmierte ODR, die zurückgelesenen Register, der FIFO-Erfassungsweg und der mittlere Durchsatz nach der Host-Uhr. Nicht gesichert ist die Ursache der ungefähr 3,5 % höheren Rate. Die vorhandenen Aufnahmen enthalten keine unabhängig gemessenen Wandlungszeitpunkte oder ein externes Referenzsignal. Eine Abweichung des realen Sensortakts ist eine mögliche Erklärung; ohne direkten Nachweis wird sie nicht zur festgestellten Ursache erklärt. Ein vollständiger Ausschluss unerkannter Verluste, von Aliasing oder von Problemen der physikalischen Bandbegrenzung ist ebenfalls nicht möglich.

Die bereits vor dem Modelltraining ausgeführte Spektralprüfung der v4-Entwicklungsdaten fand einen gemeinsamen dominanten Anteil bei ungefähr 39,45 Hz auf der aus dem Durchsatz geschätzten 1024er-FFT-Achse. Auf einer mit 200 Hz beschrifteten Achse liegt derselbe Bin bei 38,08594 Hz. Unterschiede dieser Zahlen entstehen durch die Achsenskalierung und sind kein Drehzahlnachweis. Auch die gröbere 128er-Diagnostik besitzt ein anderes Frequenzraster. Der Signalabstand zum Stillstand und eine starke gemeinsame Spektrallinie belegen messbare Betriebsanregung, aber keine Empfindlichkeit für einen bestimmten Defekt.

## Fehlalarme bei unverändertem Normalbetrieb

Tabelle 7-2: Unabhängige Normalaufnahmen bei 75 % PWM

| Aufnahme | gültig / ungültig | RMS: Fehlalarme | Isolation Forest: Fehlalarme | Autoencoder: Fehlalarme |
|---|---:|---:|---:|---:|
| Normaltest 1, 11.09. | 194 / 0 | 57 (29,38 %) | 34 (17,53 %) | 0 (0,00 %) |
| Normaltest 2, 11.09. | 194 / 0 | 0 (0,00 %) | 0 (0,00 %) | 0 (0,00 %) |
| Normaltest 3, 11.09. | 194 / 0 | 0 (0,00 %) | 0 (0,00 %) | 0 (0,00 %) |
| Zusätzliche Normalreferenz, 11.09. | 194 / 0 | 2 (1,03 %) | 1 (0,52 %) | 9 (4,64 %) |
| normal_before, 12.09. | 194 / 0 | 1 (0,52 %) | 0 (0,00 %) | 51 (26,29 %) |
| normal_after, 12.09. | 194 / 0 | 0 (0,00 %) | 0 (0,00 %) | 4 (2,06 %) |
| Zusammengefasst | 1.164 / 0 | 60 (5,15 %) | 35 (3,01 %) | 64 (5,50 %) |

Die Methoden reagieren nicht gleich auf die Variation zwischen normalen Starts. Der erste unabhängige Normaltest erzeugt vor allem RMS- und Isolation-Forest-Fehlalarme. Dagegen fällt der Autoencoder in der späteren Aufnahme normal_before durch 51 Fehlalarme auf. Die Zusammenfassung verschleiert diese Unterschiede teilweise. Kein Verfahren zeigt auf allen normalen Aufnahmen den bei der Validierung beobachteten Alarmanteil von ungefähr 1 %.

Die Fehlalarmrate wird ausschließlich unter gültigen normalen Fenstern berechnet. Sie ist eine Beschreibung dieser Testaufnahmen und keine Schätzung mit 1.164 unabhängigen Wiederholungen. Zeitlich benachbarte Fenster sind abhängig. Die einzelnen Starts unter derselben Montage decken außerdem nur einen kleinen Ausschnitt möglicher Normalbedingungen ab.

## Kontrollierte Luftstromveränderung und Rückkehrreferenz

Die am 12. September abgeschlossene Folge verwendet die Labels normal_before, airflow_modified und normal_after. Alle drei Aufnahmen dauerten 300 s bei 75 % PWM und 25 kHz. Die Platte blieb während ihres Laufs unverändert positioniert. Vor ihrem Einsetzen und Entfernen erfolgten die manuell freigegebenen Umbaupausen. Einheitliche zusätzliche Wartezeiten von 60 s bedeuten dabei keine identischen gesamten Auszeiten.

Tabelle 7-3: Entscheidungen der drei Methoden in der vollständigen Plattenfolge

| Zustand | gültige Fenster | RMS: auffällig | Isolation Forest: auffällig | Autoencoder: auffällig |
|---|---:|---:|---:|---:|
| Normal vorher | 194 | 1 (0,52 %) | 0 (0,00 %) | 51 (26,29 %) |
| Luftstrom verändert | 194 | 7 (3,61 %) | 4 (2,06 %) | 0 (0,00 %) |
| Normal nachher | 194 | 0 (0,00 %) | 0 (0,00 %) | 4 (2,06 %) |

Bei den Normalreferenzen sind die auffälligen Entscheidungen Fehlalarme. Für die Plattenaufnahme wird der Alarmanteil unter einem kontrolliert veränderten Betriebszustand angegeben. Er ist kein allgemeiner Defekt-Recall. Der Autoencoder markiert keinen ihrer 194 Fenster als auffällig, obwohl die physikalische Vibrationsstärke gegenüber beiden benachbarten Normalreferenzen steigt. RMS und Isolation Forest reagieren nur auf wenige Fenster. Eine zuverlässige Unterscheidung dieses veränderten Zustands ist mit dem Paket damit nicht belegt.

Tabelle 7-4: Physikalischer Vektor-AC-RMS der 5-s-Abschnitte von 180 bis 300 s

| Zustand | Mittelwert [mg] | Streuung der 24 Abschnitte [mg] | beobachteter Bereich [mg] | lineare Steigung [mg/min] |
|---|---:|---:|---|---:|
| Normal vorher | 28,458 | 1,618 | 26,593–33,214 | −0,707 |
| Luftstrom verändert | 38,053 | 1,299 | 36,386–41,676 | −0,903 |
| Normal nachher | 32,074 | 2,781 | 26,866–35,349 | −0,544 |

![Abbildung 7-1: Vollständige 5-s-RMS-Verläufe der unabhängigen Folge Normal → Platte → Normal. Die Markierung bei 180 s kennzeichnet den vorab gewählten Prüfabschnitt. Quelle: eigene Messungen vom 12.09.2026.](/home/malik/masterarbeit-edge-ai/results/upright_v4_frozen_airflow_test_20260912_073015/comparison_complete/rms_5s.png)

Nach Entfernen der Platte sinkt das mittlere Vibrationsniveau, kehrt aber nicht vollständig zum vorherigen Mittelwert zurück. Die Differenz zwischen beiden Normalreferenzen beträgt 3,616 mg beziehungsweise 12,71 % des vorherigen Mittels. Dreizehn der 24 nachherigen 5-s-Werte liegen im zuvor beobachteten Bereich. Diese Bereichsüberlappung beweist keine Gleichwertigkeit; die Abweichung ist aber ebenso wenig ein Beleg für einen entstandenen Defekt. Der Unterschied Platte–Nachher beträgt 5,978 mg und ist kleiner als die gesamte beobachtete Spannweite beider Normalreferenzen von 8,756 mg.

Die linearen Steigungen in Tabelle 7-4 beschreiben Verläufe innerhalb einzelner Aufnahmen. Sie werden nicht mit den unterschiedlichen Mittelwerten zwischen Starts verwechselt. Beispielsweise unterscheiden sich die Mittelwerte der ersten und zweiten Hälfte von normal_before nur um rund +0,046 mg, obwohl die lineare Anpassung eine negative Steigung ergibt. Schwankungen und einzelne Abschnitte beeinflussen die Anpassung. Aus diesen Daten ergibt sich kein Nachweis eines über alle Starts gleichen kontinuierlichen Einlauftrends. Die 180 Sekunden bleiben deshalb ein unveränderter Prüfkandidat, nicht eine nachträglich verschobene Grenze und nicht eine allgemeine Stationaritätsgarantie.

## Explorative Fehleranalyse der Modellentscheidungen

Die Frage, weshalb der Autoencoder im Normalzustand 51 von 194 Fenstern markiert, im Plattenzustand aber kein einziges, wurde nach Kenntnis der Testergebnisse untersucht. Diese Untersuchung ist ausdrücklich eine explorative Fehleranalyse. Sie ändert weder die Schwelle noch die Auswahl des Testabschnitts und liefert keinen zusätzlichen unabhängigen Test. Für jeden Vergleich wurden exakt dieselben 128er-Fenster des eingefrorenen Datenwegs verwendet. Die in Abbildung 7-1 dargestellten 5-s-Kennwerte wurden nicht als Modellscores eingesetzt.

Die Signalstärke in physikalischen Einheiten erklärt die Entscheidungen nicht allein. Der Mittelwert des physischen Vektor-AC-RMS der Modellfenster steigt von rund 28,408 mg vor der Änderung auf 38,025 mg mit Platte. Rund 95 % des Zuwachses der mittleren quadratischen Signalenergie entfallen auf die Z-Achse. Die Standardisierung gewichtet diese Achse jedoch schwächer. Bezogen auf dieselbe physische quadratische Amplitude beträgt das Gewicht der X-Achse ungefähr das 8,16-Fache und das der Y-Achse das 5,85-Fache des Gewichts der Z-Achse. Diese Verhältnisse folgen unmittelbar aus den inversen Quadraten der gespeicherten Skalierungsfaktoren.

Tabelle 7-5: Mittlerer Autoencoder-Rekonstruktionsfehler je Achse auf identischen Modellfenstern

| Zustand | MSE X | MSE Y | MSE Z | gesamter MSE |
|---|---:|---:|---:|---:|
| Normal vorher | 0,824745 | 0,538481 | 0,175125 | 0,5128 |
| Luftstrom verändert | 0,621914 | 0,473663 | 0,184719 | 0,4268 |

Der Gesamtfehler ist das arithmetische Mittel der drei Achsenfehler. Der mit Platte geringfügig höhere Z-Fehler wird durch kleinere X- und Y-Fehler überkompensiert. Die gespeicherte obere Schwelle von rund 0,54436 wird deshalb seltener und in dieser Aufnahme überhaupt nicht überschritten. Ein größerer physischer Vektor-RMS muss bei dieser Vorverarbeitung und diesem Modell somit keinen größeren Anomaliescore verursachen. Auch der RMS-Modellscore wird aus standardisierten Werten berechnet und ist nicht identisch mit dem physischen Vektor-AC-RMS.

![Abbildung 7-2: Achsenbeiträge zur physischen Energie, zur standardisierten Energie und zum Autoencoder-Fehler auf denselben 128er-Fenstern. Dargestellt sind Mittelwerte je Aufnahme; sie ersetzen nicht die Entscheidungen einzelner Fenster. Quelle: eigene explorative Auswertung.](/home/malik/masterarbeit-edge-ai/results/upright_v4_exploratory_diagnosis_20260912_081728/axis_decomposition.png)

Vierzig der 51 Autoencoder-Fehlalarme in normal_before liegen in den ersten 60 s des ausgewerteten Abschnitts, also zwischen 180 und 240 s ab dem Stellbefehl. Innerhalb dieser Aufnahme besteht ein starker positiver Zusammenhang des Fehlers mit der X-Schwingungsstärke; die explorativ berechnete Korrelation beträgt ungefähr 0,82. Mit der Z-Schwingungsstärke besteht kein vergleichbar ausgeprägter Zusammenhang. Die Fehlalarme kennzeichnen daher keine einfache Überschreitung der Gesamtvibration.

Die Spektralanalyse zeigt keine ausschließlich in den fehlerhaft markierten Fenstern vorkommende neue dominante Linie. Ein gemeinsamer dominanter Z-Anteil liegt im groben 128er-Raster bei Bin 24: 37,5 Hz bei nominell 200 Hz beziehungsweise ungefähr 38,8 Hz bei Skalierung mit dem beobachteten Durchsatz. Das ist mit dem gemeinsamen Schwingungsanteil der höher aufgelösten Entwicklungsanalyse vereinbar. Die Frequenzraster sind verschieden; aus den Binmitten wird keine unterschiedliche tatsächliche Drehzahl abgeleitet.

Der Plattenzustand liegt in den untersuchten Einzelmerkmalen weitgehend innerhalb bereits bekannter normaler Variation. Beim physischen Modellfenster-RMS liegen 188 von 194 Plattenfenstern innerhalb der Spannweite der normalen Validierungsaufnahme; unter Einbezug der zuvor untersuchten Normalaufnahmen sind es 194. Auch alle 194 Autoencoder-Scores liegen innerhalb der Spannweite der Normalvalidierung. Ein Vergleich eindimensionaler Spannweiten beweist keine Gleichheit der gemeinsamen Verteilungen. Er erklärt jedoch, weshalb diese Merkmale keine klare neue Abweichung anzeigen müssen. Die Prüfkette selbst wurde anhand identischer Fenster und Scores abgeglichen; die beobachtete geringe Trennung wird nicht als Import- oder Rundungsfehler umgedeutet.

Belegt sind die Achsengewichtung, die kleineren X- und Y-Rekonstruktionsfehler, die zeitliche Häufung der normalen Fehlalarme und die genannten Merkmalsüberlappungen. Ungeklärt bleibt, welche physikalischen Mechanismen die Unterschiede zwischen den Starts erzeugen. Kontaktbedingungen, Aufstellungsdynamik, thermische Einflüsse, Luftströmung und Drehzahländerungen sind mögliche Ursachen. Ohne gezielte Messung sind sie keine festgestellten Erklärungen.

## Zweiter normaler Betriebspunkt bei 50 % PWM

Für FF4 wurden drei zusätzliche Normalstarts ohne Platte bei 50 % PWM und unverändertem Aufbau v4 aufgezeichnet. Modelle, Skalierung, Schwellen, Sensorregister und Bewertungsabschnitt blieben gleich. Die niedrigere Stellvorgabe wurde vorab als zweite normale Bedingung festgelegt. Ihre Daten wurden weder zum Nachtraining noch zur erneuten Kalibrierung verwendet. Ein Tastgradwechsel ist nicht gleichbedeutend mit einer gemessenen Drehzahländerung.

Tabelle 7-6: Fehlalarme im zweiten normalen Betriebspunkt

| Aufnahme | gültig / ungültig | RMS | Isolation Forest | Autoencoder |
|---|---:|---:|---:|---:|
| 50 %, Lauf 1 | 194 / 0 | 1 (0,52 %) | 0 (0,00 %) | 17 (8,76 %) |
| 50 %, Lauf 2 | 194 / 0 | 2 (1,03 %) | 1 (0,52 %) | 11 (5,67 %) |
| 50 %, Lauf 3 | 194 / 0 | 0 (0,00 %) | 0 (0,00 %) | 7 (3,61 %) |
| 50 %, zusammen | 582 / 0 | 3 (0,52 %) | 1 (0,17 %) | 35 (6,01 %) |
| 75 %, sechs frühere Normalaufnahmen | 1.164 / 0 | 60 (5,15 %) | 35 (3,01 %) | 64 (5,50 %) |

![Abbildung 7-3: Fehlalarmraten je vollständiger Normalaufnahme und zusammengefasst bei 75 % und 50 % PWM mit demselben eingefrorenen Paket. Die Aufnahmen sind nicht zeitgleich oder randomisiert gepaart. Quelle: eigene Testauswertung.](/home/malik/masterarbeit-edge-ai/results/upright_v4_second_pwm50_20260912_091000/comparison_50_vs_75/false_alarm_comparison.png)

Bei RMS und Isolation Forest sinkt der zusammengefasste Fehlalarmanteil im vorliegenden Vergleich. Beim Autoencoder steigt er von 5,50 % auf 6,01 %, also um ungefähr 0,52 Prozentpunkte. Innerhalb der drei 50-%-Starts nimmt sein Anteil von 8,76 % auf 3,61 % ab. Das erlaubt keine allgemeine Aussage, eine niedrigere PWM sei günstiger oder ungünstiger. Die Methoden reagieren unterschiedlich, und die zeitlich getrennten Reihen isolieren die PWM nicht von sämtlichen weiteren Einflüssen. H3 wird deshalb nicht als allgemeine oder kausal nachgewiesene Zunahme bestätigt.

Die physischen 5-s-RMS-Mittelwerte im späten Abschnitt liegen bei 16,761, 16,600 und 16,485 mg. Die Streuungen innerhalb der Läufe betragen 0,690, 1,226 und 0,308 mg. Im zweiten Lauf reicht die Spannweite bis 21,918 mg, obwohl sein Mittelwert nahe an denen der anderen Starts liegt. Ein ähnlicher Mittelwert bedeutet folglich keine identischen Verläufe. Die niedrigere physische Amplitude allein begründet keine Änderung des primären 75-%-Modellpakets.

## Laufzeit, Ressourcen und lokaler Sensorbetrieb

Noch nicht freigegebener Entwurf: Laufzeitmatrix läuft.

## Erfüllungsgrad der Anforderungen

Die Tabelle ordnet die Ergebnisse den ursprünglichen Anforderungen aus Kapitel 4 zu. „Nachgewiesen“ bezieht sich stets auf den angegebenen Versuchsumfang. Ein dokumentierter Teilnachweis wird nicht mit vollständiger Erfüllung gleichgesetzt. Die MUSS-Prioritäten werden durch schwache Ergebnisse oder ausstehende Messungen nicht nachträglich verändert.

Tabelle 7-9: Nachweisstand der Anforderungen A1–A13

| ID | Stand | Beleg und Grenze |
|---|---|---|
| A1 | Teilweise nachgewiesen | XYZ, Einheit, Zeitstempel, Flags, Host-Abstände und Spektren geprüft; physikalischer Sensortakt, genaue nutzbare Bandbreite und unbekannte physische Verluste nicht abschließend bestimmt. |
| A2 | Nachgewiesen | Ganze Aufnahmen getrennt; Training und Kalibrierung nur normal; Scaler ausschließlich an Trainingspunkten angepasst. |
| A3 | Nachgewiesen | Identische 128er-Testfenster, gemeinsame Quantilregel und eingefrorene Vorverarbeitung für alle drei Methoden. |
| A4 | Im Messumfang nachgewiesen | Automatische lokale Verarbeitung und maschinenlesbare Entscheidungen; ungültige Fenster getrennt behandelt. |
| A5 | Nachgewiesen | Aufnahme-, Protokoll-, Modell- und Codekennungen sowie Hashes und Umgebungsdaten gespeichert. |
| A6 | Nachgewiesen | Ausführung auf dem Raspberry Pi; numerischer Konvertierungsvergleich und identischer Live-/Offline-Datenweg geprüft. |
| A7 | Siehe Abschnitt 7.7 | P99 und Fristüberschreitungen gegen das beobachtete Fensterintervall geprüft; keine harte Echtzeitgarantie. |
| A8 | Für endliche Läufe geprüft | CPU, RSS, Modellgrößen, Queue und Verluste gemessen; kein Nachweis unbegrenzten Dauerbetriebs. |
| A9 | Teilweise nachgewiesen | Fehlalarme je Normalaufnahme und Alarmanteile der kontrollierten Änderung; keine belastbare allgemeine Defektleistung und kein entsprechender F1-Nachweis. |
| A10 | Nachgewiesen | Drei normale 50-%-Tests bei unverändertem Paket; Vergleich zu den vorab bestimmten 75-%-Normalreferenzen. |
| A11 | Teilweise nachgewiesen | Aufbauversionen und Schritte dokumentiert; unabhängige Normalstarts vorhanden, aber nur eine abgeschlossene unabhängige Plattenfolge und keine vollständige Rückkehr zum vorigen Mittelwert. |
| A12 | Optional, nicht Teil des Nachweises | Frühere Oberfläche vorhanden; Integration und Zusatzlast des eingefrorenen Pakets nicht als geprüft ausgewiesen. |
| A13 | Nachgewiesen | Eindeutige Aufnahmen, erhaltene Rohdaten, geordneter Abschluss und 0-%-Fehlerpfad durch Läufe und Softwaretests geprüft. |

# Diskussion

## Aussagekraft des Methodenvergleichs

Die Arbeit trennt drei Ebenen: die korrekte Softwareausführung, die Beschreibung der gemessenen Versuchszustände und die Generalisierung auf bislang ungesehene Fehler. Für die erste Ebene liegen konsistente Offline- und Live-Datenwege sowie numerische Modellprüfungen vor. Für die zweite Ebene stehen unabhängige Normalaufnahmen, eine kontrollierte Luftstromfolge und ein zweiter normaler Betriebspunkt zur Verfügung. Für die dritte Ebene reicht diese Datenbasis nicht aus.

Die höhere Komplexität des Autoencoders führt im vorliegenden Versuch nicht zu einer nachgewiesenen Überlegenheit. Er erzeugt in einer Normalreferenz zahlreiche Fehlalarme und markiert den Plattenzustand gar nicht. Die einfacheren Verfahren unterscheiden den veränderten Zustand ebenfalls nur schwach. Diese Ergebnisse bleiben Bestandteil der Evaluation. Sie werden nicht durch neue Schwellen, ausgesuchte Fenster oder nachträgliches Nachtraining verbessert. Eine methodisch einheitliche Prüfung kann daher zu dem Ergebnis führen, dass das geprüfte Paket für den gewählten Zustand nicht ausreichend empfindlich ist.

H1 setzt einen Vergleich der F1-Werte unter definierten Versuchsanomalien voraus. Die äußere Luftstromveränderung ist zwar absichtlich herbeigeführt, aber kein nachgewiesener Defekt. Zudem liegt nur eine unabhängige veränderte Aufnahme vor. Ein allgemeiner F1-Nachweis für Defekterkennung wird deshalb nicht beansprucht. Der beobachtete Alarmanteil ist für den konkret geänderten Zustand beschreibbar; eine geeignete Fehlerklasse oder deren spätere Häufigkeit wird dadurch nicht festgelegt. H1 bleibt im angestrebten umfassenden Sinn ungeklärt, und eine Überlegenheit des neuronalen Hauptverfahrens ist nicht belegt.

Die Normaltests zeigen, dass die Normalvalidierung die tatsächlich beobachtete Variation zwischen Starts nur begrenzt repräsentiert. Eine auf einem normalen Validierungslauf kalibrierte obere 99-%-Schwelle ergibt nicht automatisch 1 % Fehlalarme in späteren normalen Aufnahmen. Die Unterschiede betreffen sowohl das physische Signal als auch die achsenabhängigen Modellfehler. Weitere Normalläufe könnten die Variation genauer beschreiben, würden aber die bereits gemessenen Fehlalarmraten des eingefrorenen Pakets nicht rückwirkend ändern.

## Einlaufzeit, Aufstellung und Vorverarbeitung

Der Abschnitt von 180 bis 300 s wurde vor den unabhängigen Tests festgelegt. Er entfernt die unmittelbare Startphase aus der Modellbewertung, garantiert aber keine stationäre Verteilung. Ein Unterschied zwischen zwei Startmittelwerten und ein zeitlicher Trend innerhalb eines Starts sind verschiedene Befunde. Nicht überlappende RMS-Bereiche widerlegen für sich genommen keine geeignete Einlaufzeit. Umgekehrt belegen ähnliche Mittelwerte oder eine optisch ruhige Kurve keine allgemeine Reproduzierbarkeit. Die vorliegenden Verläufe werden deshalb ohne nachträgliche Abschnittsanpassung berichtet.

Die Aufbauversion ist Teil der Gültigkeitsgrenze. Änderungen von Sensorbefestigung und Lüfteraufstellung wurden als neue Versionen behandelt. Alte liegende Aufnahmen wurden nicht mit den v4-Daten zu einer gemeinsamen Normalreferenz vermischt. Ein stärkeres Befestigen des heutigen Aufbaus könnte sein dynamisches Verhalten verändern und würde eine neue Datenbasis erfordern. Es ist keine reine Softwarekorrektur. Der eingefrorene Vergleich lässt sich wissenschaftlich abschließen, ohne den Aufbau so lange zu verändern, bis die Kennzahlen günstiger ausfallen.

Die Vorverarbeitung entfernt pro Achse und Fenster den Gleichanteil. Dadurch wird die statische Orientierung nicht direkt als Anomaliesignal verwendet. Die anschließende Skalierung stellt jedoch nicht automatisch alle physikalischen Richtungen gleich. Sie teilt durch die im Training geschätzte jeweilige Achsenstreuung. Der Zuwachs einer bereits stark streuenden Achse kann daher im standardisierten Score weniger ins Gewicht fallen als kleinere Veränderungen einer zuvor ruhigen Achse. Dies ist eine dokumentierte Eigenschaft des gewählten Verfahrens. Eine andere Gewichtung wäre eine neue Modell- und Vorverarbeitungsversion, deren Nutzen unabhängig geprüft werden müsste.

## Technische Grenzen und Übertragbarkeit

Die lokale Laufzeitprüfung beantwortet eine andere Frage als die Erkennungstests: ob die gespeicherte Verarbeitung auf der Zielhardware im festgelegten Messumfang Schritt halten kann. Numerische Konsistenz und kurze Latenz machen eine fachlich ungeeignete Entscheidung nicht richtig. Ebenso bedeutet eine schwache Zustandstrennung nicht, dass der Erfassungs- oder Ausführungsweg falsch implementiert ist. Die getrennten Nachweise verhindern diese Vermischung.

Die Zeitbewertung beginnt mit dem hostseitig vollständigen Fenster. Sie enthält weder die physikalische Fensterfüllzeit noch eine unbekannte Verzögerung zwischen Sensorwandlung und Host-Leseabschluss. Ein endlicher Test unter gewöhnlichem Linux ist keine harte Echtzeitzusage. Die optionale GUI wurde aus dem abschließenden Messweg ausgeschlossen; ihre frühere Existenz ersetzt keinen Nachweis ihrer Zusatzlast mit dem neuen Paket.

Die unbekannte tatsächliche Drehzahl begrenzt die physikalische Interpretation. Ein vorhandener PWM-Registerwert belegt eine Stellvorgabe, aber keine gemessene Signalform oder Rotationsgeschwindigkeit. Die um rund 3,5 % höhere beobachtete Punktzahl gegenüber der nominalen ODR ist konsistent dokumentiert. Sie bleibt als offene Ursache bestehen. Eine nachträgliche Umbenennung in einen 207-Hz-Sensorbetrieb wäre ohne Referenzmessung nicht gerechtfertigt.

Die Generalisierung bleibt auf diesen Lüfter, die dokumentierte Montage, die verwendete Sensorik und kurze Messserien beschränkt. Weder wechselnde Geräte noch langfristige Alterung, Temperaturbereiche oder verschiedene tatsächliche Defekte wurden systematisch untersucht. Die Arbeit liefert damit einen nachvollziehbaren Pilotvergleich mit klaren Grenzen und keine betriebsfertig validierte industrielle Fehlerdiagnose.

# Ausblick und verbleibende Nachweise

Der vorhandene Modellstand sollte als abgeschlossener Pilotstand erhalten bleiben. Für die Dokumentation ist keine weitere Wiederholung gleicher Normalstarts erforderlich, nur um eine günstigere durchschnittliche Kennzahl zu erreichen. Künftige Messungen sollten jeweils eine benannte offene Frage beantworten und vorab einen eigenen Auswertungsplan erhalten.

Die erste offene physikalische Frage betrifft die Zeitbasis. Ein kleinster gezielter Versuch wäre eine unabhängig referenzierte Messung des Data-Ready-Takts beziehungsweise eines bekannten Anregungssignals zusammen mit dem unveränderten FIFO-Datenweg. Dafür müssen geeignete Messmittel, Signalanbindung und zulässige elektrische Pegel vorab geklärt werden. Das Ergebnis könnte die Abweichung zwischen nominaler ODR und Host-Durchsatz einordnen; aus den vorhandenen Dateien allein ist diese Ursache nicht sicher auflösbar.

Eine zweite Frage betrifft die tatsächliche Drehzahl. Dafür wäre ein bestätigter separater Tachoanschluss oder ein berührungsloses Referenzmessgerät erforderlich. GPIO18 bleibt der PWM-Ausgang und wird nicht gleichzeitig als bestätigter Tachoeingang behandelt. Beschaltung, Pegel und Impulse pro Umdrehung müssten dokumentiert werden. Erst danach ließen sich Stellvorgabe, Drehzahl und Frequenzmerkmale nachvollziehbar miteinander vergleichen.

Für einen erweiterten Erkennungsnachweis muss zunächst festgelegt werden, welcher kontrolliert veränderte Zustand die Zielklasse bilden soll. Eine weitere äußere Luftstromänderung könnte die Empfindlichkeit gegenüber diesem Betriebszustand untersuchen, wäre aber weiterhin kein automatischer Defektnachweis. Manipulationen an einem laufenden Rotor sind ausgeschlossen. Änderungen erfolgen ausschließlich nach Trennen der externen Versorgung und bestätigtem Stillstand; Sensor und Aufstellung bleiben für einen Modellvergleich unverändert. Die konkreten sicheren Grenzen einer neuen Änderung sind vor ihrer Umsetzung zu prüfen.

Ein geeigneter Folgeplan würde mehrere vollständige unabhängige Normal–Änderung–Normal-Folgen vorsehen. Geometrie, Stellvorgabe, Auszeiten, Messdauer, Bewertungsabschnitt und Labels werden vorher fixiert. Die Rückkehrreferenzen prüfen, ob das Entfernen der Änderung das zuvor beobachtete Signal wiederherstellt. Die Reihenfolge und weitere Störeinflüsse sind so zu planen, dass Zustands- und Zeitunterschiede besser unterscheidbar werden. Die Anzahl der Wiederholungen folgt der gewünschten Genauigkeit auf Aufnahmeebene und nicht der bloßen Zahl verfügbarer Fenster.

Eine neue Modellversion wäre erst begründet, wenn ein vorher festgelegtes Ziel besteht, beispielsweise robustere Normalabdeckung oder höhere Empfindlichkeit für eine klar definierte Änderung. Denkbar sind zusätzliche unabhängige Entwicklungsaufnahmen, andere Achsengewichtungen oder spektrale Merkmale. Sie dürfen nicht durch Optimieren auf die hier bereits ausgewerteten Testfenster als unabhängig bestätigt gelten. Nach Änderungen sind neue, vollständig unbenutzte Testaufnahmen nötig. Training, Skalierung, Validierung und Test bleiben nach vollständigen Aufnahmen getrennt.

Die GUI bleibt eine optionale Erweiterung. Für ihre Einbindung müssten die gespeicherten Entscheidungen des validierten Datenwegs angezeigt, ungültige oder veraltete Ausgaben erkennbar gemacht und zusätzliche CPU-, RAM- und Latenzkosten unter ansonsten gleichen Bedingungen gemessen werden. Dies ist eine getrennte Software- und Messaufgabe; es ist keine Voraussetzung dafür, den bereits geprüften Betrieb ohne Oberfläche nachvollziehbar zu berichten.

# Fazit

Die Arbeit zeigt, wie ein lokaler Vergleich von RMS-Schwelle, Isolation Forest und TFLite-Autoencoder auf einem Raspberry Pi 5 nachvollziehbar umgesetzt werden kann. Die Datenkette verbindet dreiachsige Beschleunigungserfassung, Qualitätsprüfung, Fensterbildung, gespeicherte Vorverarbeitung, Entscheidung und Protokollierung. Ganze Aufnahmen wurden vor der Fensterbildung Training, Validierung oder Test zugeordnet. Das anschließend eingefrorene Paket blieb während der unabhängigen Prüfungen unverändert.

FF1 wird durch die Anforderungsanalyse, den Variantenvergleich und die dokumentierte Realisierung beantwortet. Der kleine Lüfterprüfstand ermöglicht wiederholte lokale Messungen und eine äußere Luftstromänderung. Die Auswahl des kostengünstigen ADXL345 bringt jedoch Grenzen bei Zeitbasis, Bandbreitennachweis und physikalischer Interpretation mit sich. Eine unbekannte Drehzahl oder Sensortaktabweichung wird nicht als erfüllter Nachweis behandelt.

Zu FF2 liegen vergleichbare Entscheidungen auf identischen unabhängigen Testfenstern vor. Die Methoden zeigen unterschiedliche Fehlalarme zwischen normalen Starts. Der Autoencoder erkennt die untersuchte Plattenänderung in keinem der 194 gültigen Fenster, während RMS sieben und Isolation Forest vier Fenster markieren. Die explorative Fehleranalyse erklärt diesen Befund durch die gespeicherte Achsenskalierung, geringere X- und Y-Rekonstruktionsfehler und Überschneidungen mit bekannter normaler Variation. Eine allgemein erfolgreiche Anomalieerkennung oder eine Überlegenheit des Autoencoders ist daraus nicht ableitbar. Der ursprünglich angestrebte umfassende Defektvergleich bleibt ein Teilnachweis.

FF3 wird durch getrennte Ressourcen- und Latenzmessungen im Sensorbetrieb und im zeitgetreuen Replay konkretisiert. Die Angaben in Abschnitt 7.7 beziehen sich auf definierte Prozessgrenzen, eine endliche Messdauer und das beobachtete Fensterintervall. Sie beschreiben die technische Ausführbarkeit des Datenwegs und ersetzen keine Beurteilung der fachlichen Richtigkeit seiner Entscheidungen.

FF4 ist durch einen zweiten normalen Betriebspunkt bei 50 % PWM untersucht. Das Paket wurde dafür nicht angepasst. RMS und Isolation Forest zeigen in diesen Aufnahmen geringere zusammengefasste Fehlalarmraten als in den festgelegten 75-%-Normalreferenzen; beim Autoencoder ist der Anteil geringfügig höher. Die zeitlich getrennten Reihen begründen keine allgemeine kausale Wirkung des Tastgrads. H3 wird daher nur methodenspezifisch beschrieben und nicht pauschal bestätigt.

Der wissenschaftliche Beitrag liegt in der konsistenten und überprüfbaren Umsetzung sowie in der offenen Bewertung ihrer Grenzen. Die Messungen zeigen, dass stärkere physische Vibration, ein größerer Modellscore und eine richtige Anomalieentscheidung verschiedene Sachverhalte sind. Das dokumentierte Pilotpaket bildet eine Grundlage für gezielt geplante weitere Untersuchungen. Es ist kein vollständig validiertes Defekterkennungssystem, und die nicht bestätigten Erwartungen bleiben als Ergebnisse der Arbeit erhalten.

# Anhang

## Digitale Belege und Zuordnung

Die folgenden Pfade sind relativ zur Projektwurzel masterarbeit-edge-ai angegeben. Rohdaten werden nicht in die Worddatei kopiert. Die jeweiligen maschinenlesbaren Berichte enthalten Aufnahme-IDs, Zeitstempel, Protokolle und vollständige Artefakthashes. Historische Ergebnisse wurden für diesen Abschluss nicht überschrieben.

Tabelle A-1: Verzeichnis der maßgeblichen digitalen Belege

| Kennung | Inhalt | Projektpfad |
|---|---|---|
| B1 | Eingefrorenes Modellpaket und Trainingsnachweis | results/upright_v4_training_pilot_20260911_130614/run_001/ |
| B2 | Drei unabhängige normale 75-%-Tests | results/upright_v4_independent_normal_20260911_133047/ |
| B3 | Zusätzlicher Normaltest und dokumentierter abgebrochener Plattenstart | results/upright_v4_frozen_airflow_test_20260911_164040/ |
| B4 | Vollständiger unabhängiger Test Normal → Platte → Normal | results/upright_v4_frozen_airflow_test_20260912_073015/ |
| B5 | Explorative Fehleranalyse auf identischen Modellfenstern | results/upright_v4_exploratory_diagnosis_20260912_081728/ |
| B6 | Drei unabhängige normale 50-%-Tests | results/upright_v4_second_pwm50_20260912_091000/ |
| B7 | Abschließende Sensor-/Replay-Laufzeitprüfung und Erhaltungsnachweis | results/upright_v4_finalization_20260912_103145/ |
| B8 | Vor dem Training erstellte Spektralprüfung der Entwicklungsaufnahmen | results/upright_v4_spectral_review_20260911_114502/ |

Die eindeutige Kurzkennung des eingefrorenen Pakets lautet pilot_bundle.json im Unterverzeichnis frozen von B1. Sein SHA-256-Wert ist cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5. Der vollständige Manifest- und Artefaktabgleich ist in den digitalen Belegen enthalten; die Kurzpfade der Tabelle ersetzen diese Prüfsummen nicht.

Die letzte Softwareergänzung ist versioniert in pilot_runtime_final.py, pilot_stream_final.py, pilot_recorder_final.py und run_final_runtime_evidence.py. Sie verändert weder das eingefrorene Paket noch seine vier überprüften ursprünglichen Vorverarbeitungs- und Auswertungsmodule. Die Tests und das vor dem Lauf fixierte Protokoll sind B7 zugeordnet. Die 300-s-Rohdaten des Sensorbetriebs liegen separat unter data/upright_v4_finalization_20260912_103145/runtime_evidence/.

## Lesen der Messdateien

Eine CSV-Zeile entspricht einem vollständigen XYZ-Messpunkt. Neben Beschleunigung und Label enthalten die Dateien Softwareindex, Host-Zeitstempel und Qualitätsmerkmale. Die relative Erfassungszeit ist aus der monotonen Host-Uhr abgeleitet; sample_index/200 ist lediglich eine nominelle Sensorzeit. Pro Zustand werden eigene Dateien verwendet. Der erste Messpunkt und der Stellbefehl besitzen getrennte Zeitstempel. Eine aus dem Dateinamen abgeleitete Uhrzeit ersetzt diese Angaben nicht.

Ein gültiges Modellfenster besteht aus 128 aufeinanderfolgenden XYZ-Punkten desselben Aufnahmelaufs im Abschnitt [180,300) s. Ein Rest von weniger als 128 Punkten wird als unvollständiger Rest dokumentiert. Er wird nicht zu einem normalen Fenster ergänzt. Bei erkannten Qualitätsfehlern wird keine normale Entscheidung erzeugt. Die 5-s-Diagnostik nutzt dagegen Zeitabschnitte mit einer eigenen Mittelwertentfernung je Achse und besitzt eine andere Punktzahl und Aufgabenstellung.

Das Kontrolljournal beschreibt Stellbefehle und zurückgelesene Einstellungen. Sichtbestätigungen sind Nutzerbeobachtungen und werden nicht durch Softwarewerte ersetzt. Für unbeaufsichtigt freigegebene spätere Serien werden nicht vorhandene neue mechanische Beobachtungen nicht erfunden. Insbesondere bedeutet die zuletzt zurückgelesene Vorgabe 0 % nicht automatisch einen dokumentierten vollständigen mechanischen Stillstand.

# Literaturverzeichnis

Analog Devices (2022). ADXL345: 3-Axis, ±2 g/±4 g/±8 g/±16 g Digital Accelerometer. Datenblatt, Revision G, Mai 2022. https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf (Abruf: 12.09.2026.)

Analog Devices (2025). ADXL354/ADXL355: Low Noise, Low Drift, Low Power, 3-Axis MEMS Accelerometers. Datenblatt, Revision D, Juni 2025. https://www.analog.com/media/en/technical-documentation/data-sheets/adxl354_adxl355.pdf (Abruf: 12.09.2026.)

Antonini, M., Pincheira, M., Vecchio, M., & Antonelli, F. (2023). An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Industrial Environments. Sensors, 23(4), 2344. https://doi.org/10.3390/s23042344 (Abruf: 12.09.2026.)

ARCTIC (o. J.). Specifications: P12 Pro PST. Technisches Datenblatt. https://www.arctic.de/media/2c/de/c6/1750758983/Spec_Sheet_P12_Pro_PST_EN.pdf (Abruf: 12.09.2026.)

Buttazzo, G. C. (2011). Hard Real-Time Computing Systems: Predictable Scheduling Algorithms and Applications (3. Aufl.). Springer. https://doi.org/10.1007/978-1-4614-0676-1 (Abruf: 12.09.2026.)

Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly Detection: A Survey. ACM Computing Surveys, 41(3), Artikel 15, 1–58. https://doi.org/10.1145/1541880.1541882 (Abruf: 12.09.2026.)

Department for Communities and Local Government (2009). Multi-criteria analysis: a manual. London. ISBN 978-1-4098-1023-0. https://www.gov.uk/government/publications/multi-criteria-analysis-manual-for-making-government-policy (Abruf: 12.09.2026.)

Garay, C. E., Miranda Bonomi, F. A., Mansilla, G. N., Fagre, M., Guzmán, S. G., Ritorto, P. A., Perez, F. I., & Katz, M. (2026). A Multimodal TinyML-Based Predictive Maintenance Architecture for Industrial IoT in the 6G Era. Sensors, 26(14), 4536. https://doi.org/10.3390/s26144536 (Abruf: 12.09.2026.)

Goodfellow, I., Bengio, Y., & Courville, A. (2016). Deep Learning. MIT Press. Insbesondere Kapitel 14: Autoencoders. https://www.deeplearningbook.org/ (Abruf: 12.09.2026.)

Google (2026a). Convert TensorFlow models. LiteRT-Dokumentation, Stand 28.05.2026. https://developers.google.com/edge/litert/conversion/tensorflow/convert_tf (Abruf: 12.09.2026.)

Google (2026b). Post-training quantization. LiteRT-Dokumentation, konsultierte Fassung 2026. https://developers.google.com/edge/litert/conversion/tensorflow/quantization/post_training_quantization (Abruf: 12.09.2026.)

Google (2026c). Quickstart for Linux-based devices with Python. LiteRT-Dokumentation, konsultierte Fassung 2026. https://developers.google.com/edge/litert/microcontrollers/python https://developers.google.com/edge/api/tflite/python/tf/lite/Interpreter (Abruf: 12.09.2026.)

Google (2026d). Install TensorFlow with pip. TensorFlow-Dokumentation, konsultierte Fassung 2026. https://www.tensorflow.org/install/pip (Abruf: 12.09.2026.)

Jardine, A. K. S., Lin, D., & Banjevic, D. (2006). A review on machinery diagnostics and prognostics implementing condition-based maintenance. Mechanical Systems and Signal Processing, 20(7), 1483–1510. https://doi.org/10.1016/j.ymssp.2005.09.012 (Abruf: 12.09.2026.)

Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining: Formulation, detection, and avoidance. ACM Transactions on Knowledge Discovery from Data, 6(4), Artikel 15. https://doi.org/10.1145/2382577.2382579 (Abruf: 12.09.2026.)

Knap, P., Jachymczyk, U., & Lalik, K. (2026). Leakage-Safe, Reproducible Benchmarking for Vibration-Based Fault Diagnosis. PHM Society European Conference, 9(1), 1–8. https://doi.org/10.36001/phme.2026.v9i1.4924 (Abruf: 12.09.2026.)

Lessmeier, C., Kimotho, J. K., Zimmer, D., & Sextro, W. (2016). Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification. European Conference of the Prognostics and Health Management Society. https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf (Abruf: 12.09.2026.)

Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation Forest. Proceedings of the Eighth IEEE International Conference on Data Mining, 413–422. https://doi.org/10.1109/ICDM.2008.17 (Abruf: 12.09.2026.)

NASA (2023). 6.8 Decision Analysis. Webfassung des NASA Systems Engineering Handbook. https://www.nasa.gov/reference/6-8-decision-analysis/ (Abruf: 12.09.2026.)

NVIDIA (o. J.). Jetson Orin Nano Super Developer Kit. Technische Spezifikationen. https://www.nvidia.com/de-de/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/ (Abruf: 12.09.2026.)

ONNX Runtime developers (o. J.). Python. ONNX Runtime-Dokumentation zur Installation und Ausführung. https://onnxruntime.ai/docs/get-started/with-python.html (Abruf: 12.09.2026.)

Oriental Motor (o. J.). Servo Motor Features Overview. https://www.orientalmotor.com/servo-motors/technology/servo-motor-features.html (Abruf: 12.09.2026.)

PCB Piezotronics (o. J.). Model 356A32: Triaxial Accelerometer. Technische Spezifikationen. https://www.pcb.com/products?m=356a32 (Abruf: 12.09.2026.)

Pittino, F., Puggl, M., Moldaschl, T., & Hirschl, C. (2020). Automatic Anomaly Detection on In-Production Manufacturing Machines Using Statistical Learning Methods. Sensors, 20(8), 2344. https://doi.org/10.3390/s20082344 (Abruf: 12.09.2026.)

PyTorch (o. J.). ExecuTorch Documentation. Dokumentation zum Modellexport und zur lokalen Ausführung. https://docs.pytorch.org/executorch/stable/index.html (Abruf: 12.09.2026.)

Randall, R. B., & Antoni, J. (2011). Rolling element bearing diagnostics—A tutorial. Mechanical Systems and Signal Processing, 25(2), 485–520. https://doi.org/10.1016/j.ymssp.2010.07.017 (Abruf: 12.09.2026.)

Raspberry Pi Ltd. (o. J.). Raspberry Pi 5. Produktbeschreibung und technische Spezifikationen. https://www.raspberrypi.com/products/raspberry-pi-5/ https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf (Abruf: 12.09.2026.)

Raspberry Pi Ltd. (2026). Raspberry Pi 4 Model B. Product Brief, April 2026. https://pip-assets.raspberrypi.com/categories/545-raspberry-pi-4-model-b/documents/RP-008344-DS-1-raspberry-pi-4-product-brief (Abruf: 12.09.2026.)

Ren, H., Anicic, D., & Runkler, T. A. (2021). TinyOL: TinyML with Online-Learning on Microcontrollers. International Joint Conference on Neural Networks, 1–8. https://doi.org/10.1109/IJCNN52387.2021.9533927 (Abruf: 12.09.2026.)

Ruff, L., Kauffmann, J. R., Vandermeulen, R. A., Montavon, G., Samek, W., Kloft, M., Dietterich, T. G., & Müller, K.-R. (2021). A Unifying Review of Deep and Shallow Anomaly Detection. Proceedings of the IEEE, 109(5), 756–795. https://doi.org/10.1109/JPROC.2021.3052449 (Abruf: 12.09.2026.)

scikit-learn developers (o. J. a). Common pitfalls and recommended practices. Benutzerhandbuch. https://scikit-learn.org/stable/common_pitfalls.html (Abruf: 12.09.2026.)

scikit-learn developers (o. J. b). Cross-validation: evaluating estimator performance. Insbesondere Aufteilung gruppierter Daten. https://scikit-learn.org/stable/modules/cross_validation.html (Abruf: 12.09.2026.)

scikit-learn developers (o. J. c). Metrics and scoring: quantifying the quality of predictions. https://scikit-learn.org/stable/modules/model_evaluation.html (Abruf: 12.09.2026.)

scikit-learn developers (o. J. d). IsolationForest. API-Dokumentation. https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html (Abruf: 12.09.2026.)

SciPy developers (o. J. a). Discrete Fourier Transforms (scipy.fft). SciPy-Benutzerhandbuch. https://docs.scipy.org/doc/scipy/tutorial/fft.html (Abruf: 12.09.2026.)

SciPy developers (o. J. b). Signal Processing (scipy.signal), Abschnitt Spectral Analysis. SciPy-Benutzerhandbuch. https://docs.scipy.org/doc/scipy/tutorial/signal.html#spectral-analysis (Abruf: 12.09.2026.)

Shi, W., Cao, J., Zhang, Q., Li, Y., & Xu, L. (2016). Edge Computing: Vision and Challenges. IEEE Internet of Things Journal, 3(5), 637–646. https://doi.org/10.1109/JIOT.2016.2579198 (Abruf: 12.09.2026.)

STMicroelectronics (2026). Migrating applications from STM32F7 to STM32H743/H753 MCUs. Application Note AN4936, Fassung vom 09.01.2026. https://www.st.com/resource/en/application_note/an4936-migrating-applications-from-stm32f7-to-stm32h743h753-mcus-stmicroelectronics.pdf https://www.st.com/en/microcontrollers-microprocessors/stm32h743-753.html (Abruf: 12.09.2026.)

Universität Paderborn, Lehrstuhl Konstruktions- und Antriebstechnik (o. J.). Bearing Data Center. Beschreibung des Lagerprüfstands und des Datensatzes. https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter (Abruf: 12.09.2026.)
