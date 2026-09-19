# Erläuterungen zur Präsentation

Stand: Vorbereitung; ausschließlich abgeschlossene Techniktests, keine Anrufversuchsergebnisse.

## Folie 1: Wie früh erkennen drei Methoden eine Vibration?

Diese Fassung verwendet ausschließlich die abgeschlossenen technischen Kurztests vom 19.09.2026. Reale Anrufversuche wurden inzwischen begonnen; diese separate Vorbereitungsfassung wertet sie nicht aus. Sie enthält keine Resultate eines Handy-Anrufversuchs. Eine externe Handyvibration ist eine gezielt eingebrachte Störung, kein Nachweis eines echten Lüfterdefekts. Quellen: plan.json; protocol.md; technical_checks/*/run.json. Der gewählte Betriebspunkt beträgt 75 % PWM, nicht gemessene Drehzahl.

## Folie 2: Ein Anruf pro Methode: zunächst ein Pilotversuch

Plan: ein Anruf je Methode, insgesamt drei Anrufe. Vorlauf mindestens 30 s, Zielvibration etwa 5 s, anschließend mindestens 15 s Ruhe. Anrufsignal und Benutzerbestätigung werden separat protokolliert. Die tatsächliche Vibration kann später beginnen und anders lang dauern. Telefonposition, Befestigung, Vibrationsmuster und Klingelton aus sind vorab zu dokumentieren. Ein Ereignis pro Methode erlaubt keine belastbare allgemeine Erkennungsrate. Für exakt identische Eingaben ist Replay notwendig.

## Folie 3: Gemeinsame Messkette, eine aktive Methode

Die Pipeline verwendet den ADXL345 im FIFO-Betrieb. Fenstergröße und Schrittweite betragen 128. Die nominale Periode ist 128/200 = 0,64 s; Host-Lesezeitstempel sind keine direkt gemessenen Sensor-Abtastzeitpunkte. Standardisierung erfolgt mit den eingefrorenen Trainingsparametern. Im Live-Einzelbetrieb wird eine Methode ausgeführt. Das Beispiel unten zeigt echte Rohdaten des abgeschlossenen Autoencoder-Techniktests, ohne Anruf. Rohdatenquelle: sources/technical_checks/autoencoder/raw.csv. Keine Störung in diesem Bild behauptet.

## Folie 4: Eigene Scores, eigene Schwellenwerte

Die Standardisierung erfolgt achsweise. Autoencoder: mittlere quadratische Abweichung zwischen Eingabe und Rekonstruktion über 384 Werte. Isolation Forest: negatives score_samples auf dem flachgelegten standardisierten Fenster. RMS: Wurzel des mittleren Quadrats des standardisierten Fensters. P99 bedeutet 99. Perzentil der normalen Validierungsscores, nicht 99 % Genauigkeit. Der AE-Schwellwert ist aus der eingefrorenen Keras-Kalibrierung übernommen, die anderen aus dem Vergleichsbündel. Es gibt 97 Validierungsfenster; die AE-Validierung wurde zusätzlich zur Trainingsüberwachung/Early Stopping verwendet, kein eigener dritter Kalibrierungssplit. Quelle: bundle/bundle.json, plan.json und archivierte Vergleichsimplementierung.

## Folie 5: Zwölf Fenster verarbeitet, kein Alarm

Jedes Teilbild zeigt einen anderen technischen Test. Für bessere Lesbarkeit sind Scores durch die jeweils eigene positive Schwelle geteilt. Der Wert 1 markiert diese Schwelle. Die Division liefert keine kalibrierte Wahrscheinlichkeit und erlaubt keine Aussage über gleiche Sensitivität. Alle 12 vollständigen Fenster sind gültig und als normal klassifiziert. Das belegt die Funktionsfähigkeit der Pipeline in diesen kurzen Aufnahmen, keine getestete Fehlererkennung oder Fehlalarmrate. Quellen: technical_checks/*/decisions.csv und summary.json.

