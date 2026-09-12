# Vorab festgelegtes Protokoll: unabhängige Normalitätsprüfung v4

Dieses Protokoll wurde vor der ersten neuen Aufnahme festgeschrieben. Seine maschinenlesbare Fassung ist [protocol.json](protocol.json); [protocol.sha256](protocol.sha256) verankert ihren Inhalt. Freigaben, Sitzungen und spätere Ergebnisse werden als separate Dateien ergänzt. Die beim Festschreiben noch fehlende erste Bereitschaft wird dadurch nicht rückwirkend als bereits vorhanden dargestellt.

## Festes Modellpaket

Ausschließlich [das erfolgreich trainierte v4-Pilotpaket](../upright_v4_training_pilot_20260911_130614/run_001/frozen/pilot_bundle.json) wird verwendet. SHA256: `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`. Fest bleiben Autoencoder/TFLite, Isolation Forest, StandardScaler und die Schwellen RMS 1,2747695377144315, IF 0,5045395247064507 und AE 0,544357966122261. Keine Trainings- oder Schwellenfunktion wird für die Testauswertung aufgerufen.

Die 246 bereits vorhandenen CSV-Dateien werden mit Pfaden, SHA256 und Aufnahme-ID/Stammnamen ausgeschlossen. Dazu gehören sämtliche Trainings-/Validierungsquellen und bereits untersuchte Pilotaufnahmen. Neue Testdateien müssen zum neuen Protokoll gehören und zeitlich nach seiner Festschreibung sowie nach der jeweiligen Benutzerfreigabe aufgenommen sein. Jede Quelle darf nur einmal in die gemeinsame Auswertung eingehen.

## Drei neue unabhängige Starts

| Lauf | Zustand / Label | PWM | Aufnahme | Modellbewertung |
|---|---|---|---|---|
| `normal_test_01` | ohne Platte, normal / 0 | 75 % bei 25 kHz | 300 s, gesamter Anlauf | [180,300) s |
| `normal_test_02` | ohne Platte, normal / 0 | 75 % bei 25 kHz | 300 s, gesamter Anlauf | [180,300) s |
| `normal_test_03` | ohne Platte, normal / 0 | 75 % bei 25 kHz | 300 s, gesamter Anlauf | [180,300) s |

Aufbau: `fan_upright_position_v4_20260911_103726`. Die vorher bestätigte sichere aufrechte Stellung und Sensorbefestigung mit zwei Schrauben am feststehenden Rahmen werden übernommen. Es wird kein Umbau verlangt. Lüfterposition, Sensorposition und Befestigung bleiben unverändert; keine Platte ist eingesetzt.

Vor Start 1 fehlen ausschließlich aktuelle Bereitschaft, vollständiger mechanischer Stillstand und angeschlossene externe 12-V-Versorgung. Nach der Freigabe bleibt die Vorgabe weitere 60 Sekunden auf 0 %. Anschließend stellt die Software einmalig 75 % ein und ruft die vorhandene Aufzeichnung möglichst unmittelbar auf. Tatsächlicher Stellbefehlsbeginn, Befehlsabschluss und erster XYZ-Punkt werden getrennt gespeichert. Keine Antwort ist während der Aufnahme erforderlich.

Nach jedem Lauf stellt die Software 0 % ein und liest PWM-Konfiguration und Pin-Funktion zurück. Die nächste Phase beginnt erst nach einer neuen Nachricht des Nutzers: **„Lüfter steht, nächster Lauf freigegeben“**. Dann folgen wieder mindestens 60 Sekunden zusätzliche Auszeit ab erfasster Freigabe. Es gibt keine Antwortfrist, keine wiederholte Nachfrage zum Lauf und keine automatischen Wiederholungsstarts.

Die zusätzliche Auszeit und die gesamte Zeit zwischen dem vorherigen 0-%-Stellbefehl und dem nächsten 75-%-Stellbefehl werden getrennt angegeben. Für den ersten Lauf ist die gesamte vorherige Auszeit unbekannt. Der exakte mechanische Stillstandszeitpunkt wird nicht aus PWM abgeleitet. Die gesamten Auszeiten müssen wegen der manuellen Freigaben nicht identisch sein.

Rohdateien erhalten eindeutige Namen `normal_test_XX_75pwm_300s_<UTC-Zeitstempel>.csv` unter dem neuen Datenverzeichnis. Sidecar, Sitzung, Freigabe und Steuerjournal bleiben separat erhalten. Vorhandene Dateinamen und bereits versuchte Phasen werden nicht wiederverwendet.

## Sensor und Vorverarbeitung

