# Abschlussbericht: v4 Normal → Luftstromveränderung → Normal

**Die geplante Folge ist vollständig aufgenommen und ausgewertet.** Alle drei 300-s-Aufnahmen liegen separat vor. Bei der abschließenden Prüfung wurden 0 % PWM bei 25 kHz und die korrekte PWM-Pinfunktion zurückgelesen. Es ist kein weiterer Start vorgesehen. Der mechanische Stillstand nach dem letzten Lauf ist noch nicht durch eine Nutzerbeobachtung bestätigt.

## Ergebnis und Einordnung

Der mittlere physische Vektor-AC-RMS im vorab festgelegten Abschnitt [180,300) s beträgt 28,458 mg vor dem Einsetzen der Platte, 38,053 mg mit Platte und 32,074 mg nach dem Entfernen. Beide normalen Referenzen liegen im Mittel unter dem veränderten Zustand. Die Rückkehrreferenz bleibt jedoch um 3,616 mg beziehungsweise 12,707 % über dem ersten Normalmittelwert. Es ist daher eine Absenkung nach Entfernen der Platte belegt, keine vollständige Gleichheit mit dem ersten Normalzustand.

Die eingefrorenen Modelle zeigen keine zuverlässige Alarmreaktion auf diesen kontrolliert veränderten Zustand: RMS überschreitet die Schwelle in 7/194 Fenstern, Isolation Forest in 4/194 und der Autoencoder in 0/194. Gleichzeitig erzeugt der Autoencoder 51/194 beziehungsweise 4/194 Fehlalarme in den beiden normalen Referenzen. Das ist eine Einschränkung des geprüften Pilotpakets und bleibt als Ergebnis erhalten. Eine höhere physische RMS-Amplitude allein ist kein Nachweis erfolgreicher Modell- oder Defekterkennung.

## Aufbau, Trennung und vorab festgelegte Regeln

Aufbauversion `fan_upright_position_v4_20260911_103726`: aufrecht befestigter Lüfter, ADXL345 mit zwei Schrauben am feststehenden Rahmen, Platine schräg. Sichere, unveränderte Aufstellung und Sensorbefestigung wurden aus den Nutzerbestätigungen übernommen. Die Platte wurde gemäß aktueller Nutzerangabe separat und kippsicher, kontaktfrei, parallel und mittig 100 mm vor dem Luftauslass angebracht: 120 × 120 mm; Abstand von Auslass-Rahmenebene zur nächsten Plattenfläche. Das sind Nutzerangaben, keine unabhängige Vermessung. Der tatsächliche Auslass wurde zuvor ausdrücklich bestätigt; eine eigene Prüfung eines Gehäusepfeils wird nicht behauptet.

Vor jedem Start lag die aktuelle Freigabe bei bestätigtem Stillstand und angeschlossener Versorgung vor. Die manuellen Umbauten wurden entsprechend der vom Nutzer bestätigten Anleitung bei getrennter 12-V-Versorgung und vollständigem Stillstand durchgeführt; ausschließlich die Platte sollte bewegt werden. Es wurde keine sichtbare Laufbeobachtung während einer Aufnahme angefordert oder angenommen. Tatsächliche Drehzahl und elektrische PWM-Wellenform wurden nicht gemessen.

Sensor und Stellvorgabe blieben unverändert: ADXL345, nominell 200 Hz, ±2 g, volle Auflösung, 0,0039 g/LSB, FIFO-Stream, I²C-Bus 1 bei konfigurierten 100 kHz; 75 % PWM bei 25 kHz. BCM-GPIO18 ist physischer Pin 12; Hardware-PWM a3/PWM0_CHAN2, Periode 40.000 ns, Betriebsimpulsdauer 30.000 ns. Die Pin-Funktion war vor und nach allen drei heutigen Aufnahmen korrekt. Der frühere Fehler bleibt separat dokumentiert; sein damaliger Verursacher ist dadurch nicht geklärt.

Der vollständige Anlauf wurde gespeichert. Bewertet wurde ausschließlich [180,300) s ab Stellbefehlsaufruf, je 128 XYZ-Punkte, Schrittweite 128, ohne Überlappung und ohne Fenster über Aufnahmegrenzen. Je Fenster und Achse: Mittelwertentfernung in Float64, danach Float32 und Anwendung des gespeicherten Scalers. Alle Methoden erhielten dieselben geprüften Fenster. Paket, Modelle, Skalierung, Schwellen und Abschnittsauswahl blieben unverändert. Die unveränderte Implementierung ist durch die archivierten 166 Softwaretests und Hashprüfung belegt; diese Tests wurden für die heutigen Hardwarephasen nicht erneut als neue Testausführung ausgegeben.

