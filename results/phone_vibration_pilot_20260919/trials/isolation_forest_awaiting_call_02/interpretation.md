# Isolation Forest: explorativer Anrufversuch 02

Dieser Lauf ersetzt Versuch 01, dessen Anrufkoordination unklar war. Alle Originaldaten bleiben erhalten.
Der Schwellenwert wurde unverändert aus dem eingefrorenen Bündel übernommen: 0,4833547401595273.
PWM vor und nach der Aufnahme: 75 %.

## Beobachtungen

196 vollständige Fenster, 25.170 Rohsamples und 82 gespeicherte Samples eines unvollständigen Schlussfensters.
Keine ungültigen oder verworfenen Fenster, keine erkannten Sensorlücken, Überläufe oder Sättigungen.

| Abschnitt anhand der Operator-/Chat-Markierungen | Fenster | Alarmfenster | Maximaler Score |
| --- | ---: | ---: | ---: |
| Vollständig vor Anruf-Freigabe | 76 | 0 | 0,383693 |
| Vollständig zwischen Freigabe und Rückmeldung | 59 | 6 | 0,577300 |
| Vollständig nach Rückmeldung | 59 | 0 | 0,383001 |

Zwei Fenster überlappen Abschnittsgrenzen und sind in dieser Tabelle ausgeschlossen, aber in den Rohdaten und Gesamtsummen enthalten.
Freigabe: 47,492907006 s; Rückmeldung: 84,314888855 s nach Aufnahmestart.
Die sechs Alarmfenster liegen zwischen 58,079740 und 66,117840 s nach Aufnahmestart.

## Aussagegrenzen

Die Freigabe und die Rückmeldung sind keine Messungen des physischen Vibrationsbeginns oder -endes.
Die Differenz zwischen Freigabe und erstem Alarm ist deshalb keine Fehler-Erkennungsverzögerung.
Sechs Alarmfenster sind keine sechs unabhängigen Anrufversuche; es ist ein einzelner Anrufversuch.
Aus einem Anruf lässt sich weder eine allgemeine Erkennungsquote noch ein Geschwindigkeitsvorteil gegenüber anderen Methoden ableiten.
Die separat aufgenommenen Methoden erhielten keine nachweislich identischen Vibrationssignale.
Eine spätere Wiedergabe derselben Rohaufnahme kann identische Eingabedaten herstellen, aber keinen fehlenden unabhängigen Fehlerbeginn nachträglich messen.
Der endgültige Handyaufbau ist im eingefrorenen Plan noch nicht bestätigt; die Aufnahme bleibt ein explorativer Pilot.

CPU/RAM umfassen den Erfassungs- und Auswertungsprozess inklusive Logging. Die gemessene Berechnungszeit ist nicht die Fehler-Erkennungsverzögerung.
Diagramme und Browser-Screenshot werden nach der Aufnahme erstellt; es handelt sich nicht um eine Live-GUI oder ein Foto des Aufbaus.
