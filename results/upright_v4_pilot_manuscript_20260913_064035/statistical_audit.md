# Statistische und evidenzbezogene Prüfung des abgeschlossenen v4-Pilotstands

Prüfdatum: 13.09.2026. Grundlage ist der vorliegende Manuskripttext `input_readable.txt`. Es wurden ausschließlich vorhandene Dateien gelesen sowie archivierte Scores, Entscheidungen und Laufzeiten nachgezählt. Es erfolgten kein Modellaufruf, kein Training, keine Kalibrierung, keine Messung, kein Hardwarezugriff und keine Änderung vorhandener Daten, Modelle oder Dokumenthistorien. Neue Ausgaben dieser Prüfung sind ausschließlich diese Datei und `statistical_audit.json` im selben Verzeichnis.

## Ergebnis der Nachzählung

Die geprüften Zahlen des Manuskripts stimmen mit den archivierten Entscheidungen überein. Die wesentlichen Grenzen betreffen die statistische und physikalische Interpretation, nicht Rechenfehler. Der Datensatz trägt einen abgeschlossenen deskriptiven Pilotvergleich. Er trägt keine allgemeine Aussage über Defekterkennung, eine kausale PWM-Wirkung oder langfristige Echtzeit- und Speicherzusagen.

Geprüft wurden zehn ursprüngliche Test-Scoretabellen mit je 194 Fenstern und drei Methoden, insgesamt 5.820 Methodenentscheidungen. Für jedes gültige Fenster wurden endlicher Score, unveränderte methodenspezifische Schwelle, die Regel `Score > Schwelle`, das Label und die Fenstergrenzen geprüft. Alle drei Methoden verwenden in jeder Aufnahme dieselben Fenster. Sämtliche geprüften Testfenster liegen im vorab festgelegten Abschnitt `[180,300)` s; ihre Länge beträgt jeweils 128 XYZ-Punkte. Alle geprüften Fenster sind gültig. Die 5.238 Zeilen der zusammengeführten 75-%-/50-%-Normaltabelle stimmen hinsichtlich Score, Schwelle und Entscheidung mit den ursprünglichen Einzeldateien überein.

Die drei Entwicklungsaufnahmen überschneiden sich nicht mit den zehn Testaufnahmen. Die SHA-256-Kennung des eingefrorenen Pakets lautet `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`; sie steht unverändert in sämtlichen geprüften Testtabellen und Laufzeitprozessen. Alle zehn im Paketmanifest aufgeführten Artefaktprüfsummen stimmen mit den vorhandenen Dateien überein. Die Prüfung belegt die Konsistenz des aktuellen Archivstands; eine historische Vollständigkeitsgarantie allein aus Hashes wird daraus nicht abgeleitet.

Die Quellenprüfsummen, Einzelzählungen, Prüfbedingungen und Runtime-Ergebnisse sind maschinenlesbar in `statistical_audit.json` enthalten.

## Entwicklung und Kalibrierung

| Datenrolle | Aufnahmen | Fenster je Methode | RMS-Alarme | IF-Alarme | AE-Alarme |
|---|---:|---:|---:|---:|---:|
| Training | 2 | 388 | 0 | 0 | 0 |
| Validierung/Kalibrierung | 1 | 194 | 2 | 2 | 2 |

Quelle: `results/upright_v4_training_pilot_20260911_130614/analysis/all_normal_window_scores.csv` sowie `run_001/frozen/pilot_bundle.json` und die dort archivierten Implementierungsdateien.

Die Trennung nach vollständigen Aufnahmen verhindert die unmittelbare Verteilung von Fenstern derselben Aufnahme auf Training und Test. Sie erzeugt jedoch keine breite Abdeckung normaler Betriebszustände: Für das Lernen stehen nur zwei normale Aufnahmen zur Verfügung. Die eine Validierungsaufnahme dient sowohl der Bewertung bzw. Auswahl des Autoencoder-Modellstands als auch der Schwellenkalibrierung. Diese Kalibrierung ist vom späteren Test getrennt, aber keine zusätzliche, vom gesamten Entwicklungsverfahren unberührte Kalibrierungsstichprobe.

Die zwei Alarme aus 194 Kalibrierungsfenstern entsprechen 1,03093 %. Sie entstehen unter der verwendeten empirischen P99-Regel mit linearer Interpolation. Sie sind weder eine unabhängig gemessene Test-FPR noch eine Zusage, dass spätere Aufnahmen ungefähr 1 % Fehlalarme besitzen. Die zeitliche Abhängigkeit und die schmale Normalabdeckung begrenzen die Übertragung zusätzlich. Die vorhandene Erläuterung in Manuskriptabsatz 266 ist richtig und sollte erhalten bleiben.

