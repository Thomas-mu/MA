# Durchführungsnachtrag: Handyvibration

Datum: 19.09.2026. Zeitstempel der Originaldateien in UTC; lokale Zeitzone Europe/Berlin (UTC+2).
Messung ohne Live-GUI, jeweils eine Methode aktiv, nominal 200 Hz, 128 Samples je Fenster,
20 Warmup-Fenster, Schwellen und Modelle während der Versuche unverändert.
Lüfter-PWM vor und nach den ausgewählten Aufnahmen: 75 % (keine Drehzahlmessung).

## Vollständige Versuchshistorie

| Lauf | Fenster | Alarmfenster | Ungültig | Verwendung |
| --- | ---: | ---: | ---: | --- |
| Autoencoder 01 | 170 | 30 | 0 | Nutzer bat um Wiederholung wegen möglicherweise zu frühen Anrufs |
| Autoencoder 02 | 158 | 12 | 1 | Nutzer bat erneut um Wiederholung wegen zu frühen Anrufs |
| Autoencoder 03 | 184 | 11 | 0 | Ausgewählter explorativer Anrufversuch |
| Isolation Forest 01 | 154 | 7 | 0 | Nutzer bat um Neustart; keine Anruf-Freigabe protokolliert |
| Isolation Forest 02 | 196 | 6 | 0 | Ausgewählter explorativer Anrufversuch |
| RMS 01 | 234 | 6 | 0 | Ausgewählter explorativer Anrufversuch |

Die Wiederholungen sind keine nachträgliche Löschung unerwünschter Messwerte: alle Originaldaten und
die Begründung der Auswahl bleiben erhalten. Frühere Alarme sind nicht automatisch als echte Fehler oder
Fehlalarme etikettiert. Eine Fehlalarmrate darf nicht aus den ausgewählten ruhigen Vorläufen abgeleitet werden.

## Zeitmarken der ausgewählten Läufe

| Methode | Operator-Freigabe (UTC) | Nutzer-Rückmeldung (UTC) |
| --- | --- | --- |
| Autoencoder | 10:28:32.708535 | 10:29:05.585407 |
| Isolation Forest | 10:37:31.057067 | 10:38:07.879046 |
| RMS | 10:40:30.709127 | 10:41:38.645921 |

Diese Zeitmarken wurden im laufenden Versuch geschrieben. Sie messen **nicht** den tatsächlichen
physischen Beginn bzw. das Ende der Handyvibration. Die tatsächliche Dauer der Vibration wurde nicht verifiziert.
Vor der Freigabe wurden mindestens 30 Sekunden aufgezeichnet, nach Rückmeldung mindestens 15 Sekunden.
Die Aufnahmeprozesse wurden anschließend geordnet beendet; vollständige Rohdaten wurden gespeichert.

## Qualität und Auswertung

Die drei ausgewählten Läufe enthalten insgesamt 614 gültige vollständige Fenster und 78.843 Rohsamples.
251 Rohsamples gehören zu unvollständigen Schlussfenstern und werden nicht klassifiziert.
Keine verworfenen Fenster und keine gemeldeten Sensorlücken, Überläufe oder Sättigungen in diesen Läufen.
Digitale Integritätsprüfungen ersetzen keine unabhängige Kalibrierung der Messkette.

Pro Lauf: CSV-Rohdaten/Entscheidungen, JSON-Metadaten/Marker, Interpretationsnotiz,
vierteilige Diagramme als PNG/PDF und tatsächlicher Browser-Screenshot mit Nachweisen.
Grafiken wurden erst nach Ende der betreffenden Aufnahme erzeugt.

Das Offline-Replay verwendet dieselben Fenstergrenzen für alle Methoden und exakt dieselben Rohwerte.
Die ursprünglichen 614 Live-Vorhersagen und ihre Scores wurden ohne Abweichung reproduziert.
Erste Alarmfenster: Aufnahme A jeweils 97; B Autoencoder 93, IF/RMS 94; C jeweils 155.
Die Auswertung dokumentiert Gleichstände und zählt Alarmfenster nicht als unabhängige Störungsereignisse.

