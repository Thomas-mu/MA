# Verbleibende Nachweise und begrenzter Abschlussplan

Dieser Plan folgt den Forschungsfragen FF1–FF4, H1–H3 und A1–A13 der aktuellen, unveränderten Wordfassung. [Anforderungsauszug](requirements_extract.txt), [abgeschlossene explorative Diagnose](diagnosis_report.md), [zweiter PWM-Betriebspunkt](second_pwm_protocol.md), [Live-/Ressourcenplan](live_evidence_plan.md).

Die schlechte Reaktion auf den Plattenzustand ist ein Ergebnis, kein Anlass, so lange umzubauen oder nachzutrainieren, bis Kennzahlen günstig werden. Eine neue Modellversion ist für den wissenschaftlichen Abschluss dieses Pakets nicht erforderlich. Es wird kein weiterer 75-%-Normallauf allein zum Erzwingen einer konstanten RMS-Kurve verlangt.

## Priorisierte Restarbeiten

| Priorität | Nachweis / Anforderungsbezug | Belegter Stand | Noch konkret zu erledigen / Abschlusskriterium |
|---|---|---|---|
| 1 | Zweiter NORMAL-Betriebspunkt: FF4, H3, A10 | 75-%-Normaltests und unverändertes Paket vorhanden; 50-%-v4-Test fehlt | neuen Aufnahme-/Testadapter auf 50 % vorbereiten und softwareseitig prüfen; drei unabhängige 300-s-Normalläufe, unveränderte Modelle/Schwellen; Fehlalarme je Lauf und Methode berichten, H3 auch bei Nichtanstieg nicht erzwingen |
| 2 | Aktueller Sensor-Livebetrieb: A4, A7, A8, A13 / FF3, H2 | vorhandener Live-Unterbau für altes Profil; neues Paket offline erfolgreich, Integration fehlt | Paketloader, exakte Zentrierung/Fensterlage/Qualitätslogik anbinden; Parität und Fehlerpfade prüfen; geplante Replay-/Sensor-Live-Messmatrix ausführen; P99, CPU, RSS, Rückstand, Verluste und INVALID vollständig berichten |
| 3 | Messketten-/Betriebspunktgrenzen: A1, Kapitel 5 | monotone Zeit, konsistente XYZ-Zählung, Flags und beobachteter Durchsatz dokumentiert; nominell 200 vs. ungefähr 207 XYZ/s | physische Sensorzeitbasis und exakte Verluste nicht als geklärt ausgeben. Vor allem fehlt der in Kapitel 5 geforderte tatsächliche Drehzahlnachweis. Dafür muss ein separat bestätigtes Messverfahren verfügbar sein; GPIO18 bleibt PWM, FFT-Peaks sind kein Tacho |
| 4 | Wiederholbarkeit der veränderten Bedingung: A11, FF2 | mehrere unabhängige Normalstarts; eine vollständige aktuelle Plattenfolge mit unvollständiger Rückkehr | bei gewünschter wiederholter Zustandsaussage eine zweite vorab dokumentierte identische Folge; dieselbe physische Veränderung, keine Schwellenänderung. Auch zwei Folgen bleiben ein Pilot. Ohne Ergänzung einmalige Reichweite ausdrücklich begrenzen |
| 5 | GUI: A12, sofern im finalen Funktionsumfang | Legacy-GUI implementiert, aktuelle Paketanbindung und belastbarer Zusatzlastnachweis fehlen | tatsächlichen Displayzugriff klären; gleiche gepacete Daten mit/ohne GUI, danach kontrollierte Live-Zusatzlast, Anzeige-/Entscheidungs-/Sensordrops getrennt. Keine GUI-Demo als Pipelinebenchmark ausgeben |
| 6 | Wissenschaftlicher Abschluss: A5, A9 / FF1–FF4 | neue Quellen, Tabellen, Grafiken, Negativbefunde und Hashes getrennt vorhanden | nach Abschluss oder expliziter Begrenzung der offenen Nachweise die Ergebnisse zusammenführen; fehlende oder nicht bestätigte Ziele klar benennen. Die Worddatei bleibt in diesem Auftrag unverändert |