Die neue Folge besitzt ein eigenes Protokoll und einen Ausschlussbestand mit 258 früheren CSV-Dateien einschließlich Training, Validierung und vorheriger Tests. Die unterbrochene Folge vom Vortag wurde nicht fortgeschrieben oder als heutige Normalreferenz verwendet. Jede aktuelle Rohaufnahme wurde gegen diesen Bestand geprüft.

## Zeitpunkte, Versatz und Auszeiten

Zeitangaben in der folgenden Tabelle sind Ortszeit Europe/Berlin am 12.09.2026 (UTC+2). Rohjournale speichern UTC und monotone Hostzeit. Die protokollierte Freigabeannahme ist nicht als exakter Nachrichtensendezeitpunkt zu verstehen.

| Phase | 75-%-Befehlsaufruf | Erster XYZ-Punkt nach Aufruf / s | Nach Befehlsabschluss / s | Erste bis letzte Probe / s | Zusätzliche Auszeit / s | Seit vorherigem 0-%-Befehlsabschluss / s |
|---|---|---:|---:|---:|---:|---:|
| normal_before | 09:38:23.502252 | 0.095444 | 0.046579 | 299.989994 | 60.025137 | unbekannt |
| airflow_modified | 09:48:45.339029 | 0.097458 | 0.048458 | 299.991595 | 60.022426 | 321.440292 |
| normal_after | 09:57:15.150608 | 0.092900 | 0.048338 | 299.989904 | 60.032063 | 209.412212 |

Je 60 s zusätzliche Auszeit bedeuten keine identische gesamte Auszeit. Die gesamte erste Auszeit über Nacht und während der Versorgungstrennung ist unbekannt. Die späteren Gesamtdauern messen den Abstand zweier protokollierter Stellbefehle, keine genaue mechanische Stillstands- oder Abkühlzeit. Unterschiedliche thermische Vorgeschichte und zeitliche Normalvariabilität sind mögliche Einflussgrößen; ihre tatsächlichen Beiträge wurden hier nicht gemessen.

## Datenqualität

| Phase | XYZ / Achsenwerte | Beobachteter Durchsatz / XYZ/s | Hostabstand Median / P99 / Max. in ms | >10 ms / >160 ms | FIFO max. | Lücke / Überlauf / Sättigung |
|---|---:|---:|---|---:|---:|---:|
| normal_before | 62140 / 186420 | 207.136909 | 5.588826 / 5.694864 / 13.437473 | 1 / 0 | 2 | 0 / 0 / 0 |
| airflow_modified | 62121 / 186363 | 207.072468 | 5.583385 / 5.689257 / 8.172495 | 0 / 0 | 1 | 0 / 0 / 0 |
| normal_after | 62105 / 186315 | 207.020301 | 5.586851 / 5.692289 / 8.060022 | 0 / 0 | 1 | 0 / 0 / 0 |

Alle drei Aufnahmen haben monotone und konsistente Hostzeitstempel sowie durchgehende gespeicherte Sample-Indizes. Nichtendliche XYZ-Punkte und gesetzte Qualitätsflags: jeweils 0. Alle Aufnahmen erfüllen die vorab festgelegten Qualitätskriterien. Ein Host-Abstand über 10 ms im ersten Normallauf ist allein kein Beleg für Datenverlust. Physische Verluste bleiben exakt unbekannt; das Fehlen von Flags beweist nicht ihre Abwesenheit. Host-Zeitstempel beschreiben Leseabschlüsse und keine unmittelbar gemessene Sensorwandlungszeit. Die beobachteten 207,020–207,137 XYZ/s bleiben von den nominellen 200 Hz getrennt; es erfolgten keine Zeitneuskalierung und kein Resampling.

## Modellvergleich

| Phase | Methode | Gültige / ungültige Fenster | Alarme | Anteil gültiger Fenster |
|---|---|---:|---:|---:|
| normal_before | RMS | 194 / 0 | 1 | 0.515 % |
| normal_before | Isolation Forest | 194 / 0 | 0 | 0.000 % |
| normal_before | TFLite-Autoencoder | 194 / 0 | 51 | 26.289 % |
| airflow_modified | RMS | 194 / 0 | 7 | 3.608 % |
| airflow_modified | Isolation Forest | 194 / 0 | 4 | 2.062 % |
| airflow_modified | TFLite-Autoencoder | 194 / 0 | 0 | 0.000 % |
| normal_after | RMS | 194 / 0 | 0 | 0.000 % |
| normal_after | Isolation Forest | 194 / 0 | 0 | 0.000 % |
| normal_after | TFLite-Autoencoder | 194 / 0 | 4 | 2.062 % |

