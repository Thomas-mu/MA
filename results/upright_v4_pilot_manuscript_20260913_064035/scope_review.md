# Unabhängige Prüfung des wissenschaftlichen Pilotumfangs

Stand: 13.09.2026. Grundlage ist die vor der Überarbeitung gesicherte Textfassung `input_readable.txt` im selben Verzeichnis; SHA-256: `2f0186bc080d254ff3ae965585b40ec7c48f758f2ec1dfe534832f896fa63a88`. Die unten genannten Blocknummern stammen aus dieser Fassung und bleiben deshalb auch dann eindeutig, wenn sich Absatz- oder Seitenzahlen der überarbeiteten Worddatei verschieben. Ergänzend gelesen wurden `review_thesis.md` und `followup_completion_report.md` im Abschlussverzeichnis vom 12.09.2026 sowie der archivierte Korrelationsbefund der explorativen Fehleranalyse. Dieser Review verändert ausschließlich die vorliegende neue Datei. Es wurden weder Hardwarebefehle noch Messungen, Modelltraining oder neue Modellentscheidungen ausgeführt.

## Urteil

Die vorhandene Untersuchung lässt sich als abgeschlossene, begrenzte Pilotstudie wissenschaftlich konsistent darstellen. Dazu müssen ihre nachgewiesenen Ergebnisse, negativen Hypothesenbefunde und verbleibenden Anforderungen sichtbar getrennt werden. Ein Abschluss mit begrenzter Aussagekraft ist keine nachträgliche Erfüllung der ursprünglich gesetzten MUSS-Anforderungen. Insbesondere bleiben A1 und A11 nur teilweise nachgewiesen; die in Kapitel 5 angekündigte tatsächliche Drehzahl wurde nicht erfasst.

Die schwache Erkennung ist ein gültiges Evaluationsergebnis. Für FF2/H1/A9 muss kein industrieller Defekt erzeugt werden: Das vorab festgelegte Label `airflow_modified` ist die positive Versuchsklasse. A11 verlangt dagegen tatsächlich Wiederholungen dieser Bedingung. Diese fehlende Wiederholung darf weder durch 194 Fenster noch durch die wiederholten Normalstarts ersetzt werden. Die Entscheidung, ohne zusätzliche Daten abzuschließen, lässt den Wiederholungsnachweis offen und muss dies ausdrücklich sagen.

Die bisherige Fassung enthält bereits viele passende Einschränkungen. Den deutlichsten verbliebenen Umfangswiderspruch bildet Block 280, der weiterhin eine nachgewiesene Defektklasse als offenen Nachweis aufzählt. Eine weitere echte Überdehnung ist die aus konstanter Stellvorgabe abgeleitete Unabhängigkeit des beobachteten physischen Betriebszustands vom untersuchten Verfahren in Block 237. Die übrigen Empfehlungen verbessern überwiegend die eindeutige Schlussfassung, ohne neue Pflichtaufgaben zu erzeugen.

## Konkrete Korrekturen und Ersatztexte

### 1. Abschlussstatus früh festlegen, ursprüngliche Ziele erhalten

**Fundstellen:** Kapitel 1.3–1.5, Blöcke 45–59; Kapitel 4, Blöcke 128–143; Kapitel 5, insbesondere Block 169.

FF1–FF4, H1–H3 und die Anforderungstabelle sollten inhaltlich erhalten bleiben. Die Arbeit darf das erreichte Untersuchungsniveau präzisieren, aber weder die fehlende Drehzahlmessung aus der ursprünglichen Konzeption streichen noch A11 auf bloße Protokollierbarkeit verkürzen. Die folgenden Sätze eignen sich als Ergänzung in Kapitel 1.5:

> Die Arbeit wird mit dem vorhandenen Datenstand als begrenzte Pilotstudie abgeschlossen. Sie bewertet das eingefrorene v4-Paket auf den dokumentierten unabhängigen Testaufnahmen; zusätzliche Messungen, Nachtraining und Nachkalibrierung sind nicht Bestandteil dieses Abschlusses. Die Forschungsfragen und Anforderungen aus der Konzeption bleiben der Bewertungsmaßstab. Nicht vollständig nachgewiesen sind insbesondere die physikalische Charakterisierung der Messkette und die Wiederholung der veränderten Versuchsklasse; die ursprünglich vorgesehene tatsächliche Drehzahl wurde nicht erfasst. Diese Lücken begrenzen die Aussagen und werden in Kapitel 7 einzeln ausgewiesen.

