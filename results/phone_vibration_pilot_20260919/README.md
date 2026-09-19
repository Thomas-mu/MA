# Handyvibrations-Pilot vom 19.09.2026

Status: Drei ausgewählte Einzelaufnahmen, deren Offline-Replay und ein zusätzlicher gemeinsamer Live-Anruf sind abgeschlossen.
Es ist kein weiterer Anruf erforderlich. Der Lüfter wurde nach den Aufnahmen unverändert bei 75 % PWM belassen.

## Ergebnisse für die Besprechung

- [Aktuelle PowerPoint: 14 Folien inklusive gemeinsamem Live-Anruf](presentation_v3_joint/handyvibration_mit_gemeinsamem_liveversuch.pptx)
- [Aktuelle Präsentation als PDF](presentation_v3_joint/handyvibration_mit_gemeinsamem_liveversuch.pdf)
- [Ergebnisbericht des gemeinsamen Live-Anrufs](presentation_v3_joint/joint_report.md)
- [Nummerierter Vergleich: erstes Fenster und erste Alarmentscheidung](presentation_v3_joint/assets/joint_alarm_order.png)
- [Screenshot des gemeinsamen Berichts](presentation_v3_joint/joint_report_screenshot.png)

Gemeinsamer Live-Anruf: Autoencoder und Isolation Forest schlagen erstmals im selben Fenster 108 an,
RMS in Fenster 109. Die Autoencoder-Entscheidung liegt rund 19 ms vor IF und 616 ms vor RMS.
Dies sind relative Abstände der ersten Alarmentscheidungen dieses Laufs, keine unabhängig gemessenen
Verzögerungen ab physischem Vibrationsbeginn. 197 identische Fenster, 591 gültige Entscheidungen;
alle Rohfensterhashes und Entscheidungen wurden nachgeprüft. CPU/RAM gehören zum gesamten gemeinsamen Prozess.

## Frühere Einzelversuche und Offline-Replay

- [PowerPoint mit zehn Ergebnisfolien](presentation_v2_results/handyvibration_ergebnisse.pptx)
- [PDF der Ergebnispräsentation](presentation_v2_results/handyvibration_ergebnisse.pdf)
- [Ausführlicher Ergebnisbericht](presentation_v2_results/results_report.md)
- [Erklärungen und Quellen je Folie](presentation_v2_results/speaker_notes.md)
- [Nummeriertes Diagramm der ersten Alarmfenster](presentation_v2_results/assets/first_alarm_ranks.png)
- [Durchführungsnachtrag mit allen Neustarts](session_results.md)

Die drei Aufnahmen wurden zusätzlich jeweils allen drei Methoden mit identischen Rohfenstern vorgelegt.
Ergebnis: zweimal Gleichstand beim ersten Alarmfenster; in der ursprünglich mit Isolation Forest aufgenommenen
Sequenz meldet der Autoencoder ein Fenster früher als IF und RMS. Das ist keine allgemeine Sieger-Rangliste
und keine unabhängig gemessene Fehler-Erkennungsverzögerung.

## Screenshots der gespeicherten Berichte

- [Autoencoder](trials/autoencoder_awaiting_call_03/report_screenshot/report.png)
- [Isolation Forest](trials/isolation_forest_awaiting_call_02/report_screenshot/report.png)
- [RMS](trials/rms_awaiting_call_01/report_screenshot/report.png)

Das sind echte Browser-Screenshots nachträglich ausgewerteter Daten. Keine Live-GUI und kein Foto des Aufbaus.
Rohdaten, Entscheidungen, Zeitmarken, Prozesswerte und Hash-Nachweise liegen bei den jeweiligen Aufnahmen.

## Versionen und Aussagegrenzen

`protocol.md` und `plan.json` bleiben als ursprüngliche Planung erhalten; ihr Vorbereitungsstatus ist nicht der aktuelle Durchführungsstand.
`presentation_v1/` zeigt ausschließlich die vorausgehenden Techniktests, keine Anrufergebnisse.
`presentation_v2_results/` enthält die ausgewählten Anrufversuche und das Offline-Replay.
`presentation_v3_joint/` enthält zusätzlich den gemeinsamen Live-Anruf, seine Diagramme und einen echten Bericht-Screenshot.
`joint_trials/all_methods_01/` archiviert dessen originale Rohdaten, gemeinsame Fenster, Zeitstempel und Ressourcenwerte.
`replay_v1/` enthält die zusätzliche Auswertung ohne Sensorzugriff oder Veränderung der Modelle/Schwellen.
Frühere Anläufe wurden nicht gelöscht. Alle sechs ursprünglichen Einzelversuche und der zusätzliche gemeinsame Lauf sind archiviert.

Die PDF wurde wegen fehlendem LibreOffice-Impress-Modul aus einer Druckansicht der PowerPoint-Elemente
mit Chromium erzeugt. Die Folien wurden visuell geprüft; PowerPoint kann Text geringfügig anders umbrechen.

Für belastbare allgemeine Erkennungszeiten und -quoten fehlen weiterhin ein unabhängig gemessener physischer
Vibrationsbeginn, eine bestätigte finale Aufbaukalibrierung und wiederholte Versuche. Tischvibration ist kein
nachgewiesener Lüfterdefekt. Die Prozesswerte sind keine elektrische Leistungsmessung und kein isolierter Modellbenchmark.