Die eingefrorenen Schwellen sind RMS `1.2747695377144315`, IF `0.5045395247064507` und AE `0.544357966122261`. Beim IF ist der Score `-score_samples` auf dem standardisierten und abgeflachten 128×3-Fenster. Die Entscheidung verwendet die eigene Kalibrierungsschwelle; sie ist nicht die eingebaute `predict`-Entscheidung des IF. `contamination="auto"` legt hier keine erwartete FPR von 1 % fest. Größere Scores sind innerhalb jeder Methode auffälliger. Die Zahlen verschiedener Methoden besitzen keine gemeinsame metrische Skala; insbesondere ist ein IF-Score keine Wahrscheinlichkeit.

Die AE-Schwelle stammt unverändert von den normalen Keras-Validierungsscores. Die Konvertierung zu TFLite und die späteren Prüfungen sind keine erneute Kalibrierung. Dieses Detail ist bereits in Manuskriptabsatz 267 richtig angegeben.

## Gültige Nenner und Auswertungseinheiten

Eine Aufnahme dauert 300 s, ihre Modellkennzahlen beziehen sich jedoch ausschließlich auf die 194 vollständigen Fenster in `[180,300)` s. Die Bezeichnung „je vollständiger Aufnahme“ beschreibt die Gruppierung; sie darf nicht als Auswertung sämtlicher 300 s verstanden werden. Unvollständige Restpunkte bleiben Rohdaten, liefern aber nach dem unveränderten Fenstervertrag keine Entscheidung. Sie sind keine nachträglich ausgeschlossenen Fehlentscheidungen.

FPR verwendet den Nenner aller gültigen Normalfenster der jeweils benannten Auswertung. Recall verwendet die gültigen Fenster des kontrolliert veränderten Labels. Die Zahl von drei Methodenentscheidungen pro Fenster wird nicht als dreifache Stichprobengröße verwendet. Bei reinen Normalaufnahmen ist Recall mangels positiver Fälle nicht definiert; Precision kann bei Alarmen rechnerisch null sein, ist dort aber kein sinnvoller allgemeiner Erkennungsnachweis. Der vorliegende Ansatz, in den Einzelaufnahmen primär Klassenraten und Verwechslungszahlen auszuweisen, ist angemessen.

Nicht überlappende Fenster sind nicht automatisch statistisch unabhängig. Gemeinsamkeit von Aufnahme, Montage, Start, zeitlichem Verlauf und Betriebsbedingungen bleibt bestehen. „Unabhängiger Test“ bedeutet hier vor allem, dass die neuen Aufnahmen nicht zur Entwicklung eingesetzt wurden. Es bedeutet nicht, dass 1.164 Fenster 1.164 unabhängige Wiederholungen repräsentieren. Auch getrennte Starts desselben Geräts unter derselben Montage sind keine Stichprobe verschiedener Geräte oder Einsatzumgebungen.

Die 24 physischen 5-s-RMS-Blöcke im späten Abschnitt und die 194 Modellfenster haben unterschiedliche Länge und Skalierung. Streuungen der 5-s-Werte beschreiben die zeitliche Variation innerhalb eines Laufs; sie sind keine Unsicherheitsschätzung über 24 unabhängige Versuche. Mittelwerte der Achsenbeiträge dürfen die Entscheidungen einzelner Fenster erläutern, aber keine statistische Trennbarkeit beweisen.

## Kontrollierte Folge und H1

Die eine vollständige Folge vom 12.09.2026 besteht aus zwei Normalaufnahmen und einer Aufnahme mit kontrolliert veränderter Luftströmung. Das positive Label bezeichnet diesen Versuchszustand. Es bezeichnet keinen nachgewiesenen Defekt. Die nachträgliche ergänzende Berechnung von Precision, Recall, F1 und Accuracy ändert weder Label noch Scores oder Entscheidungen, ist aber als deskriptive Auswertung des einen Zustandsversuchs zu kennzeichnen.

| Methode | TP | FN | FP | TN | Precision | Recall | F1 | FPR | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RMS | 7 | 187 | 1 | 387 | 87,50 % | 3,61 % | 6,93 % | 0,26 % | 67,70 % |
| Isolation Forest | 4 | 190 | 0 | 388 | 100,00 % | 2,06 % | 4,04 % | 0,00 % | 67,35 % |
| Autoencoder | 0 | 194 | 55 | 333 | 0,00 % | 0,00 % | 0,00 % | 14,18 % | 57,22 % |

