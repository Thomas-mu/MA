# Unabhängige fachliche Konsistenzprüfung der Abschlussfassung

Stand: 12.09.2026. Geprüft wurde die Wordfassung mit SHA-256 `fc92abeb7893f391f3df6b10dea06921dd76425bc3645e9c8da6b4eb8b8b8d8d` gegen die Textfassung der ursprünglichen Kapitel 1–5, das fertig eingesetzte Manuskript der Kapitel 6–10, die Layoutprüfung und ausgewählte digitale Ergebnisdateien. Es wurden keine Hardwarebefehle ausgeführt, keine Aufnahme gestartet, keine Inferenz neu ausgeführt und keine bestehende Datei geändert. Dieser Bericht ist eine technische und fachliche Konsistenzprüfung; er ersetzt weder eine eigene Autorenprüfung noch eine Betreuerfreigabe.

## Urteil

Die zentralen Zahlen und die Unterscheidung zwischen korrekter Softwareausführung, beobachteter Zustandserkennung und begrenzter Übertragbarkeit sind nachvollziehbar. Es gibt keinen Anlass, schlechte Erkennungsergebnisse zu korrigieren, das eingefrorene Paket zu verändern oder zum Berichtsschluss unbedingt echte Defekte zu erzeugen. Die wesentliche fachliche Korrektur betrifft den gegenüber Kapitel 1–5 teilweise zu stark erweiterten Anspruch eines allgemeinen Defektnachweises. Daneben sind eine nicht eingelöste Ankündigung und eine unklare Zuordnung von Zielanwendung und Literaturprüfstand zu bereinigen.

## Notwendige Korrekturen

### K1 – Ursprünglichen Untersuchungsumfang korrekt wiedergeben

**Fundstellen:** Kapitel 1.4–1.5; Kapitel 7.8/Tabelle 7-9, Zeile A9; Kapitel 8.1; Kapitel 10, Absatz zu FF2. Im ergänzten Manuskript insbesondere Zeilen 343, 357 und 401.

FF2 verlangt Kennzahlen auf gleichen Testfenstern. H1 lautet, dass das neuronale Verfahren bei den **definierten Versuchsanomalien** einen höheren F1-Wert als die statistische Baseline erreicht. Kapitel 1.5 begrenzt die Aussagen ausdrücklich auf die untersuchten Bedingungen und definierten Anomalien und schließt gesicherte Schadensdiagnose und Restlebensdauerprognose aus. Kapitel 5.2 grenzt konkrete Lagerfehler vom Kernvergleich ab.

Die Formulierung in Kapitel 10, „Der ursprünglich angestrebte umfassende Defektvergleich bleibt ein Teilnachweis“, gibt diesen ursprünglichen Umfang daher nicht zutreffend wieder. Ebenso ist das Fehlen einer allgemeinen Defektleistung allein kein Nachweis, dass die Kennzahlenanforderung A9 unerfüllt wäre. A9 enthält kein Mindestgüteziel: Auch eine sehr geringe Erkennung bewertet die Erkennungsqualität. Die Replikationsfrage ist in erster Linie A11 zuzuordnen.

**Vorgeschlagene Ersatzformulierung für FF2:**

> FF2 wird für den vorab definierten kontrolliert veränderten Betriebszustand durch die Kennzahlen auf identischen Testfenstern beantwortet. In der untersuchten Folge beträgt der F1-Wert 6,93 % für RMS, 4,04 % für Isolation Forest und 0 % für den Autoencoder. H1 ist in dieser Folge nicht bestätigt. Die eine veränderte Aufnahme begrenzt die Aussage über Wiederholbarkeit und Übertragbarkeit; ein Defekt wurde weder als notwendige Voraussetzung dieser Pilotbewertung verlangt noch durch die Platte nachgewiesen.