## Präsentation und Prüfung

Zehn Ergebnisfolien in `presentation_v2_results/`, mit Quellen und Sprechernotizen.
PowerPoint, PDF, Diagramme und drei Screenshots sind archiviert; alle Folien wurden visuell geprüft.
Fünf fokussierte Tests für Markierungen, fehlende physische Ground Truth, Rohfenster-Zuordnung,
Abschnittsgrenzen und Gleichstands-Rangfolge bestanden.
Dateiprüfsummen, Fensterzahlen und PowerPoint-Struktur wurden zusätzlich geprüft.

Originalplanung und Vorbereitungspräsentation bleiben unverändert; dieser Nachtrag beschreibt die Durchführung.
Es wurden keine echten Lüfterdefekte nachgewiesen, keine allgemeine Erkennungsrate bestimmt und keine
elektrische Leistungsaufnahme gemessen. Finale Handyaufstellung und Normalkalibrierung bleiben offen.

## Nachtrag: zusätzlicher gemeinsamer Live-Anruf

Auf Nutzerwunsch wurden alle drei Methoden gleichzeitig auf einem Sensorstream ausgeführt.
Jedes vollständige Fenster wurde identisch an drei Worker-Threads übergeben; eine Barriere gibt diese gemeinsam frei.
Gleiche Rohwerte, Fenstergrenzen und Dispatch-Zeitstempel wurden anhand der gespeicherten Daten überprüft.
Die Barriere garantiert keinen exakt gleichen CPU-Startzeitpunkt; Scheduler und Berechnungsdauer wirken auf die Ausgabezeiten.

Lauf: `joint_trials/all_methods_01`. Freigabe am 19.09.2026 um 11:39:35.147659 UTC,
Ende-Rückmeldung um 11:40:24.451055 UTC; sauber beendet um 11:40:49.124936 UTC.
Beide Chat-Zeitmarken sind keine unabhängig gemessenen physischen Vibrationszeitpunkte.

| Methode | Erstes Alarmfenster | Fensterrang | Ausgaberang | Abstand zur frühesten Alarmentscheidung | Alarmfenster |
| --- | ---: | ---: | ---: | ---: | ---: |
| Autoencoder | 108 | 1 | 1 | 0 ms | 11 |
| Isolation Forest | 108 | 1 | 2 | 19,061107 ms | 7 |
| RMS | 109 | 2 | 3 | 615,658777 ms | 6 |

197 gemeinsame Fenster, 591 gültige Entscheidungen, 25.270 Rohsamples (54 davon im unvollständigen Schlussfenster).
Keine verworfenen Fenster, Sensorlücken, Überläufe oder Sättigungen gemeldet.
77 Fenster vollständig vor Freigabe und 39 nach Rückmeldung: bei allen Methoden keine Alarme.
79 Fenster vollständig zwischen den Chat-Markierungen; zwei grenzüberlappende Fenster ohne Alarm.
Alle 591 Entscheidungen und die Rohfensterhashes wurden geprüft; maximale Score-Abweichung beim Nachrechnen 0.

Median der gesamten Prozess-CPU: 13,04 % eines Kerns; maximale abgetastete RSS: 174,42 MiB.
Diese Werte gelten für den gesamten gemeinsamen Prozess, nicht für jeweils ein Modell.
Schwellen und PWM blieben unverändert. Ein einzelner gemeinsamer Anruf erlaubt keine allgemeine Gewinner-Rangfolge.

`presentation_v3_joint/` ergänzt die zehn früheren Ergebnisfolien um vier Folien des gemeinsamen Anrufs.
Die früheren Präsentationen bleiben unverändert. Protokoll, Diagramme, echter Browser-Screenshot,
Quellen- und Artefakthashes sind archiviert; acht fokussierte Tests bestanden.