Quelle: drei `evaluation_*/scores.csv` unter `results/upright_v4_frozen_airflow_test_20260912_073015/`; unabhängig nachgezählt und mit `results/upright_v4_followup_closure_20260912/per_record_metrics.json`, `review_values.json` sowie `results/upright_v4_finalization_20260912_103145/controlled_state_descriptive_metrics.json` abgeglichen.

Die Klassenverteilung ist 194 positive zu 388 negativen Fenstern. Ein stets „normal“ ausgebendes Verfahren erreicht bereits 66,67 % Accuracy. RMS liegt um 1,03 Prozentpunkte, IF um 0,69 Prozentpunkte darüber; der AE liegt darunter. Diese Accuracy-Werte kompensieren die geringe Markierung des veränderten Zustands nicht. IF-Precision von 100 % bedeutet hier lediglich vier positive Entscheidungen ohne Fehlalarm innerhalb dieser Folge; 190 positive Fenster bleiben unmarkiert.

H1 wird durch den beobachteten Vergleich nicht gestützt: Der F1 des AE ist in dieser Folge um 6,93 Prozentpunkte niedriger als derjenige der RMS-Baseline. Daraus folgt kein allgemeiner Überlegenheitsnachweis für RMS. Die drei Verfahren sind auf den Fenstern gepaart, doch für den positiven Zustand existiert nur eine Aufnahme und nur eine vollständige Folge. Ein fensterweiser Signifikanztest oder ein zufälliges Fenster-Bootstrap würde diese geringe Zahl von Wiederholungen nicht ersetzen. Die Kennzahlen sind Zustandskennzahlen der vorliegenden Folge, keine belastbare Schätzung der Wiederholbarkeit oder eines allgemeinen Defekt-Recalls.

## Normalvariation, Referenzmischung und H3

Alle folgenden Zahlen sind Fehlalarme unter jeweils 194 gültigen Normalfenstern. Reihenfolge ist die Aufnahmefolge innerhalb der dokumentierten Gruppen; Training und Validierung sind nicht enthalten.

| Normalaufnahme | PWM | RMS | IF | AE |
|---|---:|---:|---:|---:|
| normal_test_01, 11.09. | 75 % | 57 (29,38 %) | 34 (17,53 %) | 0 (0,00 %) |
| normal_test_02, 11.09. | 75 % | 0 (0,00 %) | 0 (0,00 %) | 0 (0,00 %) |
| normal_test_03, 11.09. | 75 % | 0 (0,00 %) | 0 (0,00 %) | 0 (0,00 %) |
| normal_sep11 | 75 % | 2 (1,03 %) | 1 (0,52 %) | 9 (4,64 %) |
| normal_before, 12.09. | 75 % | 1 (0,52 %) | 0 (0,00 %) | 51 (26,29 %) |
| normal_after, 12.09. | 75 % | 0 (0,00 %) | 0 (0,00 %) | 4 (2,06 %) |
| normal_pwm50_01 | 50 % | 1 (0,52 %) | 0 (0,00 %) | 17 (8,76 %) |
| normal_pwm50_02 | 50 % | 2 (1,03 %) | 1 (0,52 %) | 11 (5,67 %) |
| normal_pwm50_03 | 50 % | 0 (0,00 %) | 0 (0,00 %) | 7 (3,61 %) |

| Methode | 75 %, sechs Aufnahmen | 50 %, drei Aufnahmen | Differenz 50 minus 75 |
|---|---:|---:|---:|
| RMS | 60/1.164 = 5,15464 % | 3/582 = 0,51546 % | −4,63918 Prozentpunkte |
| IF | 35/1.164 = 3,00687 % | 1/582 = 0,17182 % | −2,83505 Prozentpunkte |
| AE | 64/1.164 = 5,49828 % | 35/582 = 6,01375 % | +0,51546 Prozentpunkte |

Quellen: ursprüngliche Scoretabellen der ersten Normalserie, der normalen Einzelaufnahme vom 11.09., der vollständigen Plattenfolge und der drei 50-%-Starts; zusammengeführt in `results/upright_v4_second_pwm50_20260912_091000/comparison_50_vs_75/false_alarm_comparison.csv` und `all_scores.csv`. Das vor den 50-%-Aufnahmen fixierte `protocol.json` benennt bereits alle sechs 75-%-Referenzaufnahmen. Die Referenzen werden deshalb vollständig beibehalten.

