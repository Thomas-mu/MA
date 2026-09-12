# Unterbrochene Folge mit eingefrorenem Modellpaket: Normal → Luftstromveränderung → Normal

**Status: unvollständig (`incomplete`).** Die neue Normalaufnahme ohne Platte wurde abgeschlossen und ausgewertet. Der anschließend freigegebene Plattenlauf wurde bei der anfänglichen Prüfung der Pin-Funktion abgebrochen, bevor ein Stellbefehl auf 75 % oder ein Sensorzugriff erfolgte. Die abschließende Normalaufnahme wurde nicht gestartet. Es gibt deshalb keinen gemessenen Vergleich mit Platte und keine gemessene Rückkehrreferenz für diese Folge.

Dieser Bericht ergänzt ausschließlich neue Ergebnisdateien. Er ersetzt weder Messprotokolle noch frühere Berichte. Zeitangaben sind UTC; am Versuchstag entspricht die Ortszeit in Deutschland UTC + 2 Stunden.

| Phase | Tatsächlicher Stand | Vorhandene Messdaten |
|---|---|---|
| `normal_before` | 300-s-Aufnahme bei 75 % und 25 kHz abgeschlossen; eingefrorenes Paket angewendet | Eine vollständige neue Rohaufnahme mit Metadaten und Auswertung |
| `airflow_modified` | Anfangsprüfung fehlgeschlagen; anschließend 0 % und PWM-Pin-Funktion wiederhergestellt | Keine Aufnahme; `csv: null`; Fehler- und Steuerungsjournal vorhanden |
| `normal_after` | Nicht gestartet | Keine Aufnahme |

Aufbauversion ist `fan_upright_position_v4_20260911_103726`. Die aufrechte Lüfteraufstellung und Sensorbefestigung wurden entsprechend den Nutzerbestätigungen übernommen. Die Freigabe des Plattenlaufs dokumentiert eine separat befestigte Platte von 120 × 120 mm, 100 mm Abstand zwischen Auslass-Rahmenebene und nächster Plattenfläche, parallele und mittige Anordnung sowie Kontaktfreiheit und unveränderte Lüfter-/Sensorposition. Diese Angaben sind Nutzerangaben, keine unabhängig durchgeführte Geometrievermessung. Der Nutzer bestätigte die tatsächliche Luftauslassseite; eine gesonderte konkrete Beobachtung eines Gehäusepfeils wurde nicht beschrieben. Die Freigabe und deren Herkunft bleiben in der [Freigabedatei](airflow_modified_release.json) erhalten.

## Abbruch vor dem Plattenlauf

Die [Sitzungsdatei](airflow_modified_session.json) enthält den Fehler:

> `FanPWMError: Held PWM setting or pinmux changed; recording conditions are unconfirmed.`

Das [Steuerungsjournal](airflow_modified_fan.jsonl) trennt die anfänglichen Lesezugriffe von der anschließenden Wiederherstellung:

| Zeitpunkt am 11.09.2026 | Belegter Vorgang | Bedeutung |
|---|---|---|
| 17:01:34.689 | Am Ende von `normal_before` waren `a3 / PWM0_CHAN2` und 0 % rückgelesen | Bestätigte Softwarekonfiguration am Ende der vorausgehenden Aufnahme |
| 17:09:34.110 | Erster `pinctrl get 18` der neuen Phase meldet `18: op dl pd \| lo // GPIO18 = output` | GPIO18 war bereits beim ersten Lesezugriff als normaler Digitalausgang konfiguriert |
| 17:09:34.130 | `verify(0)` verwirft die Anfangsbedingung | Die gespeicherten PWM-Attribute allein genügen bei falscher Pin-Funktion nicht |
| 17:09:34.152 | Im Fehlerpfad wird `pinctrl set 18 op dl` angekündigt und danach ausgeführt | Dieser eigene Schreibbefehl liegt nach der Fehlerfeststellung; er erklärt den bereits zuvor gelesenen Zustand nicht |
| 17:09:34.193–17:09:34.231 | Wiederherstellung von `a3`, Rücklesen und Abschluss der 0-%-Transaktion | Hardware-PWM-Funktion und Stellvorgabe 0 % wurden wiederhergestellt |
| 17:09:34.247 | Erneute vollständige Prüfung von 0 % erfolgreich | Rückgelesen: Periode 40.000 ns, Tastgrad 0 ns, aktiviert, normale Polarität, Pin-Funktion `a3 / PWM0_CHAN2` |