Die Prioritäten bedeuten keine zwingende Sperre der übrigen Arbeit: beispielsweise kann die Live-Software vorbereitet werden, solange die Drehzahlmessung offen ist. Ein fehlender Tacho rechtfertigt weder erfundene Drehzahlwerte noch das Liegenlassen der unabhängigen Offlineaufgaben. Die spätere 50-%-Auswertung ist bis dahin als Vergleich zweier PWM-Vorgaben auszuweisen.

## Bereits abgeschlossene Arbeit nicht erneut durchführen

| Anforderung | Bestehender Nachweis und Geltungsbereich |
|---|---|
| A2 – Datentrennung | getrennte vollständige Aufnahmen für Training, Normalvalidierung und Tests; aktuelles Paket unverändert. Heute 582 vorbereitete AC-Fenster exakt wiedergefunden |
| A3 – gleicher Methodenvergleich | gleiche 128er-Fenster, gleiche Vorverarbeitung und gespeicherter Scaler; heute 4.074 archivierte Testergebnisscores exakt reproduziert |
| A5 – Zuordnung | Paket-/Code-/Datenhashes, Aufnahme- und Fenster-IDs vorhanden; neue Analyse erhält eigene Dateien |
| A6 – TFLite-Zielausführung | frühere Keras/TFLite-Konsistenzprüfung bestanden, 0 Entscheidungsabweichungen auf 194 Validierungsfenstern; reale LiteRT-Ausführung des aktuellen Pakets in den Offline-Tests nachgewiesen |
| A13 – abgeschlossene Aufnahmen | die drei 300-s-Läufe sind gespeichert, jeweils mit erfolgreicher 0-%-Rücklesung. Das ersetzt nicht die noch nötigen Fehler-/Shutdown-Tests des neu zu integrierenden Liveadapters |
| A9 / H1 – Erkennungsqualität | normale Fehlalarme und Plattenalarmanteile belegt; zuverlässige Plattenerkennung und Überlegenheit des AE nicht nachgewiesen. Die Diagnose ist abgeschlossen. Keine nachträgliche Defektetikettierung und kein F1-Erfolg aus diesen Daten ableiten |

Die in FF2/A9 genannten vollständigen binären Defektkennzahlen wurden durch das aktuelle Protokoll bewusst nicht als Defektleistung ausgewiesen. Diese Lücke muss im abschließenden Methodenumfang transparent bleiben. Soll stattdessen ausdrücklich eine **vorab definierte Betriebsänderung** als positive Zielklasse mit binären Kennzahlen untersucht werden, braucht das einen eigenen prospektiven Testvertrag und unabhängige Aufnahmen; es darf nicht rückwirkend als bestandener Defektnachweis erscheinen. Ein zusätzlich erzeugter mechanischer Defekt ist keine Voraussetzung, um die Grenzen und Nichtbestätigung von H1 wissenschaftlich ehrlich zu berichten.

## Kleinster sinnvoller nächster Versuch

**Ein 300-s-Normalstart bei 50 % PWM und 25 kHz**, nach 60 s zusätzlicher Auszeit, ohne Platte und bei unverändertem v4-Aufbau. Er prüft eine noch unbeantwortete Pflichtfrage: Welche Fehlalarme erzeugt das eingefrorene Paket bei einer zweiten normalen PWM-Vorgabe? Er ist der erste der drei vorab geplanten Starts; ein einzelner Lauf ist kein Wiederholbarkeitsnachweis. Vorher muss der neue 50-%-Adapter einschließlich Paritäts-/Fehlerprüfungen fertig sein. Der bestehende 75-%-Runner ist dafür nicht freigegeben.

**Vorbereitung durch den Nutzer:** Aufbau und Sensor unverändert lassen, Platte außerhalb des Luftstroms belassen. Es ist kein neuer Plattenumbau nötig. Zum späteren Start Versorgung anschließen, aktuellen vollständigen Stillstand und Freigabe bestätigen. Zwischen den weiteren Starts genügt jeweils eine neue Stillstands-/Startfreigabe; Steuerbefehle übernimmt die Software. Keine Antwortfrist und keine Laufabfragen während der Aufnahme. Nach jedem Lauf wird 0 % eingestellt und zurückgelesen. Für diese Planungsarbeit ist jetzt keine Handlung oder Antwort erforderlich.

## Aufwandsschätzung ab diesem Stand