Da alle Aufnahmen denselben Nenner 194 haben, entspricht die gepoolte FPR hier auch dem ungewichteten Mittel der Aufnahmeraten. Dennoch beschreibt sie eine Mischung sehr unterschiedlicher Starts. 57 der 60 RMS-Fehlalarme und 34 der 35 IF-Fehlalarme bei 75 % stammen aus dem ersten Normaltest. Beim AE stammen 51 der 64 Fehlalarme aus `normal_before` am 12.09. Die Methoden reagieren folglich auf verschiedene normale Starts empfindlich.

Die AE-FPR der drei 50-%-Aufnahmen liegt jeweils über den drei alarmfreien ersten 75-%-Tests und jeweils unter den 26,29 % der späteren 75-%-Aufnahme `normal_before`. Innerhalb der 50-%-Serie fällt sie von 8,76 % über 5,67 % auf 3,61 %. Somit existiert keine über sämtliche Aufnahmevergleiche konsistente Richtung. Die gepoolte Zunahme um 0,52 Prozentpunkte bleibt ein korrektes Ergebnis der vorab festgelegten Gesamtmischung; sie isoliert keinen stabilen oder kausalen Effekt der Stellvorgabe.

Die 50-%- und 75-%-Aufnahmen sind zeitlich getrennt, nicht randomisiert gepaart und stammen aus unterschiedlichen Startfolgen. Der PWM-Wechsel ist mit Zeit, Startgeschichte und anderen nicht vollständig kontrollierten Einflüssen verbunden. Eine gemessene Drehzahl ist nicht vorhanden. Weder eine allgemeine Verschlechterung bei geringerer PWM noch die gegenteilige kausale Behauptung ist gestützt. H3 wird als allgemeine gerichtete Aussage nicht bestätigt; der kleine gepoolte AE-Anstieg ist nur deskriptiv mit ihrer Richtung vereinbar. Keine Aufnahme darf zur Erzeugung einer günstigeren oder eindeutigeren Richtung nachträglich entfernt werden.

Die im JSON zusätzlich dokumentierten Minima, Maxima und Mediane sind eine Prüfung der Heterogenität, keine neue primäre Zielgröße und kein Ersatz des festgelegten Poolings. Es wurden keine alternativen Testauswahlen, angepassten Schwellen oder inferenziellen Vergleiche erzeugt.

## Laufzeit, Ressourcen und H2

Alle 18 archivierten Entscheidungsjournale wurden nachgezählt und gegen ihre gespeicherten Prüfsummen und `runtime_analysis/analysis.json` geprüft. Jede Datei enthält 194 gültige Entscheidungen. Die empirischen P99-Werte wurden ausschließlich aus den gespeicherten Latenzen mit linearer Interpolation nachvollzogen; sie stimmen mit dem Archiv überein. Auch die Schwellen und Entscheidungen stimmen mit dem eingefrorenen Paket überein.

| Betriebsart | Prozesse | gültige Entscheidungen | ungültig | Fristüberschreitungen |
|---|---:|---:|---:|---:|
| Sensor-Live | 9 = 3 je Methode | 1.746 | 0 | 0 |
| Offline-Replay | 9 = 3 je Methode | 1.746 | 0 | 0 |

Je Prozess werden zwar 300 s erfasst bzw. wiedergegeben, die aktive Modellbewertung umfasst 120 s. Im Sensor-Livebetrieb liegen sämtliche empirischen P99 unter dem je Prozess aus der Host-Zeitbasis abgeleiteten Fensterintervall. Damit ist die deskriptive Prüfbedingung von H2 im gemessenen Umfang erfüllt. Null Überschreitungen sind kein Beleg einer zukünftigen Überschreitungswahrscheinlichkeit von exakt null. Es werden deshalb weder eine harte Echtzeitgarantie noch ein aus unabhängigen Bernoulli-Versuchen abgeleitetes Konfidenzintervall behauptet.

Für CPU und RSS ist der Prozess die sinnvolle Vergleichseinheit: je Methode und Betriebsart drei Prozesse. Die vielen zeitlichen Ressourcenproben innerhalb eines Prozesses sind keine zusätzlichen unabhängigen Wiederholungen. Die Ressourcenwerte des Sensorbetriebs und des Replay müssen getrennt bleiben, weil die Replay-Implementierung die Quelldatei vorab im Speicher hält. Die jeweilige P99-Bandbreite über drei Prozesse ist eine Spannweite beobachteter Laufkennwerte, kein Konfidenzintervall. Ein einzelnes Prozess-P99 beruht auf nur 194 Entscheidungen und beschreibt entsprechend wenige Beobachtungen am oberen Rand.