BCM-GPIO18 entspricht physischem Pin 12. Vor dem Abbruch waren in sysfs ebenfalls 40.000 ns Periode, 0 ns Tastgrad, `enable=1` und normale Polarität gespeichert. Wegen `op dl` war damit jedoch keine korrekt zugeordnete Hardware-PWM-Funktion bestätigt. Der niedrige gelesene Digitalpegel ist weder eine Drehzahlmessung noch ein Nachweis vollständigen mechanischen Stillstands.

Die Anfangsprüfung liegt im [Runner](../../src/run_controlled_airflow_test.py) vor `connect(...)`, vor der zusätzlichen Auszeit und vor `set_percent(75)`. Die Sitzung enthält daher keinen 75-%-Stellbefehl, keinen Aufnahmebeginn und keine CSV-Datei. Der abgebrochene Versuch bleibt als eigenständiger fehlgeschlagener Vorgang erhalten; es gab keinen automatischen Wiederholungsstart.

## Gesicherte Softwarebefunde und offene Ursache

Die rein lesende Prüfung des Codes ergab: Konstruktion und Eintritt in [FanPWM](../../src/fan_pwm.py) lesen die vorhandene Konfiguration; `verify()` verändert sie ebenfalls nicht. `close()` und `__exit__()` geben die Sperre frei, ohne die letzte Ausgangseinstellung umzuschalten. Auch in den geprüften Projektimporten vor der Anfangsprüfung wurde keine GPIO-Initialisierung oder GPIO-Bereinigung gefunden. Der normale geprüfte Runnerpfad erklärt den anfänglichen Wechsel auf `op dl` somit nicht.

Die tatsächliche Ursache bleibt **unbekannt**. Es gibt keinen Beleg, der diesen Wechsel einem bestimmten Prozess oder einem manuellen Eingriff zuordnet. Die anschließende Prozessprüfung fand keinen laufenden Python-Steuerprozess und keinen durch `fuser` erkennbaren konkurrierenden Besitzer der geprüften Sensor-/GPIO-Geräte. Eine solche Momentaufnahme schließt einen zuvor beendeten Prozess oder einen einmaligen direkten Steuerbefehl nicht aus.

Der Dienst `fan-pwm.service` war als `active (exited)` sichtbar. Es handelt sich um einen bereits am Vortag gestarteten Einmaldienst; das zugehörige Skript richtet 25 % und `a3` ein. Die geprüften Informationen enthalten keinen zum Fehlerzeitraum passenden Dienstlauf und keinen Nachweis, dass der Dienst den beobachteten Zustand verursacht hat. Der Dienst wurde nicht verändert. Die [Fehlerdiagnose](abort_diagnosis.json) dokumentiert die Prozess-/Dienstprüfung; die [abschließende Prüfung](final_after_abort_verification.json) verknüpft die zugehörigen Artefakthashes und Integritätsbefunde.

Die [anschließende lesende Zustandsbeobachtung](post_abort_pin_observation.json) enthält sieben Abfragen zwischen 17:12:11.955 und 17:12:41.970 UTC. Alle meldeten `a3 / PWM0_CHAN2`, 0 ns Tastgrad, 40.000 ns Periode, aktiviert und normale Polarität. Das belegt die rückgelesene Softwarekonfiguration in diesen Momenten. Es beweist weder das Fehlen früherer oder späterer konkurrierender Zugriffe noch eine elektrische Wellenform, eine Drehzahl oder mechanischen Stillstand.

## Ergebnis der vorhandenen Normalaufnahme