**Direkte Präzisierung von Block 169, ohne die Zielsetzung zu löschen:**

> Als konkrete Variante wurde der ARCTIC P12 Pro PST vorgesehen, dessen Datenblatt PWM-Ansteuerung und ein Drehzahlsignal ausweist (ARCTIC, o. J.). Ein PWM-Tastgrad ist eine Stellgröße und kein Nachweis einer konstanten Drehzahl. Die Konzeption sah deshalb die Erfassung der tatsächlichen Drehzahl vor. Dieser Nachweis wurde in der abgeschlossenen Pilotstudie nicht erbracht; die Betriebspunkte werden entsprechend durch ihre dokumentierten PWM-Vorgaben beschrieben. Für FF4 wurde ein zweiter normaler Betriebspunkt bei unveränderter Montage untersucht. Versuchszustand, Schutzmaßnahmen und Messablauf sind in Kapitel 6 dokumentiert; den begrenzten Nachweis der Rücksetzbarkeit bewertet Kapitel 7.

Das ist eine transparente Abweichung von der Konzeption, keine nachträgliche Erfüllung. Ähnlich sollte Kapitel 5.3 seine Signalqualitätsprüfung als geplanten Maßstab darstellen und direkt auf den Teilnachweis A1 verweisen.

### 2. Den unberechtigten offenen Defektnachweis entfernen

**Fundstelle:** Kapitel 6.7, Block 280: „Eine nachgewiesene Defektklasse […] gehören weiterhin zu den offenen Nachweisen.“

Diese Aussage widerspricht Kapitel 1.5, H1 und der bereits korrigierten FF2-Antwort. Eine allgemeine Defektklasse war keine notwendige Voraussetzung des begrenzten Methodenvergleichs. Die vorhandene veränderte Versuchsklasse darf zugleich nicht wegen ihrer schlechten Erkennung zurückgenommen werden.

**Ersatz für die letzten beiden Sätze des Absatzes:**

> Nicht vollständig nachgewiesen sind die physikalische Zeitbasis und nutzbare Bandbreite der Messkette sowie die Wiederholbarkeit der veränderten Versuchsklasse. Die ursprünglich vorgesehene unabhängige Drehzahlmessung fehlt. Kapitel 7 bewertet diese Lücken anhand der ursprünglichen Anforderungen; die erfolgreiche Programmausführung erfüllt nicht automatisch sämtliche MUSS-Anforderungen. Ein nachgewiesener Lüfterdefekt ist kein nachträglich eingeführtes Abschlusskriterium des vorab definierten Zustandsvergleichs.

Der letzte Satz kann entfallen, wenn die Abgrenzung unmittelbar davor oder in Kapitel 1.5 bereits eindeutig steht.

### 3. Keine Kausalität aus unveränderter PWM ableiten

**Fundstelle:** Kapitel 6.2, Block 237: „Damit hängt der beobachtete Betriebszustand nicht von dem jeweils untersuchten Verfahren ab.“

Belegt ist, dass Modellentscheidungen die Stellvorgabe nicht ändern. Damit ist kein identischer physischer Betriebszustand zwischen zeitlich getrennten Prozessen bewiesen. Laufreihenfolge, Zeit und weitere Einflüsse bleiben möglich; dies wird später korrekt beschrieben.

**Ersatz für die drei letzten Sätze des Absatzes:**

> Die Messläufe halten die vorgegebene PWM konstant. Modellentscheidungen verändern diese Stellvorgabe während des Methodenvergleichs nicht; eine Rückwirkung über die Ansteuerung ist damit ausgeschlossen. Ob die tatsächliche Drehzahl und weitere physikalische Bedingungen zwischen getrennten Läufen identisch waren, ist dadurch nicht nachgewiesen.

