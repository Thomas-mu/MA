# Offene Arbeit bis Pilottraining und abschließender Evaluation

Stand nach Prüfung der vorhandenen Implementierung am 11.09.2026. Dieser Überblick ergänzt die bestehenden Berichte; er verändert keine Rohdaten, Modelle oder Worddatei. Es wurden weder Training noch neue Hardwaremessungen gestartet.

## Bereits erledigt

- GPIO18 als Steueranschluss und Sensorbefestigung sind geklärt. Die aktuelle aufrechte Aufstellung wird als Aufbauversion v4 getrennt von früheren Positionen geführt.
- Für diese Version liegen eine 30-s-Stillstandsreferenz, drei getrennte 300-s-Normalaufnahmen ohne Platte und eine 300-s-Plattenaufnahme vor.
- Die Kontrollsoftware verwendet Hardware-PWM, protokolliert Stellbefehle und liest die Einstellungen zurück. Die Sensorerfassung verwendet nominell 200 Hz, Full Resolution, ±2 g und FIFO-Stream mit Registerrücklesen.
- Zeitstempel, beobachteter Durchsatz, Host-Leseabstände, Qualitätsflags, Achsenwerte, AC-RMS und Spektren wurden geprüft. Die Spektralrechnung wurde numerisch gegen SciPy Welch geprüft.
- Die Normalvariation ist ein belegter Pilotbefund: späte mittlere AC-RMS-Werte 27,737 / 33,148 / 39,128 mg; Plattenaufnahme 36,481 mg. Alle Betriebsläufe besitzen denselben dominanten FFT-Bereich um geschätzte 39,45 Hz. Es ist kein eindeutiges Merkmal nur für die Platte nachgewiesen.
- Die vorhandene Software enthält Kalibrierung, Autoencoder-Training, Float32-TFLite-Konvertierung und einen gemeinsamen Vergleich mit RMS und Isolation Forest. Diese vorhandenen Funktionen sind kein Beleg für ein neues trainiertes Modell dieser Aufbauversion.
- Nachträglich nennt der Nutzer für die Platte 120 × 120 mm und einen Abstand von 100 mm. Die Abstandsbezugsebenen und die Zuordnung dieser Maße zu früheren Aufnahmen sind nicht bestätigt. Historische Geometrieangaben wurden nicht rückwirkend ersetzt.

## Unmittelbar vor einem ersten Pilottraining

| Aufgabe | Konkretes Ergebnis, das noch fehlt | Zuständigkeit |
|---|---|---|
| Pilotprofil festlegen | Expliziter Normalzustand bei 75 % PWM, Aufbauversion, verwendeter Abschnitt, Sensor- und Zeitbasis, Fensterlänge, Schrittweite, Vorverarbeitung und Qualitätsgrenzen | Software und dokumentierte methodische Entscheidung |
| Pilotdateien unverändert einbinden | Neues Profil/Importmanifest mit Originalpfaden und Hashes, Herkunft jeder abgeleiteten Fenstergruppe, erlaubten ursprünglichen Normalzustandsnamen und getrennten Aufnahme-IDs | Software |
| Training und Validierung trennen | Vorab festgelegte vollständige Normalaufnahmen je Gruppe; keine zufällige Aufteilung benachbarter Fenster und kein Stillstand oder Plattenzustand als Normaltraining | Software und dokumentierte Aufteilungsregel |
| Verarbeitungsweg überprüfen | Gleiche Rohfenster und Vorverarbeitung für die drei Methoden; Scaler nur an Training anpassen; Verhalten bei ungültigen Daten und Reproduzierbarkeit der Exporte prüfen | Software |

Die bestehende Pipeline `src/calibrate_and_train.py` verlangt ein Profil mit eigenen Dateien `normal_001.csv` usw., dazu konsistente Datei- und Sidecarhashes sowie einen zur Profilkonfiguration passenden Zustandsnamen. Die aktuellen Piloten haben dagegen Zustandsnamen `normal_before`, `normal_after` und `normal_followup` und enthalten den kompletten Anlauf ab Stellbefehl. Ein direkter Aufruf von `--train-only` auf den Ergebnisordnern ist daher kein fertiger Importweg. Es fehlt eine nachvollziehbare Einbindung dieser vorhandenen Aufnahmen beziehungsweise ihrer definierten Auswerteabschnitte. Originaldateien und ursprüngliche Labels dürfen dazu nicht stillschweigend umgeschrieben werden.