In den beiden Normalreferenzen sind zusammen 388 Fenster pro Methode gültig: RMS 1/388 Fehlalarme (0,258 %), Isolation Forest 0/388 (0 %), Autoencoder 55/388 (14,175 %). Diese gepoolten Zählwerte ersetzen nicht die getrennten Ergebnisse der beiden vollständigen Aufnahmen. Der Autoencoder zeigt deutliche Unterschiede zwischen normalen Starts.

Die jeweiligen Restpunkte nach vollständigen 128er-Fenstern betragen 22, 17 und 8; sie bleiben in den Rohdaten und wurden nicht aufgefüllt. Ungültige Fenster würden nicht als NORMAL und nicht im Nenner gültiger Fenster zählen. Die Plattenalarmanteile sind keine Defekt-Recall-Werte: Der veränderte Luftstrom ist ein kontrollierter Betriebszustand, kein nachgewiesener Defekt. Es werden keine F1-Werte oder allgemeine Erkennungsleistungen abgeleitet.

![Scoreverläufe mit eingefrorenen Schwellen](comparison_complete/scores.png)

## Physischer Vektor-AC-RMS, Zeitverlauf und Rückkehr

Je aufeinanderfolgendem 5-s-Abschnitt wurden die drei Achsenmittelwerte in Float64 entfernt. Danach wurde sqrt(mean(ax_ac² + ay_ac² + az_ac²)) berechnet. Dieser Wert in mg ist vom standardisierten RMS-Modellscore zu unterscheiden. Je Aufnahme sind alle 60 vollständigen Zeitabschnitte und die 24 späten Abschnitte gültig; der erste Abschnitt enthält die dokumentierte kurze Verzögerung bis zum ersten XYZ-Punkt.

| Phase, Abschnitt 180–300 s | Mittel / mg | SD der 5-s-Werte / mg | Min.–Max. / mg | Lineare Steigung / mg/min | Zweite minus erste Minute / mg |
|---|---:|---:|---|---:|---:|
| normal_before | 28.458001 | 1.618381 | 26.592935–33.214155 | -0.706648 | +0.046258 |
| airflow_modified | 38.052535 | 1.299051 | 36.386318–41.675628 | -0.902973 | -0.295580 |
| normal_after | 32.074148 | 2.780943 | 26.865738–35.349413 | -0.543822 | +0.407983 |

Die Verläufe sind nicht durch eine einzige lineare Steigung hinreichend beschrieben. Im ersten Normallauf sinkt das Niveau nach der Anlaufspitze deutlich. Im Plattenlauf steigt es nach einem anfänglichen Abfall wieder an. Die Rückkehrreferenz zeigt auch spät deutliche Wechsel zwischen höheren und niedrigeren Abschnitten; die negative lineare Steigung und die positive Differenz der beiden späten Minuten zeigen, dass kein gleichmäßiger monotoner Verlauf vorliegt. Solche Änderungen innerhalb eines Laufs sind von unterschiedlichen Mittelwerten zwischen Starts zu trennen. 180 s bleiben der unverändert geprüfte Einlaufkandidat, keine nachgewiesene allgemeine Stabilisierungszeit; eine vollkommen konstante RMS-Kurve ist kein notwendiges Normalitätskriterium.

Der Plattenmittelwert liegt 9,595 mg über der ersten und 5,978 mg über der zweiten Normalreferenz. Die beobachteten späten Plattenwerte (36,386–41,676 mg) überlappen die beiden Normalbereiche (zusammen 26,593–35,349 mg) nicht. Der kleinste Abstand dieser Bereiche beträgt aber nur etwa 1,037 mg. Die Mittelwertunterschiede sind größer als die jeweilige innerhalb der Aufnahmen beobachtete Standardabweichung, jedoch nicht beide größer als die gesamte beobachtete normale Spannweite von 8,756 mg. Eine allgemeine Trennreserve gegen normale Variabilität ist damit nicht gesichert.