**Vorgeschlagene A9-Fassung:** „Kennzahlen im festgelegten Pilotumfang berechnet; Konfusionszahlen, Precision, Recall, F1, Fehlalarmrate und Accuracy auf derselben vollständigen Folge. Einzelaufnahme und zeitabhängige Fenster begrenzen die Übertragbarkeit. Die Wiederholung der veränderten Bedingung bleibt unter A11 offen.“ Falls der Nachweis „Ergebnisse je Aufnahme“ vollständig tabellarisch ausgeführt werden soll, sind die je Aufnahme definierbaren Kennzahlen aus vorhandenen Entscheidungen zu ergänzen; Recall ohne positive Fälle und Precision ohne positive Vorhersagen bleiben nicht definiert. Hierfür sind keine neue Messung und kein Nachtraining erforderlich.

Das Label `airflow_modified` ist vorab vergeben und darf für deskriptive Zustandskennzahlen verwendet werden. Die bereits klare Bezeichnung „kontrolliert veränderter Betriebszustand, kein nachgewiesener Defekt“ soll erhalten bleiben. Der Wechsel der Bezeichnung darf nicht den Eindruck erzeugen, die positive Versuchsklasse werde nach dem schlechten Ergebnis zurückgenommen.

### K2 – Nicht durchgeführte Nachkalibrierung nicht als Teil des abgeschlossenen Umfangs ankündigen

**Fundstellen:** Kapitel 1.5: „Eine ergänzende Nachkalibrierung wird gesondert ausgewertet.“ Kapitel 2.8: „Eine anschließende Nachkalibrierung ist als eigener Versuch auszuwerten.“ Kapitel 4.3 enthält ebenfalls die methodische Trennung.

Eine ergänzende Nachkalibrierung wurde tatsächlich nicht durchgeführt; die unabhängigen Tests verwendeten unveränderte Schwellen. Die verbindliche Ankündigung in Kapitel 1.5 passt somit nicht zum Abschluss. Die bedingte methodische Aussage in Kapitel 2.8 kann dagegen bestehen bleiben, wenn sie eindeutig hypothetisch ist.

**Vorschlag für Kapitel 1.5:** „Eine mögliche spätere Nachkalibrierung wäre als eigener Versuch auszuwerten. Sie ist nicht Bestandteil des hier abgeschlossenen eingefrorenen Vergleichs.“

Das ist eine redaktionelle Klarstellung des realen Umfangs, kein Anlass, jetzt zur Erfüllung einer unbedingten Zukunftsformulierung Schwellen an Testdaten anzupassen. Änderungen an den bislang bewusst erhaltenen Kapiteln 1–5 müssen transparent mit neuer Ausgangskopie und Änderungsnachweis erfolgen; historische Fassungen bleiben erhalten.

### K3 – Zielanwendung und Literaturprüfstand ausdrücklich unterscheiden