Die erste Aufnahme bleibt eine gültige eigenständige normale Testaufnahme. Der Stellbefehl wurde am 11.09.2026 um 16:56:33.702319 UTC aufgerufen. Der erste gespeicherte XYZ-Punkt folgte nach **0,359989 s**; der Abstand vom ersten bis zum letzten Punkt beträgt **299,989721 s**. Die zusätzliche Auszeit nach Freigabe betrug **60,085977 s**. Der dokumentierte Abstand seit Abschluss der vorherigen Software-Nullstellung betrug **1.447,803610 s**. Diese zweite Größe ist keine gemessene Dauer des mechanischen Stillstands oder einer getrennten Versorgung.

| Qualitätsmerkmal | Ergebnis |
|---|---:|
| Vollständige XYZ-Messpunkte | 62.134 |
| Einzelne Achsenwerte | 186.402 |
| Nominelle Sensor-Abtastrate | 200 Hz |
| Beobachteter Durchsatz aus Host-Zeitstempeln | 207,117097 XYZ/s |
| Nichtmonotone Host-Abstände | 0 |
| Host-Leseabstand: Median / 99. Perzentil / Maximum | 5,576803 / 5,684731 / 10,096460 ms |
| Host-Abstände über 10 ms / über 160 ms | 1 / 0 |
| Maximale FIFO-Belegung | 2 |
| Gesetzte Lücken- / Überlauf- / Sättigungsflags | 0 / 0 / 0 |
| Nichtendliche XYZ-Punkte | 0 |
| Exakte Zahl physisch verlorener Sensorwerte | Unbekannt |

Die Sensoreinstellungen blieben ADXL345, nominell 200 Hz, ±2 g, volle Auflösung, FIFO-Stream und 0,0039 g je LSB. Die I²C-Taktkonfiguration beträgt 100 kHz. Die Zeitstempel beschreiben den Abschluss der Host-Lesezugriffe; sie sind keine unmittelbar gemessene Sensor-Konversionszeit. Die Abweichung zum nominellen Wert wird dokumentiert, nicht durch Umdeutung von XYZ-Punkten in einzelne Achsenwerte oder nachträgliche Neuskalierung beseitigt.

Die Modellbewertung verwendet ausschließlich den vorab festgelegten Abschnitt **[180, 300) Sekunden ab Stellbefehlsaufruf**. Aus 24.854 XYZ-Punkten entstanden 194 vollständige Fenster zu jeweils 128 Punkten, ohne Überlappung. Die verbleibenden 22 Punkte wurden nicht zu einem unvollständigen Modellfenster ergänzt. Alle 194 Fenster waren für jede Methode gültig; ungültige Fenster wurden nicht als NORMAL gewertet.

| Methode | Gültige Fenster | Ungültige Fenster | Fehlalarme unter normalen Fenstern | Fehlalarmrate |
|---|---:|---:|---:|---:|
| RMS | 194 | 0 | 2 | 1,031 % |
| Isolation Forest | 194 | 0 | 1 | 0,515 % |
| TFLite-Autoencoder | 194 | 0 | 9 | 4,639 % |

Die [Scoregrafik mit eingefrorenen Schwellen](evaluation_normal_before/scores.png) und die [numerische Auswertung](evaluation_normal_before/summary.json) dokumentieren diese Ergebnisse. Es erfolgten kein Nachtraining, keine erneute Anpassung des Scalers und keine Schwellenänderung. Diese weitere Normalaufnahme erweitert die beobachtete normale Variabilität; die Fehlalarme werden als Ergebnis erhalten.

![Scores der normalen Einzelaufnahme mit eingefrorenen Schwellen](evaluation_normal_before/scores.png)

