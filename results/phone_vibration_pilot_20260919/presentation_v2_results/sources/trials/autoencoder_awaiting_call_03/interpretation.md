# Autoencoder: dritter Durchgang nach zwei vorzeitig ausgelösten Anrufen

Explorativer Anruf-Pilot mit dem bestehenden 75-%-Profil. Dieser Durchgang
ersetzt für die deskriptive Darstellung die Läufe 01 und 02; deren Rohdaten
bleiben erhalten. Eine Freigabe als abschließender wissenschaftlicher Test
oder eine neue Kalibrierung des Handyaufbaus ist damit nicht verbunden.

## Beobachtungen aus Rohprotokoll und Entscheidungen

- 184 vollständige Fenster, 23.617 gespeicherte Rohsamples.
- Keine ungültigen oder verworfenen Fenster; keine erfassten Gap-, Overrun-
  oder Sättigungsflags. 65 restliche Samples im Rohprotokoll erhalten.
- Operator-Freigabemarkierung bei 51,648510 s seit Aufnahmestart.
- Rückmeldung „fertig“ bei 84,525371 s seit Aufnahmestart.

| Durch Chat-Markierungen definierter Abschnitt | Vollständige Fenster | Alarmfenster | Höchster MSE |
| --- | ---: | ---: | ---: |
| Vor Freigabe | 83 | 0 | 0,207978 |
| Zwischen Freigabe und Rückmeldung | 52 | 11 | 5,408586 |
| Nach Rückmeldung | 47 | 0 | 0,201317 |

Zwei Fenster überlappen eine Markierungsgrenze und sind in diesen drei
Phasensummen nicht enthalten. Der unveränderte MSE-Threshold beträgt 0,477203.
Die elf Alarmfenster sind keine elf Störungsversuche; es gab einen Anruf.

## Zeitliche Interpretation

Erster Alarm: Fenster 97 bei 59,916734 s seit Aufnahmestart; dies liegt
8,268224 s nach der Operator-Markierung. Der Wert enthält unter anderem die
Zeit bis zum tatsächlichen Anruf und Vibrationsbeginn. Er ist **keine
gemessene Fehler-Erkennungsverzögerung**.

Der physische Vibrationsbeginn und das Ende wurden nicht unabhängig erfasst.
Die 32,876860 s zwischen Freigabe und Rückmeldung sind deshalb ebenfalls
keine gemessene Vibrationsdauer. Die Daten zeigen Alarmfenster nach Freigabe
und unauffällige Fenster davor/danach, erlauben aber noch keinen belastbaren
Geschwindigkeitsvergleich mit anderen Methoden oder eine Erkennungsquote.

## Rechenzeit und Dokumentation

Median der Fensterverarbeitung: 0,459028 ms. Prozess-CPU, RAM, Temperatur und
Takt stehen pro Fenster in decisions.csv. Dies ist ein einzelner Pilotlauf,
kein kontrollierter isolierter Ressourcenbenchmark. Grafikexporte und
Browser-/Präsentationsexporte wurden erst nach Ende dieser Aufnahme freigegeben.

Quellen: decisions.csv, raw.csv, cues.jsonl und run.json im selben Verzeichnis.