Nach Entfernen der Platte liegt der Normalmittelwert zwar innerhalb des ersten beobachteten 5-s-Normalbereichs, aber nur 13 von 24 Rückkehrabschnitten liegen darin. Der Mittelwert bleibt 12,707 % höher. Das belegt eine Rückbewegung zu niedrigeren Werten, keine statistisch gesicherte Äquivalenz. Beobachtete Minima und Maxima sind keine Konfidenzintervalle oder Akzeptanzgrenzen. Weder eine Bereichsüberlappung noch deren Fehlen beweist für sich die Eignung oder Uneignung der 180-s-Grenze.

![Vollständige Verläufe und späte 5-s-Abschnitte](comparison_complete/rms_5s.png)

## Empfehlung und verbleibende Grenzen

Die Messkette liefert für diesen Pilot auswertbare Rohdaten und einen sichtbaren Unterschied zwischen den kontrollierten Zuständen. Das eingefrorene Modellpaket bildet diesen Unterschied als Alarmentscheidung jedoch nur schwach ab; insbesondere ist die Autoencoder-Reaktion gegenüber dem Plattenzustand nicht stärker als gegenüber normalem Betrieb. Die Testergebnisse werden nicht zur nachträglichen Veränderung von Schwellen, Skalierung oder Abschnittsauswahl verwendet.

**Nächster konkreter Schritt ohne neuen Hardwareeingriff:** die bereits gespeicherten drei Aufnahmen getrennt nach Achsenbeiträgen und Frequenzanteilen sowie den eingefrorenen Scores untersuchen. Die konkrete offene Frage ist, warum das physische Vibrationsniveau mit Platte steigt, während insbesondere der Autoencoder-Fehler sinkt. Dabei können Gewichtsanteile durch den Scaler und Signalstruktur des vorhandenen Materials beschrieben werden; eine Ursache darf erst mit entsprechendem Befund benannt werden. Noch keine neue Modellversion und kein Nachtraining.

Für die physische Wiederholbarkeit wäre anschließend die kleinste gezielte Ergänzung eine zweite vorab dokumentierte vollständige Normal–Platte–Normal-Folge bei unveränderter Geometrie. Sie prüft, ob der RMS-Unterschied mit Platte und die unvollständige Rückkehr wieder auftreten; sie dient nicht dem Erzwingen einer konstanten Normal-RMS-Kurve. Auch zwei Folgen wären noch kein belastbarer allgemeiner Nachweis. Falls eine spätere Modelländerung begründet wird, benötigt sie ein neues Modellpaket und neue unabhängige Tests; diese Pilotdaten dürfen dann nicht zugleich als unabhängiger Erfolgsnachweis dienen.

Dieser Bericht behauptet weder allgemeine Reproduzierbarkeit noch erfolgreiche Defekterkennung. Alle Fenster innerhalb einer Aufnahme sind abhängig; drei Zustandsaufnahmen sind eine einzelne Folge und keine drei unabhängigen Wiederholungen derselben Behandlung. Eine feste Reihenfolge, unterschiedliche gesamte Auszeiten und fehlende Temperatur-/Drehzahlmessungen begrenzen die kausale Zuordnung. Frühere Daten anderer Aufbauversionen werden nicht als gemeinsame Normalreferenz verwendet.

## Integrität und Abschluss

Die 1291 geschützten bisherigen Dateien sowie alle vor dem letzten Lauf vorhandenen Dateien dieser Folge sind unverändert. Das schließt Worddatei, Modelle, frühere Messdaten und historische Berichte ein. Der eingefrorene Protokollhash lautet `5375fda6aff23f8f3c7651ac25e638a0dbbfbb52b49a33611e528bade3644a5d`, der Paket-Hash `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`. Modelle, Scaler und Schwellen wurden nicht verändert. [Abschließende Prüfung](final_complete_verification.json).

Die Sitzungsdateien dokumentieren Stellbefehle, Rücklesewerte, Aufnahme-IDs und vollständige Zeitpunkte. Quelle, Metadaten, Auswertung und Grafiken sind durch SHA256 verknüpft. Es gab in dieser Folge keine automatischen Wiederholungsstarts. Die letzte Vorgabe beträgt 0 % bei 25 kHz; nach Abschluss ist kein weiterer Start vorgesehen. Mechanischer Stillstand wird ohne Sichtbestätigung nicht behauptet.

[Maschinenlesbarer Gesamtvergleich](comparison_complete/comparison.json) · [Vergleichstabelle als CSV](comparison_complete/comparison.csv) · [Normal vorher](evaluation_normal_before/summary.json) · [Plattenlauf](evaluation_airflow_modified/summary.json) · [Normal nachher](evaluation_normal_after/summary.json)