Der physische Vektor-AC-RMS wurde unabhängig davon in aufeinanderfolgenden 5-s-Abschnitten berechnet, jeweils nach Entfernung des jeweiligen Achsenmittelwerts. Im Abschnitt 180–300 s beträgt sein Mittelwert **32,180669 mg**, die Stichprobenstandardabweichung der 24 Abschnittswerte **1,123479 mg** und der deskriptive lineare Anstieg **1,116511 mg/min**. Der Mittelwert der zweiten Abschnittshälfte liegt um **1,123557 mg** über dem der ersten. Das beschreibt eine zeitliche Veränderung innerhalb dieser Aufnahme. Die vorab festgelegte Auswertungsgrenze von 180 Sekunden bleibt unverändert; der Anstieg allein entscheidet nicht darüber, ob diese Grenze für spätere Versuche geeignet ist. Eine vollständig konstante RMS-Kurve ist keine Voraussetzung dafür, normale Variabilität zu erfassen. Ein allgemeines Stabilisierungsverhalten ist durch diese Einzelaufnahme nicht belegt.

![Vektor-AC-RMS der vollständigen Normalaufnahme in 5-s-Abschnitten](evaluation_normal_before/rms_5s.png)

Die [5-s-Werte](evaluation_normal_before/rms_5s.csv) und [Scorewerte](evaluation_normal_before/scores.csv) liegen separat vor. Benachbarte Abschnitte und Modellfenster sind keine unabhängigen Versuchsreplikate. Aus dieser normalen Einzelaufnahme lassen sich weder Defekt-Recall, F1 noch allgemeine Erkennungsleistung ableiten.

## Grenzen und Fortsetzung

Es fehlen eine gemessene Luftstromveränderung und die anschließende Normalreferenz. Deshalb kann weder ein Platteneffekt noch eine Rückkehr in den vorherigen Normalbereich bewertet werden. Die vorbereitete Luftstromveränderung wäre ein kontrollierter veränderter Betriebszustand, kein nachgewiesener Defekt. Frühere Plattenaufnahmen werden nicht nachträglich als Ersatz in diese Folge übernommen.

Das verwendete Protokoll trägt SHA256 `c57aa346ee6557294945a5155637adcb0e5c853625e95d25b909f0b851f09192`; das eingefrorene Pilotpaket trägt SHA256 `cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5`. Die [abschließende Prüfung](final_after_abort_verification.json) bestätigt beide Hashanker, unveränderte eingefrorene Implementierungsdateien sowie keine Veränderungen an den 1.241 geschützten bestehenden Dateien. Der dort dokumentierte Worddatei-Hash lautet `a9a5d7d17b28098f554240a3e1650881e252db679f33319a1d11164b3246cbb8`. Das Paket, seine Skalierung, Schwellen und Vorverarbeitung bleiben Grundlage; Testergebnisse werden nicht zur nachträglichen Anpassung verwendet.

**Nächster konkreter Schritt:** Die Untersuchung bleibt bei der rückgelesenen Stellvorgabe 0 % pausiert. Beim Wiederaufnehmen werden Pin-Funktion, PWM-Konfiguration, konkurrierende Zugriffe und die aktuellen Aufbau-/Versorgungsbedingungen erneut geprüft. Ein weiterer Erfassungsversuch erhält einen ausdrücklich dokumentierten neuen Versuchsplan und neue Dateien. Die Fehlerdatei und die Schutzmarkierungen dieses Versuchs werden weder überschrieben noch umgangen. Vor einem neuen Start ist die aktuelle Freigabe erforderlich.

Wegen der Unterbrechung ist vorab zu entscheiden, ob eine neue zeitlich zusammenhängende Normal–Platte–Normal-Folge nötig ist. Ein nach längerer Pause aufgenommener Plattenlauf darf nicht ohne Kennzeichnung als unmittelbare Fortsetzung gelten. Die vorhandene Normalaufnahme bleibt unabhängig von dieser Entscheidung als normale Einzelaufnahme erhalten. Eine erforderliche Plattenentfernung oder ein anderer manueller Umbau kann nicht durch Software ersetzt werden: externe 12-V-Versorgung vorher trennen, vollständigen Stillstand abwarten und Lüfter sowie Sensorposition unverändert lassen. Ohne entsprechende physische Durchführung und anschließende Freigabe wird keine Rückkehrreferenz gestartet.
