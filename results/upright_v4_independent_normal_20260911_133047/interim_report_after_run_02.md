# Unabhängige Normalitätsprüfung v4 – Zwischenbericht nach Lauf 2

**Zwei von drei geplanten unabhängigen Normalläufen sind abgeschlossen.** Lauf 3 ist noch nicht freigegeben oder gestartet. Beide Aufnahmen erfolgten ohne Platte bei unverändertem Aufbau v4, 75 % PWM und 25 kHz. Sie wurden separat gespeichert und mit dem vorab eingefrorenen Modellpaket ausgewertet. Dieser Zwischenstand ersetzt keine abschließende Beurteilung über drei Starts.

## Durchführung und Zeitbasis

| Merkmal | Lauf 1 | Lauf 2 |
|---|---:|---:|
| Stellbefehlsaufruf, MESZ | 2026-09-11T17:59:59.805742+02:00 | 2026-09-11T18:13:06.326894+02:00 |
| Erster XYZ-Punkt nach Stellbefehlsaufruf, ms | 93.229489 | 96.559631 |
| Hostzeitspanne erster bis letzter XYZ-Punkt, s | 299.991082770 | 299.990129944 |
| Zusätzliche Auszeit seit Freigabe, s | 60.026400232 | 60.022449160 |
| Gesamte Auszeit seit vorherigem 0-%-Befehlsabschluss, s | unbekannt | 486.099037236 |
| 0-%-Befehlsabschluss, MESZ | 2026-09-11T18:05:00.227875+02:00 | 2026-09-11T18:18:06.723005+02:00 |

Die Auszeiten sind Softwareintervalle. Der genaue Zeitpunkt des mechanischen Stillstands und damit die vollständige mechanische Auslauf- oder Abkühlzeit wurden nicht gemessen. Nach Lauf 1 bestätigte der Nutzer erneut „Lüfter steht, nächster Lauf freigegeben“. Dies gab ausschließlich Lauf 2 frei. Angeschlossene Versorgung und unveränderter sicherer Aufbau wurden als fortbestehende, bereits bestätigte Bedingungen übernommen; eine Änderung wurde nicht gemeldet. Es gab keine Antwortfrist und keinen Wiederholungsstart.

Aufbauversion `fan_upright_position_v4_20260911_103726`: aufrechter Lüfter am festen v4-Ort, ADXL345 mit zwei Schrauben am feststehenden Rahmen, schräg sitzende Platine. Sensoreinstellungen unverändert: nominell 200 Hz, ±2 g, Full Resolution, 0,0039 g/LSB, FIFO-Stream, I²C-Bus 1 mit konfigurierten 100 kHz. GPIO18 (physischer Pin 12) ist Hardware-PWM-Kanal 2; die Drehzahl wurde nicht gemessen.

## Qualitätsprüfung

| Merkmal | Lauf 1 | Lauf 2 |
|---|---:|---:|
| Vollständige XYZ-Messpunkte | 62133 | 62133 |
| Einzelne Achsenwerte | 186399 | 186399 |
| Beobachteter XYZ-Durchsatz pro Sekunde | 207.112823 | 207.113481 |
| Host-Leseabstand Median, ms | 5.561991 | 5.586499 |
| Host-Leseabstand 99. Perzentil, ms | 5.698256 | 5.691956 |
| Maximaler Host-Leseabstand, ms | 15.099650 | 11.103869 |
| Host-Leseabstände über 10 ms | 3 | 3 |
| Host-Leseabstände über 160 ms | 0 | 0 |
| Maximale Sensor-Lesedauer, ms | 5.638205 | 8.752184 |
| Maximaler FIFO-Füllstand | 3 | 2 |
| Lückenflags | 0 | 0 |
| Überlaufflags | 0 | 0 |
| Sättigungsflags | 0 | 0 |
| Nichtmonotone Host-Leseabstände | 0 | 0 |
| Nichtendliche XYZ-Messpunkte | 0 | 0 |

Beide Dateien bestehen die vorab festgelegte Qualitäts- und Herkunftsprüfung. Nominelle 200 Hz sind von beobachteten rund 207,113 XYZ/s getrennt zu betrachten. Der Durchsatz ist (N−1) geteilt durch die Hostzeitspanne. Host-Leseabschlüsse sind keine Messung der Sensorwandlungszeitpunkte. Die genaue Anzahl etwaiger physischer Verluste bleibt unbekannt; fehlende Flags belegen keine exakt verlustfreie Sensorwandlungsfolge.

## Eingefrorener Methodenvergleich

Bewertet wird unverändert ausschließlich [180,300) Sekunden seit PWM-Stellbefehlsaufruf. Je Modellfenster 128 XYZ-Punkte, Schrittweite 128, keine Überlappung und keine Aufnahmegrenzen überschreitenden Fenster. Die Auswahl umfasst 24.853 beziehungsweise 24.854 XYZ-Punkte; nach jeweils 194 vollständigen Fenstern bleiben 21 beziehungsweise 22 Punkte unaufgefüllt. Der gesamte Anlauf bleibt in den Rohdateien gespeichert. 180 Sekunden bleiben eine vorläufige Einlaufzeit.

Float64-Achsenmittelwertentfernung je Fenster → Float32 → gespeicherter Scaler. Die Eingaben stimmen nach dem vor Aufnahmebeginn ausgeführten Paritätsnachweis exakt mit dem Trainingsweg überein; 112 Softwaretests bestanden. Alle Methoden erhalten wertgleiche standardisierte Eingaben. Das Paket und seine RMS-, IF- und TFLite-Schwellen sind unverändert. Keine neue Skalierung, kein Training und keine Anpassung der Abschnittsauswahl fanden statt.