Alle neun Replay-Prozesse verwenden dieselbe vorhandene physikalische Aufnahme. Sie vergrößern die Zahl der Softwarewiederholungen, nicht die Zahl unabhängiger physikalischer Testzustände. Die neun neuen Sensoraufnahmen laufen mit jeweils nur einer Methode und sind daher kein zusätzlicher gepaarter Erkennungsvergleich der drei Methoden auf gleichen Signalen. Ihre Alarme werden nicht nachträglich in die vorher festgelegten Erkennungsnenner eingemischt.

Der vorhandene Runtime-Bericht dokumentiert für 3.492 Scores die maximale Abweichung zum eingefrorenen Offlineweg als 0,0. Diese Prüfung wird als archivierter Befund übernommen; sie wurde hier nicht durch neue Inferenz wiederholt. Sie belegt numerische Konsistenz und keine fachliche Richtigkeit der Labels oder Erkennung. Host-Lesezeiten, die endliche Messdauer, der steigende RSS-Verlauf und nicht gemessene physikalische Verluste behalten ihre bestehenden Aussagegrenzen.

## Konkrete Formulierungen für das Manuskript

Die vorhandenen Absätze 266, 300, 338, 347 sowie 415–416 enthalten bereits die zentralen Einschränkungen. Zusätzliche Präzisierung ist vor allem bei H3, der Kalibrierungsstichprobe und der Bedeutung von Aufnahme/Fenster sinnvoll:

1. **Kalibrierung:** „Die eine normale Validierungsaufnahme wurde sowohl zur Bewertung des Autoencoder-Modellstands als auch zur Schwellenkalibrierung verwendet. Sie war vom späteren Test getrennt, bildete jedoch keine zusätzliche, von der gesamten Entwicklung unberührte Kalibrierungsstichprobe. Der dort beobachtete Alarmanteil von 2/194 ist daher kein unabhängiger Fehlalarmnachweis.“
2. **Auswertungseinheit:** „Die Kennzahlen werden nach vollständigen Aufnahmen gruppiert, beziehen sich aber jeweils nur auf die 194 vollständigen Modellfenster im vorab festgelegten Abschnitt [180,300) s. Die Fenster erhöhen die zeitliche Auflösung, ersetzen jedoch keine unabhängigen Wiederholungen des Versuchszustands.“
3. **H1:** „Für das kontrollierte Zustandslabel wird H1 in der einzigen vollständigen Testfolge nicht gestützt: Der Autoencoder erreicht einen F1 von 0 %, die RMS-Baseline 6,93 %. Das Ergebnis belegt weder eine allgemeine Überlegenheit der Baseline noch eine verlässliche Defekterkennung; für den positiven Zustand liegt nur eine Aufnahme vor.“
4. **H3/Referenzmischung:** „Der geringe gepoolte Anstieg der Autoencoder-FPR von 5,50 % auf 6,01 % beschreibt die festgelegte Mischung heterogener Starts. Die drei 50-%-Aufnahmen liegen oberhalb der drei alarmfreien ersten 75-%-Tests, zugleich aber unterhalb der späteren 75-%-Aufnahme mit 26,29 % Fehlalarmen. Damit zeigt sich keine über alle Aufnahmen konsistente Änderungsrichtung. Wegen der zeitlich getrennten, nicht randomisiert gepaarten Reihen wird H3 nicht allgemein oder kausal bestätigt.“
5. **IF:** „Der Isolation Forest verwendet den negierten `score_samples`-Wert und eine separat auf normalen Validierungsscores festgelegte P99-Schwelle. Seine `contamination`-Einstellung ist weder die verwendete Entscheidungsgrenze noch eine Garantie für eine spätere Fehlalarmrate.“
6. **H2:** „Die empirische P99-Bedingung von H2 ist in allen neun Sensorprozessen erfüllt; unter 1.746 gültigen Entscheidungen wurden keine Fristüberschreitungen beobachtet. Diese Aussage gilt für die gemessenen 120 s aktiver Modellverarbeitung je Prozess und begründet keine Zusage für zukünftige oder harte Echtzeitanforderungen.“

Für den Abschluss sind keine zusätzlichen p-Werte, zufälligen Fenster-Bootstraps oder vermeintlich engen Konfidenzintervalle erforderlich. Sie würden die fehlenden unabhängigen positiven Wiederholungen und die nicht kontrollierte Vergleichsstruktur nicht beheben. Die vorhandenen ungünstigen Entscheidungen und heterogenen Starts bleiben vollständig Teil des Ergebnisses.