Bestehende Konfiguration: ADXL345, I²C-Bus 1 bei konfigurierten 100 kHz, nominell 200 Hz, ±2 g, Full Resolution, FIFO-Stream, 0,0039 g/LSB. Die Register werden mit dem vorhandenen Treiber kontrolliert. Gemessene Drehzahl bleibt unbekannt; GPIO18 ist der PWM-Steueranschluss, physischer Pin 12.

Zeitnullpunkt ist der Aufrufbeginn des 75-%-Stellbefehls in Host-Monotonzeit. Auswahl mit ganzzahligen Nanosekunden: 180 Sekunden eingeschlossen, 300 Sekunden ausgeschlossen. Je Fenster 128 vollständige XYZ-Messpunkte, Schritt 128, keine Überlappung, kein Zusammenfügen über Aufnahmegrenzen und kein Auffüllen von Resten.

Jede Achse wird je Fenster mit ursprünglichen Float64-Werten zentriert. Anschließend erfolgt Float32-Konvertierung und Anwendung des unveränderten gespeicherten Scalers. Die numerische Anordnung der Werte wird wie im Trainingsweg beibehalten. Alle drei Methoden erhalten dieselben standardisierten Werte. Die Softwareprüfung reproduziert dafür exakt die gespeicherten Eingaben des echten Trainings für 388 Trainings- und 194 Validierungsfenster; diese Quellen werden dadurch keine Testdaten.

## Qualitätsregeln und Auswertung

Die originale CSV wird vollständig auf Quelle, Label, Sensorwerte, Zeitbasis, fortlaufende Indizes und Journalzuordnung geprüft. Vollständige Aufnahme: mindestens 299,8 s zwischen erstem und letztem Hostzeitstempel; erster XYZ-Punkt weniger als eine Sekunde nach Stellbefehl. Nominelle 200 Hz und beobachteter Durchsatz `(N−1)/Hostzeitspanne` werden getrennt berichtet. Host-Leseabstände einschließlich Häufigkeit über 10 ms werden dokumentiert; sie sind keine direkten Sensorkonversionszeiten.

Ein betroffenes 128er-Fenster ist für alle Methoden ungültig bei Lücken-, Überlauf- oder Sättigungsflag, FIFO-Füllstand 32, Hostabstand über 160 ms, Sättigungswert am Sensorbereich oder nichtendlichen XYZ-Werten. Es bleibt in den Ergebniszählungen erhalten und wird nicht NORMAL. Die 160-ms-Grenze entspricht der bestehenden nominellen FIFO-Kapazitätswarnung. Fehlende Flags beweisen keine exakt verlustfreie Sensorkonversion; genaue physische Verluste bleiben unbekannt.

Strukturell unzuverlässige Aufnahmen, etwa mit nicht monotoner Zeitbasis, falscher Herkunft oder inkonsistenten Journaldaten, werden ausdrücklich als nicht auswertbar protokolliert. Sie werden nicht stillschweigend ersetzt oder als erfolgreicher Normallauf gezählt. Rohdaten und Fehlerbeleg bleiben erhalten.

Berichtet werden pro Methode und vollständigem Lauf: gültige und ungültige Fenster, Fehlalarme und **Fehlalarmrate = Fehlalarme / gültige normale Fenster**. Bei keinem gültigen Fenster ist die Rate nicht definiert. Die gemeinsame Tabelle enthält außerdem zusammengefasste deskriptive Fensterzahlen. Benachbarte Fenster sind keine unabhängigen Versuchsreplikate. Scoreverläufe werden mit den unveränderten Schwellen dargestellt.

Aus diesen ausschließlich normalen Tests werden kein Anomalie-Recall, kein F1-Wert und keine allgemeine Erkennungsleistung abgeleitet. Hohe Fehlalarmraten bleiben erhalten. Die 180-s-Einlaufzeit bleibt ein Prüfkandidat; ihre Auswahl wird nicht nach Betrachtung der Testergebnisse verändert.

## Fehler und Abschluss

Die neue Steuerung enthält genau einen freigegebenen Start pro Prozess. Bei Erfassungsfehlern oder Abbruch wird nach Möglichkeit 0 % gesetzt und zurückgelesen. Falls dies nicht bestätigt werden kann, wird der tatsächlich auslesbare Zustand berichtet; es wird kein Stillstand behauptet. Bereits vorhandene Sitzungs-/Steuerjournalmarker verhindern einen automatischen neuen Versuch.

Nach Lauf 3 bleibt die Vorgabe auf 0 %. Anschließend werden der separate Vergleichsbericht, Tabelle, Grafik und eine Empfehlung für einen kontrolliert veränderten Zustand erstellt. Es werden weder eine Platte eingesetzt noch weitere PWM-Punkte gestartet. Spätere Modell- oder Schwellenänderungen erfordern eine neue Version und neue unabhängige Tests. Worddatei, ursprüngliche Messdaten, historische Berichte und bestehende Modelle bleiben unverändert.