| Lauf | Methode | Gültig | Ungültig | Fehlalarme | Fehlalarmrate unter gültigen normalen Fenstern |
|---|---|---:|---:|---:|---:|
| Lauf 1 | RMS | 194 | 0 | 57 | 29.38 % |
| Lauf 1 | Isolation Forest | 194 | 0 | 34 | 17.53 % |
| Lauf 1 | TFLite-Autoencoder | 194 | 0 | 0 | 0.00 % |
| Lauf 2 | RMS | 194 | 0 | 0 | 0.00 % |
| Lauf 2 | Isolation Forest | 194 | 0 | 0 | 0.00 % |
| Lauf 2 | TFLite-Autoencoder | 194 | 0 | 0 | 0.00 % |
| Zusammen, 2 Läufe | RMS | 388 | 0 | 57 | 14.69 % |
| Zusammen, 2 Läufe | Isolation Forest | 388 | 0 | 34 | 8.76 % |
| Zusammen, 2 Läufe | TFLite-Autoencoder | 388 | 0 | 0 | 0.00 % |

![Scoreverläufe beider Normalläufe mit eingefrorenen Schwellen](comparison_after_run_02/scores.png)

RMS und Isolation Forest melden im zweiten Lauf keine Fehlalarme. Im ersten Lauf liegen dagegen 57 beziehungsweise 34 Fehlalarme vor. Die gemeinsame Grafik zeigt, dass die beiden Verläufe zunächst ähnliche Scorebereiche aufweisen und RMS-/IF-Scores im späteren Teil von Lauf 1 steigen. Lauf 2 zeigt keinen vergleichbar ausgeprägten Anstieg. Der Unterschied ist daher nicht allein als konstanter Mittelwertversatz zwischen Starts zu beschreiben. Eine Ursache, etwa Erwärmung oder mechanische Änderung, ist durch diese Daten nicht nachgewiesen.

Der Autoencoder blieb in beiden bisher geprüften Normalläufen unter seiner eingefrorenen Schwelle. Das belegt keine Empfindlichkeit gegenüber veränderten Zuständen. Die zusammengefassten Fehlalarmraten sind deskriptive Fensteranteile; benachbarte Fenster sind keine unabhängigen Wiederholungen. Hohe normale Fehlalarmraten aus Lauf 1 bleiben als Ergebnis erhalten und werden durch Lauf 2 nicht aufgehoben. Es wird kein Anomalie-Recall, F1 oder allgemeiner Erkennungsnachweis aus den normalen Testdaten abgeleitet. Ungültige Fenster würden weder als NORMAL noch im Fehlalarmnenner zählen.

## Status und nächster Schritt

Lauf 3 wartet auf die neue Nachricht **„Lüfter steht, nächster Lauf freigegeben“**. Danach folgen erneut 60 Sekunden zusätzliche Auszeit, einmalig 75 % PWM bei 25 kHz und 300 Sekunden Aufnahme. Ohne neue Freigabe bleibt der Start pausiert. Die gesamte vorherige Auszeit wird separat protokolliert.

Die 0-%-Stellvorgabe nach Lauf 2 wurde ausgelesen und später unabhängig bestätigt: 40.000 ns Periode, 0 ns Tastdauer, aktivierter PWM-Kanal, GPIO18 in Funktion `PWM0_CHAN2`. **Ein mechanischer Stillstand nach Lauf 2 wurde noch nicht bestätigt.** Der abschließende Drei-Lauf-Bericht folgt erst nach dem dritten freigegebenen Start.

Ein späterer kontrolliert veränderter Kandidat ist die separat befestigte Platte bei unverändert 75 % PWM, eingebettet zwischen zeitnahen Normalreferenzen. Als Nutzerangaben sind 120 × 120 mm und 100 mm Abstand dokumentiert; Bezugsebene, Auslassseite und tatsächliche Überdeckung müssen für einen neuen Versuch eindeutig dokumentiert sein. Der alte 60 × 120-mm-Plan ist keine bestätigte Istgeometrie. Jetzt wird kein Plattenversuch gestartet. Die hohen normalen Fehlalarme erschweren die Zuordnung späterer Alarme zur Luftstromveränderung und müssen im Vergleich erhalten bleiben. Modelländerungen würden eine neue Version und neue unabhängige Tests erfordern.

## Dateien und Erhaltung

Der Hashvergleich aller 1.172 vor dieser Testreihe vorhandenen Dateien ergab nach Lauf 2 keine Veränderungen. Worddatei, historische Messungen und eingefrorene Modelle blieben unverändert. Siehe [Nachprüfung](verification_after_normal_test_02.json), [vorab festgelegtes Protokoll](test_protocol.md) und [Vergleichstabelle](comparison_after_run_02/comparison.csv).

- Lauf 1: `normal_test_01_75pwm_300s_20260911_155959_798760`, Rohdaten-SHA256 `058f4aec69a567236dbe7e4c0d84590f51f3210ef320a2cd4ae794be5baa8e18`; [Ergebnisse und Artefakthashes](evaluation_normal_test_01/summary.json), [Sitzungsprotokoll](normal_test_01_session.json).
- Lauf 2: `normal_test_02_75pwm_300s_20260911_161306_321362`, Rohdaten-SHA256 `20760adbcad23554c0b49745b6163444e7974a01be20412b040304a1ff1708f2`; [Ergebnisse und Artefakthashes](evaluation_normal_test_02/summary.json), [Sitzungsprotokoll](normal_test_02_session.json).

Gemeinsamer Modellpaket-SHA256: `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`. Protokoll-SHA256: `d208261cdbe9e258b4a56ae87769c3700145b2221c4b92fed4fb55eb67fd73a7`. Beide neuen Quellen wurden auf Ausschluss historischer Trainings-, Validierungs- und bereits untersuchter Daten sowie eindeutige Identität geprüft.
