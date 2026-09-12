# Ergebnis und Einordnung des zweiten normalen Betriebspunkts

Die drei vorgesehenen 300-s-Aufnahmen bei **50 % PWM und 25 kHz** sind abgeschlossen. Insgesamt wurden **186.408 XYZ-Punkte** separat gespeichert. Je Lauf sind 194 Fenster aus [180,300) s gültig, insgesamt **582 Fenster pro Methode; 0 ungültig**. Die Steuerung steht abschließend zurückgelesen auf **0 % PWM**. Ein mechanischer Stillstand wurde am Ende nicht beobachtet.

| Methode | 50 %: neue drei Normalläufe | 75 %: sechs frühere Normalläufe |
|---|---:|---:|
| rms | 3/582 = 0.52 % | 60/1164 = 5.15 % |
| isolation_forest | 1/582 = 0.17 % | 35/1164 = 3.01 % |
| tflite_autoencoder | 35/582 = 6.01 % | 64/1164 = 5.50 % |

**Einordnung:** RMS und Isolation Forest zeigen bei den drei neuen 50-%-Aufnahmen niedrigere gepoolte Fehlalarmraten als in der vorab festgelegten älteren 75-%-Gruppe. Beim Autoencoder ist die Rate mit 6,01 % gegenüber 5,50 % numerisch ähnlich; sie steigt um 0,52 Prozentpunkte. Die Fehlalarme je neuem Lauf sind RMS 1/2/0, Isolation Forest 0/1/0 und Autoencoder 17/11/7. Der Betrieb bei niedrigerer PWM beseitigt die normalen Autoencoder-Fehlalarme damit nicht.

Der Vergleich ist deskriptiv: drei neue Läufe gegen sechs nicht zeitgleiche frühere Läufe. Unterschiede zwischen einzelnen Starts, zeitliche Veränderungen und nicht gemessene Einflüsse lassen sich hier nicht kausal von der PWM trennen. Kein Signifikanznachweis und kein allgemeiner Robustheitsnachweis. Die frühere ausdrückliche Erlaubnis des Nutzers für selbstständige Starts/Stopps erlaubte automatische Fortsetzung. Zwischen diesen Läufen gab es jeweils mindestens 60 s zusätzliche Software-Auszeit bei zurückgelesenen 0 %, aber keine erneuten Sichtbestätigungen des mechanischen Stillstands.

**Messqualität:** Die drei beobachteten Raten liegen zwischen 207,112 und 207,144 XYZ/s bei nominell 200 Hz. Kein nichtmonotoner Zeitstempel, kein gespeichertes Gap-/Overrun-/Sättigungsflag, keine Host-Lücke über 10 ms. Das größte Host-Intervall beträgt 9,790 ms. Genaue physische Verluste und die tatsächliche Drehzahl bleiben unbekannt. Der tatsächliche erste XYZ-Punkt lag 95–98 ms nach dem Stellbefehl. Die vollständigen Qualitätsprüfungen und die Sensorregister stehen im Messbericht.

**Vibrationsverlauf:** Die späten Mittelwerte des physischen Vektor-AC-RMS liegen bei 16,761 / 16,600 / 16,485 mg. Die Spanne zwischen diesen Laufmittelwerten beträgt 0,276 mg (rund 1,66 % des Mittelwerts der drei Laufmittelwerte). Innerhalb der einzelnen Läufe betragen die Standardabweichungen der 5-s-Werte 0,690 / 1,226 / 0,308 mg. Die ersten beiden Läufe enthalten späte Spitzen und positive deskriptive Steigungen (+0,477 / +0,691 mg/min); Lauf 3 ist näherungsweise flach (−0,075 mg/min). Es gibt damit keinen gleichartigen fortgesetzten Trend in allen drei Läufen. Die Ursache der Spitzen ist nicht nachgewiesen. Sie bleiben vollständig in den Daten und in der Bewertung; 180 s werden nicht nachträglich geändert.

![Fehlalarmraten je vollständigem Lauf](comparison_50_vs_75/false_alarm_comparison.png)

**Schlussfolgerung:** Der zweite normale Betriebspunkt ist mit dem eingefrorenen Paket geprüft. Dieser Nachweis schließt eine weitere Evaluationslücke, belegt aber weder erfolgreiche Anomalieerkennung noch eine Überlegenheit von 50 % für spätere veränderte Zustände. Weniger normale Fehlalarme können nicht allein die Eignung zur Erkennung veränderter Betriebszustände belegen. Die bekannten schwachen Plattenergebnisse bleiben gültig; es wurde keine Schwelle angepasst und kein Modell nachtrainiert.

**Nächster gezielter Schritt:** Den Sensor-Live-/Latenznachweis vorbereiten und mit einem einzelnen 300-s-Lauf des neuen gemeinsamen Datenwegs ohne GUI bei dem bisherigen primären Betriebspunkt 75 % beginnen. Dieser erste Lauf prüft Rohdatenfluss, exakte Offline-/Live-Scoregleichheit, vollständige Entscheidungsbilanz und Nullstellung bei einem Fehler. Er ist noch kein isolierter CPU-/RAM-Vergleich der Methoden. Danach sind für den geplanten Ressourcenvergleich getrennte frische Prozesse je Methode und Wiederholungen nötig. Keine weiteren Normalitätsmessungen nur zum Glätten der RMS-Kurve und kein neuer Plattenversuch sind aus diesen Ergebnissen unmittelbar erforderlich.

Die Software- und Messbedingungen des Live-Nachweises müssen vorher als neues Protokoll festgelegt werden. Die vorhandene Steuerfreigabe ist dokumentiert; ein zusätzlicher Live-Lauf wurde in dieser Folge **nicht gestartet**. Aufbau v4 und die entfernte Platte bitte für diesen möglichen nächsten Schritt unverändert lassen.

[Vollständiger Messbericht mit Zeitpunkten, Qualität und Tabellen](measurement_report.md) · [128er-Scoreverläufe](comparison_50_only/scores.png) · [5-s-Vibrationsverläufe](comparison_50_vs_75/rms_5s.png)

Worddatei, Modelle, Originaldaten und historische Berichte bleiben unverändert.
