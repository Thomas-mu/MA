# Autoencoder: erster Anruf-Pilot

Dieser Lauf ist eine explorative Beobachtung mit dem bestehenden 75-%-Profil.
Die endgültige Handyposition und eine zugehörige Neukalibrierung waren noch
nicht dokumentiert. Die Modelle/Schwellen wurden für den Versuch nicht verändert.

## Gesicherte Beobachtungen

- 170 vollständige Fenster ausgewertet; 21.868 Rohsamples gespeichert.
- Keine ungültigen Fenster, keine verworfenen Fenster; keine erfassten
  Gap-, Overrun- oder Sättigungsflags.
- 108 Samples des letzten unvollständigen Fensters im Rohprotokoll erhalten.
- Aufforderung/Chat-Ankündigung bei 38,637 s seit Aufnahmestart.
- Rückmeldung „fertig“ bei 68,145 s seit Aufnahmestart.
- Vor der Ankündigung: 25 Alarmfenster unter 62 vollständigen Fenstern.
- Vollständig zwischen den Chat-Markierungen: 5 Alarmfenster unter 47 Fenstern.
- Vollständig nach der Rückmeldung: 0 Alarmfenster unter 59 Fenstern.
- Zwei Fenster überlappen eine Markierungsgrenze und sind diesen drei
  Phasensummen deshalb nicht zugeordnet.

Der erste Alarm trat bereits bei 8,037 s auf, also etwa 30,601 s vor der
Anrufankündigung. Der erste Alarm auf einem vollständig nach der Ankündigung
liegenden Fenster war 897,657 ms nach dieser Markierung verfügbar.
Dieser Abstand ist **keine gemessene Reaktionszeit ab physischem Vibrationsbeginn**.

Die 29,508 s zwischen den Chat-Markierungen sind ebenfalls **keine gemessene
Vibrationsdauer**. Die tatsächliche Dauer wurde nicht unabhängig erfasst.
Die Ursache der vorherigen Alarme ist aus den verfügbaren Markierungen unklar;
sie dürfen weder sicher als Fehlalarme noch als Handyvibration bezeichnet werden.

## Rechenzeit und Grenzen

Der Median der Verarbeitung eines vollständigen Rohfensters bis zur
Schwellenentscheidung lag in diesem Lauf bei 0,438260 ms. Das ist eine
Rechenzeit, keine Fehler-Erkennungsverzögerung. Prozess-CPU und RAM befinden
sich in decisions.csv. Vorbereitung/Operatorzugriffe liefen teilweise auf
demselben Pi; die Messung ist kein isolierter Ressourcenbenchmark.

Es wurde ein Anruf angekündigt und sein Ende zurückgemeldet. Daraus folgen
noch keine verifizierte Erkennungsquote, echte Fehlalarmrate oder Rangfolge
zwischen Methoden. Die Rohdaten und unveränderten Schwellen bleiben als
Grundlage für eine nachvollziehbare spätere Auswertung erhalten.

Quellen: decisions.csv, cues.jsonl, run.json und raw.csv im selben Verzeichnis.