Die aktuellen Trainingskonstanten sind H=S=128 XYZ-Punkte, ohne Fensterüberlappung. Bei nominell 200 Hz entspricht das 0,64 s, beim beobachteten Durchsatz ungefähr 0,618 s. Die 5-s-Fenster der Pilotberichte sind davon getrennt. Die gemeinsame Pipeline verwendet derzeit einen trainingsbasierten StandardScaler und RMS über standardisierte Fenster; dies ist nicht automatisch dieselbe Größe wie der berichtete Vektor-AC-RMS mit achsenweiser Mittelwertentfernung in jedem 5-s-Abschnitt. Ob und wie diese Vorverarbeitung geändert wird, ist ausdrücklich festzulegen und für alle Methoden konsistent umzusetzen. Die Grafikwerte dürfen nicht unmittelbar als Modellschwellen übernommen werden.

Für einen rein technischen Pilot kann eine Aufteilung der vorhandenen drei vollständigen Normalaufnahmen in Training und Validierung vorbereitet werden, beispielsweise zwei Dateien für Training und eine für Validierung. Die Zuordnung ist vor dem Lauf festzuhalten; ein einzelner Validierungsstart deckt die normale Variabilität nicht zuverlässig ab. Da alle Piloten bereits untersucht wurden, ist dieser Versuch Entwicklungsarbeit und kein unabhängiger Abschlussnachweis. Die bestehende unterschiedliche Normalvariation ist kein grundsätzliches Trainingsverbot. Sie muss in der Beurteilung von Fehlalarmen und Generalisierung sichtbar bleiben.

180–300 s können für einen ausdrücklich vorläufigen Pilot als bereits untersuchter Abschnitt festgehalten werden. Damit werden 180 s nicht zur allgemein bestätigten Einlaufzeit erklärt. Bei späteren abschließenden Versuchen müssen die Auswahlregel und ihre Begründung vor Einsicht in Testdaten feststehen. Ursache und Grenzen der 200-/207-Hz-Abweichung, nutzbares Frequenzband, mögliche Aliasanteile und die Bedeutung fehlender Qualitätsflags bleiben dokumentierte Einschränkungen; sie werden nicht durch ein erfolgreich ausgeführtes Training als geklärt behandelt.

## Danach: Modelle und fairen Vergleich tatsächlich erzeugen

1. Ein neues, ausschließlich dieser Aufbauversion zugeordnetes Entwicklungsprofil verwenden. Der Autoencoder und Isolation Forest lernen aus normalen Trainingsdaten; RMS erhält eine dokumentierte Kalibrierung.
2. Skalierung ausschließlich aus Trainingsdaten bestimmen. Schwellen ausschließlich anhand separater normaler Validierung bestimmen; im vorhandenen Vergleich ist eine lineare P99-Regel vorgesehen. Die kleine Zahl unabhängiger Validierungsstarts ist gesondert auszuweisen.
3. Den Autoencoder nach Float32-TFLite konvertieren und Ausgaben beziehungsweise Rekonstruktionsfehler zwischen Keras und TFLite prüfen.
4. RMS, Isolation Forest und TFLite mit denselben vollständigen Quellen, Fenstern, Skalierungsregeln und derselben Entscheidungsregel vergleichen. Alle Modelle, Parameter, Scaler, Schwellen, Seeds und Herkunftsdateien versioniert speichern.
5. Einen abgeschlossenen Pilotlauf als technischen Befund berichten. Trainingsverlust, Rekonstruktionsfehler oder eine Kalibrierung auf Pilotdaten sind keine unabhängige Erkennungsleistung.

Dieser Trainingsschritt wurde noch nicht freigegeben oder ausgeführt. Die bisherige Nutzervorgabe, noch keine Modelle zu trainieren, gilt bis zu einer ausdrücklichen Änderung fort. Eine weitere Plattenmessung ist keine Voraussetzung, um Datenimport und Pilottraining vorzubereiten.

## Für die abschließende wissenschaftliche Evaluation