### 4. Vorwärtsformulierungen als ursprüngliche Methodik oder bedingten Ausblick kenntlich machen

**Fundstellen:** Blöcke 53, 105, 138, 169, 175–176, 207, 219–223, 385–391.

Nicht jede Formulierung „ist zu prüfen“ ist ein unerledigtes Arbeitsversprechen: Kapitel 4 definiert bewusst weiterhin gültige Anforderungen; Kapitel 5 begründet eine Auswahl vor der Evaluation. Diese Forderungen sind nicht pauschal zu löschen. In der Schlussfassung braucht dieser Aufbau jedoch eine klare zeitliche Einordnung.

**Ergänzung zu Beginn von Kapitel 5:**

> Dieses Kapitel rekonstruiert die Systementscheidung und die dabei festgelegten Prüfvorbehalte. Die Anforderungen beschreiben den ursprünglichen Zielmaßstab. Ob die jeweiligen Nachweise im vorhandenen Datenstand erbracht wurden, bewertet Kapitel 7; aus den hier genannten Prüfvorbehalten entstehen keine zusätzlichen Messungen innerhalb des abgeschlossenen Pilotumfangs.

**Block 53, Ersatz:**

> Die Arbeitshypothesen legen die Vergleichsgrößen fest. Bereits zur Entwicklung verwendete Daten werden explorativ ausgewertet. Die unabhängige Prüfung verwendet davon getrennte Testaufnahmen und ein vor ihrer Auswertung festgelegtes Versuchsprotokoll. Ihre Aussagekraft bleibt durch Zahl und Vielfalt der vollständigen Aufnahmen begrenzt.

**Block 105 und letzter Satz in Block 138, jeweils als bedingte Regel:**

> Eine spätere Nachkalibrierung wäre als eigener Versuch auszuwerten und ist nicht Bestandteil des hier abgeschlossenen Vergleichs.

**Kapitel 9, erster Absatz:**

> Der vorhandene Datenstand bildet den Abschluss dieser Pilotstudie. Die nachfolgenden Vorschläge betreffen mögliche Anschlussarbeiten und wurden hier nicht durchgeführt. Sie schließen die in Kapitel 7 ausgewiesenen Lücken nicht nachträglich. Das eingefrorene Paket und seine gemessenen Ergebnisse bleiben unverändert erhalten.

Die detaillierten Geräteanschluss- und Messanweisungen in Blöcken 386–389 können zugunsten einer fachlichen Frage mit geeignetem Nachweisweg gekürzt werden. Es ist kein verbindlicher Folgeauftrag nötig. Die frühere Planung im historischen `followup_completion_report.md` bleibt historisch erhalten; seine „zwei zusätzlichen vollständigen Plattenfolgen“ sind keine fachlich zwingende aktuelle Abschlussbedingung. Eine feste Zahl von zwei weiteren Folgen wäre außerdem kein allgemein hergeleiteter Reproduzierbarkeitsnachweis.

### 5. FF2/H1 unmittelbar bei den Hauptergebnissen sichtbar machen

**Fundstellen:** Kapitel 7.4, Blöcke 303–306; Kapitel 8.1, Block 373; Kapitel 10, Block 395.

Die bestehenden Kennzahlen sind rechnerisch konsistent. Im Hauptteil stehen sie bislang vor allem in Diskussion und Fazit; Kapitel 7.4 berichtet nur Alarmanteile. Folgender knapper Absatz unmittelbar nach Tabelle 7-3 verbindet die zentrale FF2 direkt mit dem Ergebnis:

> Für die vollständige Folge wird `airflow_modified` als vorab festgelegtes positives Zustandslabel ausgewertet. Auf denselben 582 gültigen Fenstern ergeben sich F1-Werte von 6,93 % für RMS, 4,04 % für Isolation Forest und 0 % für den Autoencoder. Die F1-Differenz des Autoencoders zur statistischen Baseline beträgt somit −6,93 Prozentpunkte; H1 ist in dieser Folge nicht bestätigt. Die vollständigen Konfusionszahlen und Kennzahlen stehen im Anhang. Die 194 positiven Fenster stammen aus einer einzigen Aufnahme und belegen keine Wiederholbarkeit des Ergebnisses.

