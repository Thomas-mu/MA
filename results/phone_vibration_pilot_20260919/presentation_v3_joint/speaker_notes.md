# Erläuterungen zu den Pilotergebnissen

## 1. Drei Methoden erkennen die eingebrachte Störung

Alle drei ausgewählten Live-Aufnahmen enthalten Alarmfenster zwischen Anruf-Freigabe und Ende-Rückmeldung; vollständig davor und danach liegen keine Alarmfenster. Physischer Vibrationsbeginn ist nicht gemessen. Im Offline-Replay identischer Daten: zweimal Gleichstand auf Fensterauflösung, einmal Autoencoder ein Fenster früher. Nur drei Einzelereignisse, keine statistische Rangfolge. Externe Tischvibration ist kein belegter Lüfterdefekt. Quellen: sources/trials/*/{run.json,decisions.csv,cues.jsonl}, replay_v1/summary.json.

## 2. Gemeinsame Messkette, eingefrorene Schwellen

ADXL345, nominal 200 Hz; Fenstergröße und Schrittweite 128, nominal 0,64 s. Zeitstempel sind Host-Lesezeitstempel. Pro Lauf nur eine Methode, ohne Live-GUI, mit 20 Aufwärmfenstern und derselben Erfassungsversion. AE: Rekonstruktions-MSE; IF: negatives score_samples; RMS: quadratischer Mittelwert nach Standardisierung. Schwellen: P99 der normalen Validierung (97 Fenster); AE übernimmt die eingefrorene Keras-Kalibrierung. Validierung wurde beim AE auch für Early Stopping verwendet. Schwellen wurden nicht auf den Anrufen angepasst. Endgültiger Handyaufbau und Übertragbarkeit der Kalibrierung bleiben unbestätigt. Quellen: plan.json, bundle/bundle.json.

## 3. Alle drei Läufe zeigen zeitlich begrenzte Alarme

Jede Kurve gehört zu einem anderen Anruf und zur jeweils live aktiven Methode. Die x-Achse beginnt pro Aufnahme neu. Gestrichelt bei 1 liegt die eigene Schwelle; Score/Schwelle ist keine Wahrscheinlichkeit und keine gleiche Sensitivität. Graue Bereiche sind Chat-Markierungen, keine Ground Truth. Ein fehlender Alarm außerhalb ist kein Nachweis einer allgemeinen Fehlalarmrate. Vollständige Fenster: AE 184, IF 196, RMS 234. Quelle: decisions.csv und cues.jsonl.

## 4. Wer meldet zuerst auf denselben Daten?

Offline-Replay, keine zusätzliche Live-Aufnahme und kein Zeitbenchmark. Original-Fenstergrenzen wurden über window_index sowie erste/letzte Zeitstempel geprüft. Erste Alarmfenster vollständig zwischen den Chat-Markierungen: Aufnahme A: AE/IF/RMS jeweils 97; B: AE 93, IF/RMS 94; C: alle 155. Vor der Freigabe keine Alarme in allen neun Kombinationen. Gleiche Fensternummer bedeutet Gleichstand; Laufzeit ist kein Tie-Break. Reproduktion der 614 Original-Live-Entscheidungen ohne Abweichung, maximale Scoreabweichung 0. Ein Fenster Vorsprung ist nicht die absolute Verzögerung ab physischem Beginn. Quelle: replay_v1/summary.json und decisions.csv.

## 5. Mehr Alarmfenster bedeuten nicht mehr Treffer

Live: AE 11, IF 6, RMS 6 Alarmfenster. Replay-Matrix Zeilen A/B/C, Spalten AE/IF/RMS: 11/6/8, 9/6/6, 9/6/6. Alle Replay-Alarme liegen vollständig zwischen den Chat-Markierungen. Ein Anruf kann mehrere intermittierende Vibrationsimpulse und mehrere Alarmfenster erzeugen. Fenster sind keine unabhängigen Ereignisse. Nicht aus 11 gegenüber 6 eine bessere Trefferquote ableiten. Fensterzahlen und Dauern unterscheiden sich. Keine physisch referenzierte Ereignis-Erkennungsrate verfügbar.

## 6. RMS rechnet am kürzesten, IF deutlich länger

processing_ms umfasst Standardisierung, Scoreberechnung und Entscheidung nach Fensterentnahme. Nicht nur reine Modell-Inferenz, nicht Wartezeit auf ein vollständiges Fenster. Dargestellt Median und P95 aller gültigen Fenster. P95 bedeutet 95 % der gemessenen Werte liegen darunter oder gleich. Drei getrennte Läufe, keine Wiederholungen; CPU-Takt dynamisch 1,5 bis 2,4 GHz. Die isolierte Algorithmuslaufzeit wurde nicht unter fixierter Systemumgebung gemessen. Quelle: ausgewählte decisions.csv, processing_ms. Kürzere Berechnung garantiert kein früheres Alarmfenster.

## 7. Isolation Forest beansprucht mehr Prozess-RAM

CPU ist der Median der intervallweise erfassten Prozesswerte: 100 % entspricht einem Kern, nicht dem gesamten Pi. Keine zeitgewichtete Gesamtauslastung und kein systemweiter Energieverbrauch. RAM ist maximale abgetastete RSS während der Aufnahme, nicht Start-Peak oder inkrementeller Modellbedarf. Keine Baseline-Subtraktion. Erfassung lief jeweils allein; bestehende Betriebssystem-/Editorprozesse bleiben Umgebungseinflüsse. Temperatur und dynamischer CPU-Takt wurden protokolliert; keine kontrollierten Wiederholungen. Keine Messung elektrischer Leistungsaufnahme. Quelle: decisions.csv, Prozessfelder.

## 8. Echte Screenshots der gespeicherten Berichte

Hier gezeigt: Autoencoder-Bericht. Für alle drei ausgewählten Läufe liegen report_screenshot/report.png, report.html, browser.log und evidence.json vor. Screenshots wurden wirklich mit Chromium gerendert; Quell- und Bildhashes sind archiviert. Die Plots selbst sind CSV-basierte Exporte. Alle Originaldaten einschließlich zurückgesetzter Anläufe bleiben erhalten. Vollständige Dateien in sources/trials/.

## 9. Pilotbefund – noch kein Zuverlässigkeitsnachweis

Alle sechs Versuche: AE01 170 Fenster/30 Alarme, AE02 158/12 mit einem ungültigen Fenster, AE03 184/11; IF01 154/7, IF02 196/6; RMS01 234/6. Nutzer bat bei AE01/02 und IF01 um Wiederholung; keine Löschung. Die Auswahl sauber koordinierter Versuche ist kein Nachweis allgemeiner Fehlalarmfreiheit. Chat-Cues messen keinen physischen Beginn; Handyposition/Befestigung/Muster sind nicht unabhängig dokumentiert. Das Profil stammt aus früherem 75-%-Standlauf; bundle measurement_chain_status=unverified_legacy. Fehlende Wiederholungen, wechselnder Takt, Reihenfolge AE→IF→RMS und ungleiche Stimuli begrenzen Schlussfolgerungen. Die geprüften digitalen Qualitätsflags waren in den drei ausgewählten Läufen unauffällig, beweisen aber keine vollständig validierte Messkette.

## 10. Erste Ergebnisse sind da – die Grenzen sind klar

Kernaussage: Alle drei Methoden reagierten im jeweils ausgewählten Anrufintervall. Im gleichen Datenstrom gab es zwei Gleichstände und einmal einen Vorsprung von einem Fenster für AE. RMS hatte die geringste beobachtete Berechnungszeit, IF die höchste Prozess-RSS. Das belegt keine allgemeine Gewinner-Methode. Nächste wissenschaftliche Schritte: Aufbau dokumentieren und mit Normaldaten validieren; unabhängige physische Start-/Endreferenz, wiederholte reproduzierbare Stimuli, Reihenfolge wechseln; Ressourcen separat mit kontrollierter Umgebung und gleicher Laufzeit testen. Diese Schritte sind Empfehlungen, nicht bereits erledigt. Präsentation und Rohdaten sind getrennt von der Vorbereitung versioniert.


# Teil B: Gemeinsamer Live-Versuch

## 11. Gemeinsamer Anruf: AE liefert zuerst Alarm

Ein zusätzlicher gemeinsamer Live-Anruf mit allen drei Methoden auf einem Sensorstream. Drei Worker-Threads erhalten identische Fenster und werden mit einer Barriere freigegeben. Erstes Alarmfenster AE und IF 108, RMS 109. Fensterrang AE/IF gemeinsam 1, RMS 2. Erste tatsächliche decision_ns: AE zuerst, IF 19,061107 ms später, RMS 615,658777 ms später. Daher Ausgabe-Ränge 1/2/3. Diese relativen Abstände enthalten Rechenzeit und Scheduling, aber sind keine absolute Verzögerung ab physischem Vibrationsbeginn. Quelle: sources/joint_run/decisions.csv; joint_summary.json.

## 12. 197 Fenster, drei Methoden – gleiche Daten

197 vollständige Fenster zu je 128 × 3 Werten, 25.270 Rohsamples, 54 Samples im unvollständigen Schlussfenster. Keine verworfenen oder ungültigen Fenster, keine gemeldeten Lücken/Überläufe/Sättigungen. 591 Entscheidungen wurden offline exakt reproduziert; Rohfensterhashes und gemeinsame Zeitgrenzen geprüft. AE 11, IF 7, RMS 6 Alarmfenster, alle vollständig zwischen den Chat-Markierungen. 77 Fenster vollständig vor Freigabe, 79 zwischen Markierungen, 39 danach, 2 grenzüberlappend. Vorher/nachher und grenzüberlappend keine Alarme. Ein Anruf bleibt ein Versuch, nicht 24 unabhängige Fehler. Score/Schwelle ist keine Wahrscheinlichkeit. Quelle: raw.csv, decisions.csv, cues.jsonl, run.json.

## 13. Die Gesamtlast im gemeinsamen Betrieb

Prozess-CPU als Median intervallweiser Samples: 13,04 % eines Kerns; maximal abgetastete RSS 174,42 MiB. Kein Start-Peak und keine elektrische Leistung in Watt. Worker-Berechnungszeiten enthalten Standardisierung, Score und Entscheidung unter Konkurrenz. Eine Thread-Barriere garantiert keine exakt gleichzeitige CPU-Ausführung. Betriebssystem-Scheduling, Bibliotheken und dynamischer Takt beeinflussen die Werte. Mit isolierten früheren Läufen nur explorativ vergleichen, kein kontrollierter Parallelisierungsbenchmark. Quelle: sources/joint_run/resources.csv und decisions.csv.

## 14. Gemeinsame Aufnahme vollständig dokumentiert

Der abgebildete Bericht wurde tatsächlich im Browser gerendert, nicht als Live-GUI rekonstruiert. Raw-CSV, Eingabehashes, Zeitstempel, Entscheidungs-CSV, Ressourcen und Quellenmanifest sind archiviert. Acht fokussierte Tests sind bestanden; zusätzlich 591 echte Entscheidungen aus dem gemeinsamen Lauf exakt nachgerechnet. Trotz identischer Inputs bleibt dies ein einzelner Anruf ohne unabhängige physische Start-/Endmessung. Finaler Handyaufbau ist nicht verifiziert; Tischvibration ist kein belegter Lüfterdefekt. Schwellen und PWM 75 % unverändert. Für allgemeine Aussagen Aufbau validieren und Ereignisse wiederholen. Teil A zeigt frühere separate Anrufe mit Offline-Replay; Teil B ist der zusätzliche gemeinsame Live-Anruf.