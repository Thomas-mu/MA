# Abschluss der fachlichen Nacharbeit und Vorbereitung der Restmessungen

Stand: 12.09.2026. Dieser Auftrag umfasst Datei- und Softwareprüfung sowie eine nachvollziehbare Revision der Wordfassung. **Es wurden keine neuen Hardwaremessungen gestartet und keine PWM-Stellbefehle ausgeführt.** Die drei angesprochenen Punkte sind daher unterschiedlich weit abgeschlossen.

| Punkt | In diesem Auftrag erledigt | Tatsächlich noch offen |
|---|---|---|
| Bewertung der Erkennung | Anforderungen mit Kapitel 1–5 abgeglichen, archivierte Entscheidungen unabhängig nachgezählt, Kennzahlen je Aufnahme ergänzt, Schlussfolgerungen korrigiert | Zwei zusätzliche vollständige Plattenfolgen für den begrenzten Wiederholungsnachweis A11; kein Nachtraining erforderlich |
| Drehzahl und Sensorzeitbasis | Erfassungsweg und Herstellerangaben geprüft, konkretes Referenzprotokoll erstellt, Offline-Import mit 26 künstlichen Softwaretests und unabhängiger Codeprüfung abgesichert | Tatsächliche unabhängige Messung; Gerät, Zeitbasis und Signalanschlüsse fehlen noch |
| Fachliche und formale Berichtskontrolle | Zehn bestehende Text-/Tabellenstellen korrigiert, neue Tabelle A-4, Word/PDF neu gesetzt und geprüft; Ausgangskopie erhalten | Persönliches Lesen, fachliche Verantwortung und gegebenenfalls Unterschrift des Autors; keine stellvertretende Autoren- oder Betreuerfreigabe |

## Was die Messungen bereits aussagen

Eine frühere Formulierung, für den Abschluss müsse ein zuverlässig funktionierender allgemeiner Defektdetektor nachgewiesen werden, war zu weitgehend. FF2 und A9 verlangen die Bewertung der vorab definierten Versuchszustände auf derselben Datenbasis. Kapitel 1.5 begrenzt den Anspruch ausdrücklich. **Auch die geringe Erkennung ist deshalb ein gültiges negatives Evaluationsergebnis.** Die Luftstromveränderung bleibt das vorab vergebene positive Zustandslabel und wird nach dem schwachen Ergebnis nicht umbenannt oder ausgeschlossen. Sie ist kein nachgewiesener Defekt.

Die nachträgliche Zählung verwendet ausschließlich die unveränderten Entscheidungen der abgeschlossenen unabhängigen Folge. Jede Tabellenzelle nennt markierte Fenster bei jeweils 194 gültigen und null ungültigen Fenstern; Markierungen in den Normalaufnahmen sind Fehlalarme.

| Aufnahme | RMS | Isolation Forest | Autoencoder |
|---|---:|---:|---:|
| `normal_before` | 1 | 0 | 51 |
| `airflow_modified` | 7 | 4 | 0 |
| `normal_after` | 0 | 0 | 4 |

Die deskriptiven F1-Werte der vollständigen Zwei-Klassen-Folge bleiben 6,93 %, 4,04 % und 0 %. H1, die erwartete Überlegenheit des neuronalen Verfahrens, ist in dieser Folge nicht bestätigt. Die vorhandene explorative Analyse erklärt die Scoreunterschiede durch gespeicherte Achsenskalierung, geringere X-/Y-Rekonstruktionsfehler im Plattenzustand und Überschneidungen mit bekannter Normalvariation. Sie weist keine bestimmte mechanische Ursache nach. Eine andere mittlere Schwingungsstärke nach dem Rückbau beweist für sich keine mechanisch misslungene Rücksetzung. Fenster sind keine unabhängigen Versuchsreplikate.

Die Modelle, Scaler, Schwellen, Vorverarbeitung und festgelegten Testabschnitte wurden nicht geändert. Der aktualisierte Bericht trennt die abgeschlossene begrenzte Kennzahlenbewertung A9 vom noch offenen Wiederholungsnachweis der veränderten Bedingung A11. Die vorhandenen 50-%-Normaltests und Laufzeitnachweise wurden nicht wiederholt.

## Zeitbasis und Drehzahl: gesicherte Grenze

Die konfigurierte ODR beträgt 200 Hz. Der gespeicherte Durchsatz von etwa 207 vollständigen XYZ-Punkten je Sekunde ist keine Zählung dreier einzelner Achsenwerte. Im geprüften Erfassungsweg wurde kein Fehler gefunden, der die Abweichung erklärt. Ein toleranzbehafteter interner Sensortakt ist anhand der Herstellerhinweise plausibel, aber für dieses Exemplar nicht unabhängig gemessen. Unbekannte physische Verluste bleiben unbekannt.

DATA_READY kann über mehrere Datenbereitstellungen aktiv bleiben. Eine bloße Flankenzahl ist deshalb kein Sensortaktnachweis. Der vorbereitete Import darf auch durch ausgefüllte Metadatenfelder keinen solchen Nachweis behaupten. Er liefert lediglich Frequenzstatistiken und ausdrücklich bedingte Umrechnungen; die physischen Nachweisfelder bleiben falsch. Alle 26 Tests verwenden künstliche Daten. Die zweite Codeprüfung hat die Korrekturen für unbewiesene Metadatenansprüche und numerische Überläufe bestätigt.