Der Zustandslabel-Recall ist ein gültiger Recall für diese Versuchsdefinition. Er ist keine allgemeine Defekt-Sensitivität. Es wäre unnötig und missverständlich, ihn allein wegen fehlender Defekte als „nicht berechenbar“ darzustellen. Ebenso ist A9 kein Mindestgüteziel: Niedrige F1-Werte erfüllen die Aufgabe der Qualitätsbewertung, sofern Testbasis und Grenzen nachvollziehbar bleiben.

### 6. Statistische Aussagen auf ihre tatsächliche Einheit begrenzen

Die Trennung von Fenstern, Aufnahmen und Wiederholungen ist in Blöcken 88, 288, 300, 309 und 416 bereits korrekt. Es ist keine neue Signifikanzanalyse nötig; eine binomial berechnete Präzision mit 194 beziehungsweise 1.164 vermeintlich unabhängigen Replikaten wäre irreführend.

**Block 327, konkretisierte Korrelation:**

> In `normal_before` liegen 40 der 51 Autoencoder-Fehlalarme zwischen 180 und 240 s ab dem Stellbefehl. Über alle 194 Modellfenster dieser Aufnahme beträgt die explorative Pearson-Korrelation zwischen Autoencoder-Score und physischer X-Achsen-RMS ungefähr r = 0,821. Die Fenster sind zeitlich abhängig; der Koeffizient beschreibt diesen Verlauf und ist kein unabhängiger Kausalnachweis. Mit der Z-Achsen-RMS beträgt die entsprechende Korrelation nur rund 0,002.

Quelle des präzisierten Koeffizienten: `results/upright_v4_exploratory_diagnosis_20260912_081728/descriptive_correlations.json`; dort ist der Umfang ausdrücklich „same 194 windows; dependent observations, no p-values or causal claim“. Diese Präzisierung benötigt keine Neuberechnung.

**Block 324, Mittelwerte und Schwellenentscheidungen:**

Der aktuelle Übergang „kleinere mittlere X-/Y-Fehler; deshalb keine Überschreitung“ kann so gelesen werden, als folge die Zahl der Alarme aus dem Gruppenmittel allein. Präziser:

> Der mittlere Gesamtfehler ist das arithmetische Mittel der drei mittleren Achsenfehler. Die kleineren X- und Y-Fehler überkompensieren den mit Platte geringfügig höheren Z-Fehler. Zusätzlich zeigt die Prüfung der einzelnen Modellfenster, dass in dieser Aufnahme kein Gesamtfehler die eingefrorene Schwelle von rund 0,54436 überschreitet. Ein kleinerer Gruppenmittelwert allein würde diesen Nullbefund nicht belegen. Ein größerer physischer Vektor-RMS muss bei dieser Vorverarbeitung und diesem Modell keinen größeren Anomaliescore verursachen.

**Block 338, H3:**

> Gegenüber den sechs festgelegten 75-%-Normalaufnahmen verändert sich die zusammengefasste Fehlalarmrate bei 50 % PWM um −4,64 Prozentpunkte für RMS, −2,84 Prozentpunkte für Isolation Forest und +0,52 Prozentpunkte für den Autoencoder. Die Differenzen wurden aus den ungerundeten Zählwerten berechnet. Die von H3 erwartete Richtung zeigt sich damit deskriptiv nur beim Autoencoder. Für RMS und Isolation Forest ist sie in diesem Vergleich nicht bestätigt. Drei 50-%-Starts und sechs zeitlich getrennte 75-%-Normalaufnahmen erlauben weder eine allgemeine Bestätigung noch die isolierte kausale Zuordnung zum Tastgrad.

„Nicht untersucht“ oder eine pauschale Nichtbeantwortung von FF4 wäre falsch. Ebenso wäre eine allgemeine H3-Bestätigung allein aufgrund von +0,52 Prozentpunkten beim Autoencoder zu weitgehend.

## Empfohlene kompakte FF-/H-Statusmatrix

Die Tabelle eignet sich für das Fazit. Sie benötigt keine Änderung der ursprünglichen Fragestellungen oder Hypothesen.