## Folie 6: Berechnung und Prozesslast im Techniktest

processing_ms misst laut archiviertem Erfassungscode Standardisierung plus Scoreberechnung und Klassifikation nach Entnahme des Fensters. Es ist weder reine Modell-Inferenz noch physische Fehlererkennungsverzögerung. CPU und RAM gelten für den gesamten Einzelprozess einschließlich Sensorerfassung und Logging. CPU 100 % entspricht einem Kern. RAM sind abgetastete RSS-Werte während des Laufs, nicht der Gesamtstart-Peak. Die technischen Tests wurden nacheinander und teils mit unterschiedlichen Codeversionen durchgeführt; vier Fenster sind kein seriöser Benchmark. Keine Rangfolge der Methodenqualität aus dieser Folie ziehen. Quellen: decisions.csv; run.json.

## Folie 7: Anrufsignal und Vibrationsbeginn unterscheiden

Cue-Zeitstempel dokumentieren die Interaktion, nicht den Vibrationsmotor des Telefons. Ein erster Alarm relativ zu einer Aufforderung wäre nur ein deskriptiver Cue-Abstand. Physischer Beginn und Ende müssen separat markiert oder gemessen werden; eine nachträgliche Schätzung aus demselben Signal ist als Schätzung zu kennzeichnen. Beim Replay derselben Aufnahme kann man bereits das erste Alarmfenster vergleichen, ohne exakte echte Latenz zu behaupten. Gleiches Fenster bedeutet Gleichstand auf Fensterauflösung. Anrufverzögerung und Fenstertakt dürfen nicht als Modellzeit fehlinterpretiert werden.

## Folie 8: Echter Screenshot eines lokalen Evidenzberichts

Der abgebildete Screenshot wurde tatsächlich mit Chromium aus evidence_report.html aufgenommen. Er zeigt nur den hier erzeugten lokalen Bericht; weder Desktop noch private Anwendungen wurden aufgenommen. Rohdaten und Metadaten liegen als eingefrorene Kopien im sources-Verzeichnis. source_manifest.json enthält SHA-256-Hashes; browser_capture.json dokumentiert Zeitpunkt, Quelle und Screenshot-Hash. Die übrigen Diagramme sind aus CSV erzeugte Exporte und werden nicht als Screenshots bezeichnet. Ein Foto der physischen Handyposition ist weiterhin nicht vorhanden.

## Folie 9: Technisch vorbereitet; Nachweise bleiben offen

Die Kalibrierungsdaten stammen aus dem bisherigen Standlaufprofil bei 75 % PWM. Ein angebrachtes Handy verändert möglicherweise die mechanische Ankopplung; der endgültige Aufbau ist noch nicht bestätigt. Das Bundle trägt measurement_chain_status=unverified_legacy, weshalb hier kein abschließend validiertes Messsystem behauptet wird. Normaldaten für Aufbaukontrolle und ggf. neue Kalibrierung sind vor den bewerteten Tests notwendig. Ein einziger Anruf pro Methode ist ein Pilot, kein Zuverlässigkeitsnachweis. Externe Tischvibrationen sind keine echten Lüfterdefekte.

## Folie 10: Vom Probelauf zur auswertbaren Versuchsreihe

Als nächstes Aufbau dokumentieren und Normalzustand prüfen. Bei verändertem mechanischem Aufbau neue Normaldaten aufnehmen und Kalibrierung erneuern. Dann jeden Einzelprozess separat aufnehmen, Aufforderung, Anrufbestätigung und Ende protokollieren, Rohdaten und Fehler erhalten. Tatsächliche physische Zeitreferenz ist für Latenz nötig. Danach gleiche Aufnahme für alle Methoden auswerten. Ressourcenbenchmark separat mit fester Umgebung, Aufwärmphase, ausreichend langer Laufzeit und Wiederholungen durchführen. Ergebnisse der Pilotversuche werden in einer neuen Präsentationsversion ergänzt; diese Version bleibt als Vorbereitungsevidenz unverändert.