- Ein vorab festgelegtes Aufnahmeprogramm mit ausreichender normaler Variation, separater Validierung und neuen unabhängigen Tests wird benötigt. Der bisherige Entwurf nennt sechs Trainings- und zwei Validierungsaufnahmen sowie mindestens drei Testaufnahmen pro Normalbetriebspunkt und verändertem Zustand. Dies sind noch keine durchgeführten oder statistisch als ausreichend nachgewiesenen Zahlen; Umfang und Dauer sind als endgültiges Protokoll zu begründen.
- Der Test muss normale Läufe bei 75 % PWM, einen zweiten normalen PWM-Betriebspunkt und einen genau beschriebenen kontrollierten veränderten Zustand umfassen. Der zweite PWM-Wert ist für diese neue Aufbauversion noch festzulegen. Dabei bleiben Modelle, Scaler und Schwellen unverändert. Die alten 25-/50-%-Profile oder Messungen anderer Aufbauversionen ersetzen diesen Test nicht.
- Die Plattenbedingung ist ein kontrollierter veränderter Betriebszustand, kein nachgewiesener Defekt. Für ihre Wiederholung fehlen die eindeutig dokumentierte Istposition und Abstandsbezugsebene. Eine zweite Normal→Platte→Normal-Folge kann die Wiederholung eines Effekts und die Rückkehr prüfen; sie ist vor weitergehenden Erkennungsbehauptungen sinnvoll. Eine schwache oder nicht eindeutige Trennung muss als Ergebnis erhalten bleiben, statt nachträglich durch passende Schwellenwahl überdeckt zu werden.
- Alle Aufnahmegruppen werden nach vollständigen unabhängigen Läufen getrennt. Bereits zur Auswahl von Parametern oder Merkmalen betrachtete Piloten werden nicht als unabhängige abschließende Tests ausgegeben. Der Testdatensatz bleibt von Training, Skalierung, Schwellenwahl und Parameteroptimierung ausgeschlossen.
- Zu berichten sind unter anderem Fehlalarme in normalen Läufen, Erkennungskennzahlen entsprechend dem festgelegten Versuchslabel, ungültige oder fehlende Entscheidungen und Ergebnisse pro vollständiger Aufnahme. Benachbarte Fenster sind keine zusätzlichen unabhängigen Wiederholungen.
- Tatsächliche Drehzahl ist bislang nicht gemessen. Sie ist keine technische Voraussetzung zum Trainieren, aber erforderlich, wenn eine Drehzahlabhängigkeit oder eine konkrete Drehzahl behauptet werden soll. Es gibt keinen bestätigten separaten Tachoeingang; GPIO18 bleibt der geklärte PWM-Steueranschluss. Ohne unabhängige Messung bleibt RPM unbekannt.

## Laufzeit, Ressourcen und Dokumentation

Für die neue Messkette und die neu zu trainierenden Modelle fehlen der abschließende Vergleich von Latenz, CPU-/Speicherbedarf und längerer Livebetrieb mit Protokollierung von Queueverlusten beziehungsweise fehlenden Entscheidungen. Die früheren technischen Replays und kurzen Liveprüfungen sind vorhandene Entwicklungsbelege; sie ersetzen diesen Nachweis nicht. Falls die GUI zur abschließenden Untersuchung gehört, stehen eine tatsächliche sichtbare Funktionsprüfung und ihr Lastvergleich weiterhin aus.

Zum Abschluss sind Implementierung, belegte Ergebnisse und Grenzen in der Masterarbeit zu aktualisieren, mit geeigneten Tabellen sowie überprüfter Formatierung und Nummerierung. Die aktuelle Nutzervorgabe verlangt jedoch, die Worddatei unverändert zu lassen; ihre Bearbeitung wird erst nach entsprechender Freigabe wieder aufgenommen. Bis dahin bleiben neue Ergebnisse in separaten Berichten. Eine neue Ausgangssicherung ist vor einer späteren Wordbearbeitung zu erstellen.

## Konkrete Reihenfolge

**Jetzt:** Pilotprofil, unverändernden Datenimport und Aufteilung der vorhandenen Normaldateien vorbereiten. Dafür ist kein Eingriff am Prüfstand erforderlich. **Nach Trainingsfreigabe:** ersten dokumentierten Pilotvergleich ausführen und technische Funktionsfähigkeit sowie Normalvalidierung beurteilen. **Danach:** Umfang der noch nötigen Normal-, Platten- und unabhängigen Testaufnahmen festlegen und diese jeweils ausdrücklich freigeben. **Zum Schluss:** unveränderten Methodenvergleich am zweiten Betriebspunkt, Laufzeitnachweise und schriftliche Ausarbeitung abschließen.

Quellen: [Kalibrierung](../../docs/kalibrierung.md), [Messkette und bisheriger Versuchsentwurf](../../docs/messkette_und_versuche.md), [Trainingspipeline](../../src/calibrate_and_train.py), [gemeinsamer Methodenvergleich](../../src/common_comparison.py), [abgeschlossene v4-Folge](../upright_position_v4_sequence_20260911_104025/final_sequence_report.md), [zusätzlicher Normallauf](../upright_v4_normal_followup_20260911_112731/measurement_report.md), [Spektralvergleich](spectral_report.md).