Die folgenden Werte sind begründete Planungsbereiche, keine bereits gemessenen Arbeitszeiten und keine Garantie. Vorausgesetzt sind unveränderte funktionierende Hardware, bestehende Python-Umgebungen und keine neue Modellversion. Die heute abgeschlossene Datei-Diagnose ist nicht noch einmal eingeplant.

| Softwarearbeit | Geschätzter aktiver Aufwand | Begründung |
|---|---:|---|
| Separater 50-%-Runner/Testimport mit Parität und Fehlerpfaden | 1,5–3 h | vorhandene Funktionen wiederverwendbar, aber feste 75-%-Prüfungen dürfen nicht umgangen werden |
| Pilot-Liveadapter, Fensterphase, Qualität und drei Methoden | 3–6 h | Loader und Scorer vorhanden; Zentrierung, Segmentierung, INVALID-/Drop-Bilanz und Shutdown müssen zusammen geprüft werden |
| Ressourceninstrumentierung, Replayausführung und Auswertung | 2–4 h | vorhandene Messkomponenten anwendbar, alte Benchmarkpfade unpassend; unterschiedliche Zeitgrenzen und Prozesswiederholungen |
| Zusammenführung der verbleibenden Nachweise | 1–2 h | Tabellen/Grafiken/Vergleich, Grenzen und Integritätsprüfung; keine automatische Wordänderung |
| **Kernumfang Software** | **rund 8–15 h** | auf kleine überprüfbare Teilaufträge begrenzt |
| GUI-Anbindung/-Nachweis zusätzlich, falls übernommen | 2–4 h | tatsächlicher Desktopzugriff vorausgesetzt; Anzeige- und Lastabgleich |

| Laufzeit / Messzeit | Reine Aufzeichnung oder Replay | Zusätzliche Auszeiten | Manuelle Beteiligung |
|---|---:|---:|---|
| Kleinster nächster 50-%-Lauf | 5 min Sensoraufnahme | mindestens 1 min | eine aktuelle Bereitschafts-/Stillstandsfreigabe, kein Umbau |
| Vollständiger zweiter PWM-Nachweis, 3 Läufe | 15 min Sensoraufnahme | mindestens 3 min | drei Startfreigaben, dazwischen Sichtprüfung; insgesamt grob 3–6 min aktive Handgriffe/Antworten, Reaktionspausen beliebig |
| Gepacetes Offline-Replay, 3 Methoden × 3 Prozesse × 300 s | 45 min Rechnerlaufzeit | keine mechanische Auszeit | keine |
| Sensor-Livevergleich, 3 Methoden × 3 Läufe × 300 s | 45 min Sensoraufnahme | mindestens 9 min | neun Startfreigaben/Stillstandsprüfungen, keine Montageänderung; grob 5–10 min aktive Beteiligung |
| GUI-Zusatzlast optional, 3 zusätzliche AE-Live-Läufe | 15 min Sensoraufnahme; zusätzlich etwa 15 min entsprechendes GUI-Replay | mindestens 3 min | Displaybereitstellung sowie drei Startfreigaben |
| Zweite Plattenfolge bei gewünschter Replikation | 15 min Sensoraufnahme | mindestens 3 min | zwei Plattenumbauten bei getrennter Versorgung, drei Freigaben; grob 5–10 min aktive Beteiligung |

Für den Kern aus zweitem PWM-Punkt und vollständigem Sensor-Livevergleich ergeben sich **60 min Sensoraufnahmen plus mindestens 12 min zusätzliche Auszeit**, daneben **45 min Offline-Replay ohne Lüfter**. Wartezeit auf freiwillige Freigaben, Auslauf und Vorbereitung kommt hinzu; die Messzeit ist keine zusammenhängende unbeaufsichtigte Startschleife. Ein späterer Drehzahl-/Sensortaktnachweis hängt von noch nicht bestätigter Messtechnik ab und ist daher nicht seriös mit einer festen Dauer veranschlagt.

Dieser Umfang soll die offenen Anforderungen beantworten. Er enthält kein Nachtraining, keine künstlichen Defekte und keine zusätzlichen Wiederholungen zur Kennzahlenverbesserung. Ein negatives oder begrenztes Ergebnis beendet den jeweiligen Nachweis genauso wie ein positives, sofern Messvertrag und Qualität eingehalten wurden.