| Bezug | Ergebnis im abgeschlossenen Pilotumfang | Schlussstatus und Grenze |
|---|---|---|
| FF1 | Anforderungen, Variantenvergleich und Umsetzung von ADXL345, Raspberry Pi 5 und drei Verfahren sind dokumentiert. | Konzeptionell beantwortet; vollständiger physikalischer Eignungsnachweis fehlt. A1/A11 bleiben teilweise nachgewiesen; tatsächliche Drehzahl nicht erfasst. |
| FF2 / H1 | Gleiche 582 Fenster einer Normal–Änderung–Normal-Folge: F1 RMS 6,93 %, IF 4,04 %, AE 0 %; AE minus RMS −6,93 Prozentpunkte. | FF2 für diesen Zustandsvergleich beantwortet; H1 in dieser Folge nicht bestätigt. Eine positive Aufnahme erlaubt keine allgemeine Wiederholbarkeitsaussage. |
| FF3 / H2 | Getrennte Sensor- und Replay-Prozesse je Methode; im Sensorbetrieb P99 höchstens 28,577 ms bei beobachtetem Fensterintervall mindestens 618,050 ms; 0 von 1.746 Sensorentscheidungen überschreiten die Frist. | FF3 für die dokumentierten Prozesse beantwortet; H2 im festgelegten Messumfang bestätigt. Hostbezogene Verarbeitungslatenz, keine Sensorwandlungs- oder harte Echtzeitgarantie. |
| FF4 / H3 | Sechs 75-%- und drei 50-%-Normalaufnahmen mit unverändertem Paket; FPR-Differenz RMS −4,64, IF −2,84, AE +0,52 Prozentpunkte. | FF4 deskriptiv beantwortet. Erwartete H3-Richtung nur beim AE beobachtet; bei RMS/IF nicht bestätigt. Keine allgemeine oder kausale Bestätigung. |

Achtet man auf kürzere Tabellenzellen, sollten mindestens Datenumfang, H1-negativer Befund, H2-Messgrenze und H3-Methodenspezifik erhalten bleiben.

## Empfohlener Endstatus A1–A13

Diese Einstufungen halten die ursprünglichen Anforderungen unverändert. „Nachgewiesen“ meint nur den explizit dokumentierten Umfang. Die Tabelle darf weder alle MUSS-Anforderungen als erfüllt zusammenfassen noch aus nicht bestätigten Hypothesen automatisch technische Nichterfüllungen ableiten.