**Fundstellen:** Kapitel 3.2 beschreibt Antonini et al. (2023) als ESP32-Sensorknoten für Pumpenüberwachung. Tabelle 3-1 bezeichnet die Daten derselben Arbeit als Lüfterprüfstand. Nach Prüfung der Originalpublikation sind beide Angaben sachlich miteinander vereinbar, aber bislang nicht ausreichend aufeinander bezogen: Abschnitt 4 beschreibt einen gefederten PC-Lüfter als Versuchsaufbau für die zur Pumpenüberwachung entwickelte Platine. Abschnitt 5.1 grenzt Erkennungsgenauigkeit aus; 5.2 setzt Normalbetrieb für das Training voraus. Es liegt somit keine falsche Hardwareangabe vor, sondern eine zu erläuternde Unterscheidung von Zielanwendung und tatsächlichem Evaluationsaufbau. [Antonini et al. (2023), Abschnitte 4, 5.1 und 5.2](https://doi.org/10.3390/s23042344).

**Vorschlag Kapitel 3.2:**

> Antonini et al. (2023) entwickeln einen ESP32-Sensorknoten für die Überwachung von Unterwasserpumpen. Die Evaluation erfolgt an einer Platine auf einem gefederten PC-Lüfterprüfstand. Merkmalsbildung, Isolation-Forest-Training und Inferenz laufen lokal; das Training setzt normalen Betrieb voraus. Die Ressourcenmessungen unterscheiden Laden, Training und Inferenz. Die Erkennungsgenauigkeit wird nicht bewertet.

**Vorschlag Tabelle 3-1, Spalte Daten/Lernaufgabe:** „Unterwasserpumpe als Zielanwendung; Evaluation am gefederten Lüfterprüfstand; Isolation Forest mit Normaltraining“.

Der am 12.09.2026 geprüfte Originalvolltext wurde über den [Europe-PMC-Volltextzugang](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9962960/fullTextXML) gelesen und separat als `antonini_primary_fulltext.xml` erhalten. Die Word-/Literaturfassung wurde hier nicht geändert.

## Anforderungen und Hypothesen: fachliche Einordnung

| Bezug | Belegter Stand | Konsequenz für den Abschluss |
|---|---|---|
| FF1/A1 | Auswahl und Implementierung dokumentiert; nominelle ODR, Host-Durchsatz und Qualitätsflags geprüft | Teilnachweis der physikalischen Messkette korrekt. Nutzbare Bandbreite und unabhängiger Sensortakt bleiben offen; ein lesbarer Registerwert schließt diese Lücke nicht. |
| FF2/H1/A9 | Gleiche eingefrorene Fenster und Regeln; gültige Zustandskennzahlen, schwache Trennung | Negatives Erkennungsergebnis ist gültige Evaluation. Kein garantierter Erfolg und kein allgemeiner Defektnachweis geschuldet. H1 in der einzelnen definierten Folge nicht bestätigt. |
| FF3/H2/A7 | Endliche Sensor-/Replay-Laufzeitprüfung; P99 unter beobachtetem Fensterintervall | „Im dokumentierten Messumfang bestätigt“ ist angemessen. Nicht zu harter Echtzeit oder Sensorwandlungs-zu-Entscheidungslatenz ausweiten. |
| A8 | 300-s-Läufe ohne Abbruch oder steigenden Fensterrückstand; kleiner positiver RSS-Verlauf | Endlicher Betriebsnachweis vorhanden. Kein belegtes unbegrenztes Speicherwachstum, aber auch kein allgemeiner Dauerbetriebsnachweis. |
| FF4/H3/A10 | Drei 50-%-Normalaufnahmen, sechs fest zugeordnete 75-%-Normalaufnahmen, Paket unverändert | Vergleich beantwortet den beobachteten Unterschied. RMS/IF widersprechen der erwarteten Zunahme, AE zeigt sie deskriptiv schwach. Keine isolierte Kausalwirkung oder pauschale Bestätigung. |
| A11 | Normalstarts wiederholt; eine unabhängige veränderte Folge; mechanischer Zustand nach Umbau freigegeben | Wiederholung der veränderten Bedingung und belastbarere Rücksetzbarkeitsprüfung offen. Unterschiedliche Normalmittelwerte allein belegen keine mechanisch misslungene Rücksetzung. |
| A12 | Alte Oberfläche, neues Paket ohne GUI geprüft | Optionaler Umfang; keine zwingende offene Kernaufgabe daraus ableiten. |
| Drehzahl | In Kapitel 5.2 ausdrücklich zu erfassen, tatsächlich ungemessen | Anders als allgemeine Defektdiagnose eine konkret benannte physikalische Nachweislücke. Nur mit bestätigter Signalanbindung oder unabhängiger Referenzmessung schließen. |

Die Rolle von 180 s wird korrekt als vorab festgelegter Prüfkandidat beschrieben. Eine vollkommen konstante RMS-Kurve ist nicht verlangt. Nicht überlappende Bereiche zwischen Starts widerlegen keine geeignete Einlaufzeit. Für A11 sollte die Formulierung „keine vollständige Rückkehr zum vorigen Mittelwert“ als deskriptiver Befund erscheinen, nicht als zwingendes Kriterium einer wiederhergestellten mechanischen Anordnung. Die einseitige Lage einer einzigen Folge kann Rücksetz-, Zeit- und Startvariabilität nicht vollständig trennen.

## Unabhängig nachgezählte digitale Befunde

Die Auswertung liest bereits gespeicherte Entscheidungen; sie trainiert oder bewertet kein Modell neu. Die für diesen Review geprüften Eingangsdateien, deren Hashes und Zählungen stehen in [review_values.json](review_values.json).

| Zustand der abgeschlossenen Folge | Gültige Fenster je Methode | RMS-Alarme | IF-Alarme | AE-Alarme |
|---|---:|---:|---:|---:|
| normal_before | 194 | 1 | 0 | 51 |
| airflow_modified | 194 | 7 | 4 | 0 |
| normal_after | 194 | 0 | 0 | 4 |

Alle drei Methoden verwenden in jeder Aufnahme dieselben vollständigen Quellindexpaare. Keine ungültigen Fenster sind in diesen ausgewerteten Abschnitten enthalten. Die Gesamtzahlen der Zustandsfolge ergeben RMS (TP=7, FN=187, FP=1, TN=387), IF (4,190,0,388) und AE (0,194,55,333). Die Tabellen A-2/A-3 und die gerundeten F1-Werte sind rechnerisch konsistent.

Im maschinenlesbaren Laufzeitabschluss stehen 18 vollständige Prozesse, davon neun Sensorprozesse mit zusammen 559.130 XYZ-Punkten. Insgesamt sind 3.492 Scores mit der eingefrorenen Referenz verglichen; gespeicherte maximale Abweichung 0,0 und keine ungültige Entscheidung. Die beobachtete Sensorrate liegt zwischen 207,077267 und 207,103048 XYZ/s, der erste Punkt 81,215–97,750 ms nach dem Stellbefehl. Diese Angaben stimmen mit Kapitel 7.7 überein. Die erneute Zahlenprüfung stellt keine unabhängige physikalische Sensortaktmessung dar.

Die Befunde der explorativen Fehleranalyse sind angemessen begrenzt: Achsenskalierung, geringere X-/Y-Rekonstruktionsfehler, Fehlalarmhäufung und marginale Merkmalsüberlappung erklären mathematische Scoreeigenschaften. Daraus wird keine gemessene mechanische Ursache abgeleitet. Die Unterscheidung zwischen physikalischem 5-s-RMS und standardisierten 128er-Modellscores wird durchgängig eingehalten.

## Optionale Verbesserungen

1. Eine kurze gemeinsame FF1–FF4/H1–H3-Abschlusstabelle würde den fachlichen Umfang besser sichtbar machen. Besonders H1 und H3 sollten „nicht bestätigt“ beziehungsweise „methodenspezifischer deskriptiver Befund“ von „nicht untersucht“ trennen.
2. Tabelle 7-9 könnte A7 direkt als „im dokumentierten Umfang nachgewiesen“ und A8 als „für die dokumentierten 300-s-Prozesse nachgewiesen“ bezeichnen. Der jetzige Verweis beziehungsweise „geprüft“ ist unnötig unbestimmt, obwohl die positiven endlichen Befunde vorliegen.
3. A9-Kennzahlen der veränderten Pilotfolge könnten in Kapitel 7.4 zusätzlich kurz genannt werden. Sie stehen derzeit erst im Anhang; damit ist die Antwort auf die ausdrücklich kennzahlenbezogene FF2 etwas schwer auffindbar.
4. Die Aussage „Die unabhängigen Normaltests umfassen drei separate Starts“ in Kapitel 6.7 sollte „Die erste unabhängige Normaltestserie umfasst drei separate Starts“ heißen. Kapitel 7 zählt korrekt insgesamt sechs 75-%-Normalreferenzen plus drei 50-%-Normalaufnahmen.
5. Aus den bisherigen Daten lässt sich keine konkrete Fallzahl für einen belastbaren populationsweiten Reproduzierbarkeitsnachweis ableiten. Eine weitere vorab fixierte vollständige Folge wäre ein kleiner Pilot-Replikationsschritt, aber nicht automatisch dessen endgültiger Nachweis.

## Grenzen dieses Reviews

Geprüft wurden fachliche Binnenkonsistenz, Anforderungen/Hypothesen, ausgewählte maschinenlesbare Zahlen und die vorhandene Verzeichnis-/Layoutprüfung. Die 66 PDF-Seiten wurden in diesem Review nicht erneut vollständig visuell kontrolliert; dazu existiert die vorangegangene dokumentierte Formatprüfung. Antonini et al. (2023) wurde gezielt anhand des Originalvolltexts geprüft; die übrigen Literaturquellen wurden nicht sämtlich erneut im Original begutachtet. Die aktuelle Hardware, Rotorfreiheit, Versorgung, Drehzahl und Sensorfrequenz wurden nicht geprüft. Eine technische Dokumentprüfung kann persönliche Autorenschaft, tatsächliche eigene Beiträge oder eine Prüfungsfreigabe nicht stellvertretend bestätigen.

## Geprüfte Hauptquellen

- `results/upright_v4_finalization_20260912_103145/existing_chapters_and_tables.txt`
- `results/upright_v4_finalization_20260912_103145/manuscript_completed.md`
- `results/upright_v4_finalization_20260912_103145/chapters_completion.md`
- `results/upright_v4_finalization_20260912_103145/thesis_final_layout_audit.json`
- `results/upright_v4_finalization_20260912_103145/runtime_analysis/analysis.json`
- `results/upright_v4_finalization_20260912_103145/controlled_state_descriptive_metrics.json`
- `results/upright_v4_finalization_20260912_103145/completion_verification.json`
- `results/upright_v4_frozen_airflow_test_20260912_073015/evaluation_{normal_before,airflow_modified,normal_after}/scores.csv`

## Direkt einsetzbare Ergänzung für H1 und A11

**Kapitel 8.1, H1:**

> H1 vergleicht die Erkennungsqualität für die vorab definierten Versuchsanomalien; sie verlangt keine gesicherte Schadensdiagnose. In der vorliegenden Folge ist die äußere Luftstromveränderung das vorab vergebene positive Zustandslabel. Die deskriptiven F1-Werte betragen 6,93 % für RMS, 4,04 % für Isolation Forest und 0 % für den Autoencoder. Die erwartete Überlegenheit des neuronalen Verfahrens ist damit in dieser Folge nicht bestätigt. Das negative Ergebnis ist eine gültige Bewertung des eingefrorenen Pakets. Eine einzige unabhängige veränderte Aufnahme belegt jedoch keine allgemeine Wiederholbarkeit. Die Platte bleibt ein kontrolliert veränderter Betriebszustand und wird nicht als nachgewiesener Defekt bezeichnet.

**Tabelle 7-9, A11:**

> Teilweise nachgewiesen: Aufbau und Protokoll dokumentiert, Normalstarts wiederholt und eine unabhängige Normal–Änderung–Normal-Folge abgeschlossen. Wiederholungen der veränderten Bedingung fehlen. Die Rückkehrreferenz zeigt einen anderen mittleren RMS; dieser Befund allein trennt normale Start-/Zeitvariabilität nicht von einer unvollständig rückgesetzten Messbedingung.

Eine notwendige Korrektur der Aufgabeninterpretation hebt diese tatsächlich offene Replikationsgrenze nicht auf. Eine bessere Erkennungsleistung wird durch redaktionelle Klarstellung weder erzeugt noch behauptet.