GPIO18 ist der PWM-Ausgang am physischen Pi-Pin 12. Ein separater Tachoanschluss und dessen Signalpegel/Pull-up sind nicht bestätigt. Eine Impulszahl pro Umdrehung wäre erst für RPM nötig; ohne sie könnte ein geeignetes Messgerät lediglich die Tachosignalfrequenz in Hz belegen. Weder PWM-Stellwert noch Vibrationspeak noch der Pi-interne Kühlerwert ersetzen die Prüflüfterdrehzahl.

## Konkreter nächster Schritt

Zuerst genügt die Angabe, ob ein Oszilloskop, Logikanalysator oder berührungsloses Drehzahlmessgerät verfügbar ist, samt Modellbezeichnung. Die entsprechende Frage ist gestellt; **vorerst nichts umstecken und die Montage nicht verändern**. Erst anhand des Geräts können tatsächliche Leitungen, Pegel, Export und Genauigkeit festgelegt werden. Eine fehlende Antwort ist weder ein angeschlossenes Messgerät noch eine Freigabe.

Der [Messplan](remaining_measurement_protocol.md) sieht eine 60-s-Zeitbasisprobe bei 0 % PWM und zwei weitere Normal–Platte–Normal-Folgen vor. Eine Drehzahlreferenz lässt sich möglichst mit einem ihrer Normalläufe verbinden. Das wären sechs neue 300-s-Aufnahmen bei 75 % und 25 kHz, jeweils 60 s zusätzliche Auszeit nach der Freigabe. Viermal muss ausschließlich die separat befestigte Platte bei getrennter Versorgung und bestätigtem Stillstand eingesetzt oder entfernt werden. Alle Abläufe pausieren dafür; keine Antwortfristen oder automatischen Ersatzstarts.

| Aufwand | Begründete Planungsschätzung |
|---|---|
| Bisherige Software-/Berichtsarbeit | In diesem Auftrag abgeschlossen: Review, korrigierte Wordfassung, Neuzählung, konservativer Import und 26 Tests |
| Weitere Softwarearbeit nach Geräteklärung | Etwa 2–4 Stunden für gerätespezifischen Export, getrennte Diagnoseinstrumentierung mit Registerwiederherstellung, Synchronisationsprüfung und Ergebniseintrag; bei ungeeignetem Export/Messweg höher, kein zugesagter Fixtermin |
| Reine neue Messzeit | 30 Minuten für sechs Betriebsläufe plus 1 Minute Sensorzeitprobe; RPM möglichst gleichzeitig mit einem Normallauf |
| Wartezeit | Mindestens 6 Minuten zusätzliche Auszeit plus tatsächliche Auslauf-, Freigabe- und Umbaupausen |
| Deine physischen Schritte | Geräteangabe, einmalige geprüfte Instrumentierung sowie vier Plattenwechsel; grob 15–30 Minuten aktive Mitarbeit, abhängig vom Messgerät und der Halterung |

Die Untersuchung endet mit dem festgelegten Umfang unabhängig davon, wie gut die Kennzahlen ausfallen. Falls die zwei weiteren Folgen erneut kaum erkannt werden, bleibt genau das der Abschlussbefund. Eine neue Modellversion wäre ein gesonderter Entwicklungsauftrag mit neuen unabhängigen Tests.

## Dateien und Kontrolle

- [Überarbeitete Worddatei](../../docs/Akz_Masterarbeit_Bericht(3).docx) und [zugehörige PDF](thesis_reviewed.pdf).
- [Ausgangskopie](../../docs/backups/Akz_Masterarbeit_Bericht(3)_vor_fachreview_20260912_131657.docx); frühere Messdaten und Abschlussberichte bleiben erhalten.
- [Fachreview](review_thesis.md), [dokumentierte Änderungen](word_revision_changes.json), [Kennzahlen je Aufnahme](per_record_metrics.csv) und [Quellenhashes](per_record_metrics.json).
- [Zeitbasis-/Drehzahlprüfung mit Herstellerquellen](timebase_rpm_audit.md), [Referenzimport](reference_tools/README.md), [26 Tests](reference_tools/software_tests.log), [unabhängiger Abschlussreview des Imports](reference_tools/review_followup.md).
- [Prüfprotokoll der Wordfassung und Bestandserhaltung](review_verification.json), [Layoutkontrolle](layout_review/visual_review.json), [abschließender rein lesender Steuerstatus](final_readonly_status.json).

Die Bestandskontrolle prüft 1.910 geschützte Dateien unverändert; die einzige freigegebene Bestandsänderung ist die Worddatei. Die zehn fachlichen Änderungen sind einzeln mit Vorher-/Nachhertext festgehalten, darunter drei Klarstellungen in Kapitel 1–5. Drei Formeln, vorhandene Messzahlen und Modellartefakte bleiben erhalten. Die Wordfassung enthält 35 Tabellen einschließlich Abkürzungsverzeichnis, sechs Abbildungen und 40 eindeutige Tabellen-/Abbildungsbeschriftungen. Inhalts-, Tabellen- und Abbildungsverzeichnis sind aktualisiert; Seitenverweise, Kapitel- und Seitenzählung sowie sichtbares Layout wurden geprüft. Dokumentierte Zwischenfassungen sind keine freigegebenen Endfassungen.

Zum Steuerstatus wird ausschließlich die rückgelesene Einstellung berichtet. **0 % PWM ist keine neue Sichtbestätigung vollständigen mechanischen Stillstands.** Die unabhängige Drehzahl-/Sensortaktmessung, die beiden zusätzlichen Plattenfolgen und die persönliche Autorenprüfung werden nicht als erledigt ausgegeben.