| ID | Geeigneter Stand | Begründung und notwendige Grenze |
|---|---|---|
| A1 | Teilweise nachgewiesen | XYZ, Einheiten, Host-Zeitstempel, Qualitätsflags, Spektral- und Signalprüfung sind dokumentiert. Tatsächlicher Sensortakt, nutzbare physikalische Bandbreite und unbekannte physische Verluste bleiben nicht abschließend bestimmt. Die ursprünglichen Anforderungen an Signal-Rausch-Abstand und vorab festgelegte Akzeptanzgrenzen bleiben bestehen; vorhandene Signalanregung allein ersetzt sie nicht. |
| A2 | Im dokumentierten Umfang nachgewiesen | Ganze Aufnahmen getrennt; Normaldaten für Training/Kalibrierung; Scaler ausschließlich aus Trainingsdaten. |
| A3 | Im dokumentierten Umfang nachgewiesen | Identische Testfenster/Labels und gemeinsame Quantilregel. Unterschiedliche numerische Schwellen sind bei unterschiedlichen Scores kein Widerspruch. |
| A4 | Im dokumentierten Umfang nachgewiesen | Automatischer lokaler Sensorweg mit Entscheidungen und Qualitätsbehandlung. |
| A5 | Im dokumentierten Umfang nachgewiesen | Kennungen, Artefakthashes, Code-/Modell-/Softwarezuordnung und maschinenlesbare Daten vorhanden. Keine pauschale externe Reproduktion behaupten. |
| A6 | Im dokumentierten Umfang nachgewiesen | Ausführung und Konvertierungsvergleich; Live-/Offline-Konsistenz. Das ist ein numerischer Nachweis, kein allgemeiner Erkennungsbeleg. |
| A7 | Im dokumentierten Messumfang nachgewiesen | P99 unter beobachtetem Fensterintervall; keine Fristüberschreitungen. Die derzeitige Zelle „Siehe Abschnitt 7.7“ kann durch diesen eindeutigen Stand ersetzt werden. |
| A8 | Für die dokumentierten 300-s-Prozesse nachgewiesen | Kein Speicherabbruch oder wachsender Fensterrückstand; Modellbewertung jeweils nur im 120-s-Abschnitt [180,300). Positiven RSS-Verlauf ausweisen. Keine unbeschränkte Betriebsdauer oder speicherkonstante Ausführung behaupten. |
| A9 | Im festgelegten Pilotumfang nachgewiesen | Vollständige Kennzahlen der gemeinsamen Zwei-Klassen-Folge und Ergebnisse je Aufnahme vorhanden. Schwache Erkennung ist kein fehlender Evaluationsnachweis. Replikationslücke gehört zu A11. |
| A10 | Im dokumentierten Umfang nachgewiesen | Zweite vorab definierte Normalbedingung und unverändertes Paket geprüft. Der Vergleich belegt keine isolierte PWM-Kausalwirkung. |
| A11 | Teilweise nachgewiesen | Aufbau/Protokoll und Normalwiederholungen vorhanden; eine vollständige unabhängige Normal–Änderung–Normal-Folge. Wiederholungen der veränderten Bedingung fehlen. Wiederherstellung derselben Geometrie und gleicher Signalverteilung nicht gleichsetzen. |
| A12 | Optional; für das eingefrorene Paket nicht nachgewiesen | Der frühere GUI-Prototyp ist kein Nachweis von Integration oder Zusatzlast. Daraus entsteht keine offene Kernaufgabe. |
| A13 | Im dokumentierten Umfang nachgewiesen | Eindeutige Läufe, erhaltende Speicherung und geordnete Abschluss-/Fehlerpfade. Softwareseitige 0-%-Rücklesung ist keine mechanische Stillstandsmessung. |

Die tatsächliche Drehzahl besitzt keine eigene A-Nummer, ist aber in Kapitel 5.2 ausdrücklich vorgesehen. Sie ist als eigener nicht erbrachter Nachweis zu nennen und bei der Interpretation von A1, A10 und A11 mitzudenken. Eine Umdeutung von PWM in Drehzahl wäre unzulässig.

## Nachgeprüfte Zahlen und Grenzen des Reviews

Die in Tabellen A-2 und A-3 gespeicherten Zählwerte ergeben rechnerisch RMS-F1 6,930693 %, IF-F1 4,040404 % und AE-F1 0 %. Die angegebenen Precision-, Recall-, FPR- und Accuracy-Werte sind zu diesen Zahlen konsistent. Der stets normale Vergleich ergibt auf 388 normalen und 194 positiven Fenstern 66,666667 % Accuracy; die entsprechende Einordnung im Manuskript ist richtig. Die oben genannten FPR-Differenzen wurden nur aus den bereits angegebenen Zählwerten arithmetisch geprüft, nicht durch neue Modellbewertung erzeugt.

Die Ausgangsfassung weist keine unbegründeten p-Werte oder aus Fenstern gebildeten unabhängigen Konfidenzintervalle aus. Die Standardabweichung der 24 zeitlichen 5-s-Abschnitte wird korrekt von einem Standardfehler unabhängiger Versuche unterschieden. Nicht überlappende Bereiche zwischen Starts belegen weder einen Defekt noch eine ungeeignete Einlaufzeit. Die vorhandenen Formulierungen dazu sollten erhalten bleiben.

Dieser Review betrifft Umfang, Binnenkonsistenz und ausgewählte bereits dokumentierte Zahlen. Er bestätigt weder eine physikalische Messreferenz noch die Vollständigkeit aller Literaturquellen, persönliche Autorenschaft oder eine Prüfungsnote. Eine sehr gute Bewertung kann angestrebt werden; eine Note 1,0 ist aus einer technischen Dokumentprüfung nicht garantierbar.
