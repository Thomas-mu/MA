# Versuchsprotokoll: Handyvibration auf dem Tisch

Status: VORBEREITET, noch keine wissenschaftliche Messreihe durchgeführt.
Betriebspunkt: 75 % PWM (zuletzt gewählter Betriebspunkt).
Methoden: Autoencoder, Isolation Forest und RMS, jeweils einzeln im Prozess.
Geplant: ein Anruf/Vibrationsereignis pro Methode; insgesamt drei Anrufe.

## Aufbau und Kalibrierung
Handyposition, Befestigung, Vibrationsmuster, Sensorposition und Lüfteraufstellung
vor Beginn dokumentieren. Das Handy bleibt auch in Normalphasen am gleichen Ort.
Der endgültige Aufbau ist noch nicht bestätigt. Das kopierte Vergleichsbündel
ist deshalb vorerst nur für technische Pilotprüfungen freigegeben. Bei geändertem
Aufbau neue normale Trainings-/Validierungsaufnahmen und Kalibrierung erstellen.
Keine Anpassung der Schwellen an die späteren Störungsversuche.

## Ablauf je Methode
Mindestens 30 s ungestörte Vorlaufphase. Der Operator protokolliert die Aufforderung
zum Anrufen. Vorgesehen sind etwa 5 s Vibration, danach mindestens 15 s Ruhe.
Einmal je Methode durchführen. Der Operator protokolliert auch das gemeldete Ende und
Abweichungen. Alle Bedienung, Aufzeichnung und Auswertung übernimmt der Assistent.
Die Person am Aufbau befestigt das Handy und löst die Vibration nach Signal aus.

## Auswertung und Grenzen
Rohdaten und Entscheidungen vollständig speichern. CPU (100 % = ein Kern),
Prozess-RAM, Rechenzeit, Fensterlatenz, Sensorausfälle und verworfene Fenster
protokollieren. Temperatur und Takt dienen als Betriebsdiagnose.
Diagramme erst nach der Aufnahme als PNG/PDF exportieren; keine Live-GUI nötig.
Exporte sind Diagramme, keine angeblichen Screenshots einer unbeobachteten GUI.
Fotos des tatsächlichen Aufbaus sind nur mit realer Kameraaufnahme möglich.

Anrufaufforderung und Rückmeldung sind keine gemessenen physischen Anfangs-/Endzeiten.
Deshalb ohne unabhängige Referenz keine echte Fehler-Erkennungsverzögerung oder
bestätigte Erkennungs-/Fehlalarmrate behaupten. Alarmzahlen zunächst deskriptiv.
Jede Vibrationsphase zählt als ein Versuch, nicht jeder Schlag oder Alarmwechsel.
Einzelanrufe zwischen Methoden liefern ähnliche, aber nicht identische Signale.
Ein späterer Replay-Vergleich derselben Rohaufnahme ermöglicht identische Eingaben.
Die Reihenfolge der Methoden bei Wiederholungen wechseln, um Reihenfolgeeffekte
zu prüfen. Ein Ereignis je Methode ist ein Funktionstest, keine belastbare Statistik.
Eine Erkennungsquote von 0/1 oder 1/1 belegt keine allgemeine Zuverlässigkeit.

## Dateien
plan.json und bundle/: eingefrorene Planung und Modellartefakte.
Je Lauf: raw.csv, decisions.csv, cues.jsonl, run.json, summary.json,
report.md und figures/overview.png sowie overview.pdf.
technical_check-Läufe dienen ausschließlich der Funktionsprüfung.
