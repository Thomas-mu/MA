# Softwareseitige Übernahme der Lüftersteuerung am 09.09.2026

**Aktueller Stand nach abschließender Nutzerklärung:** GPIO18 ist der bestätigte
Steueranschluss des Lüfters. Der ADXL345 ist mit vorgesehener I²C-Beschaltung an
einer Ecke des Lüfterrahmens befestigt. Diese beiden Hardwarepunkte sind
abgeschlossen und keine offenen TODOs. Die historische Chronologie darunter
bewahrt die damals gestellten Fragen und Antworten; sie verlangt keine erneute
Klärung. Die jetzige Fortsetzung betrifft Softwareprüfung und Wordbearbeitung.
Eine unabhängige Drehzahlmessung und die kontrollierte Pilot-/Evaluationsfolge
sind dadurch nicht nachgewiesen.

Dieser Nachtrag dokumentiert eine neue Zustandsänderung und die anschließend
ausgeführten Steuerzugriffe. Er ersetzt keine ursprünglichen Messjournale und
klassifiziert keine früheren Aufnahmen nachträglich als kontrollierten Stillstand.
Die wissenschaftliche Einordnung folgt den Forschungsfragen FF1–FF4 und den
Anforderungen A1, A5, A10 und A11 der Kapitel 1–5. Eine eingestellte PWM ist kein
Nachweis der Drehzahl oder ausreichender Messqualität.

## Nutzerangabe und Zuständigkeit

Der Nutzer meldete den Start mit `pinctrl set 18 op dh` und beobachtete einen
Lauf mit voller Leistung. Damit galt die frühere angefragte Stillstandsbedingung
nicht mehr. Der tatsächliche Ausführungszeitpunkt und eine gemessene Drehzahl
wurden nicht mitgeteilt. Der Journaleintrag vom **09.09.2026, 18:23:45,933386 UTC**
(20:23:45,933386 CEST) ist der Protokollierungszeitpunkt dieser Angabe, kein
rückwirkend bestimmter Schaltzeitpunkt.

Der Nutzer hat das softwareseitige Ausschalten, Einschalten und Einstellen des
PWM-Tastgrads für die vereinbarten Prüfungen ausdrücklich übertragen. Er soll
keine Steuerbefehle mehr selbst eingeben. Die damaligen Rückfragen betrafen Montage-/Betriebspunktangaben und physische
Zustandsbestätigungen; GPIO18 und Sensorbefestigung sind inzwischen abschließend
geklärt.

Die nachfolgende Nutzerantwort wurde um **18:28:27,909631 UTC**
(20:28:27,909631 CEST) protokolliert. Der Nutzer bestätigt vollständigen
Stillstand als Sichtbeobachtung und wünscht für den nächsten Betriebspunkt
ausdrücklich **25 % PWM**. Außerdem nennt er den ARCTIC P12 Pro PST mit 120 mm,
eine vom Pi getrennte externe 12-V-Versorgung sowie einen in Lüfternähe
befestigten ADXL345 mit I²C. GPIO18 ist nach seiner Angabe über Jumperkabel und
Adapter verbunden. Als Antwort auf die Tachofrage nennt er ebenfalls GPIO18;
diese Angabe führte damals zur Rückfrage nach der Steckerzuordnung. Die
abschließende Nutzerklärung bestätigt GPIO18 als Steueranschluss. Kein Umbau ist angefordert.

## Geprüfte Zuordnung und Ausgangskonfiguration

| Größe | Festgestellter Stand | Aussagegrenze |
|---|---|---|
| Pinbezeichnung im Nutzerbefehl | GPIO18; lokales `pinctrl -p get 12,18` ordnet physischen Pin 12 zu | Physischer Pin 18 ist GPIO24 und wurde nicht als Lüfterausgang verwendet |
| Pin-Funktion | Für Hardware-PWM auf GPIO18: `a3`, Anzeige `PWM0_CHAN2` | Eine Funktionsanzeige misst keinen elektrischen Signalverlauf am Lüfter |
| Kernel-PWM | `pwmchip0/pwm2`, kompatibel mit `raspberrypi,rp1-pwm` | Numerische Chipnamen gelten für den lokal geprüften Systemstand |
| Gerätepfad | `/sys/devices/platform/axi/1000120000.pcie/1f00098000.pwm` | Identifiziert den Controller, keine mechanische Verdrahtungsprüfung |
| Bootkonfiguration | `/boot/firmware/config.txt` enthält `dtoverlay=pwm` | Kein Beleg für einen historischen Betriebspunkt |
| Gespeicherte Vorgabe vor Übernahme | 40.000 ns Periode, 10.000 ns Tastzeit, `enable=1`, Polarität `normal`; rechnerisch 25 % bei 25 kHz | Weder frühere Halbierung noch aktueller Drehzahlwert daraus ableitbar |
| Vorhandene Python-Anbindung | `rpi_hardware_pwm` in `.venv`, `.venv_tf` und System-Python nicht importierbar | Der vorhandene Kernel-PWM-Kanal ist dennoch über sysfs zugänglich |
| Prozessprüfung | Kein konkurrierender Erfassungs- oder Lüftersteuerungsprozess bei der Prüfung erkannt | Momentaufnahme; spätere Fremdzugriffe bleiben möglich |

`pinctrl set 18 op dh` wählt GPIO18 als normalen Digitalausgang und setzt ihn
auf High. Für einen mittleren Tastgrad muss die PWM-Pinfunktion wieder aktiv
sein. Ein gespeicherter Zwischenwert wirkt nicht allein dadurch am Anschluss,
dass er im PWM-Subsystem steht. Vor der Abschaltung wurde zunächst Digital-High
gelesen; unmittelbar vor dem protokollierten eigenen Schreibzugriff zeigte die
Abfrage bereits wieder `a3`. Ursprung und Zeitpunkt dieser dazwischenliegenden
Muxänderung sind ungeklärt. Sie werden keiner Person oder Anwendung ohne Beleg
zugeschrieben.

## Tatsächlich ausgeführte Abschaltung

Die Abschaltung wurde vor dem Zugriff angekündigt. Die folgenden Zeitangaben
stammen aus `results/fan_control_20260909/control_events.jsonl`; UTC + 2 Stunden
ergibt die lokale Sommerzeit CEST. Befehle und sysfs-Schreibzugriffe sind mit
Anforderung, Abschluss und Rücklesung getrennt journalisiert.

| Zeitpunkt am 09.09.2026, UTC | Steuerereignis | Protokolliertes Ergebnis |
|---|---|---|
| 18:23:45,949244 | `pinctrl set 18 op dl` angefordert | Rückgabecode 0 um 18:23:45,955951; normaler Digitalausgang auf Low angefordert |
| 18:23:45,960826 | `/sys/class/pwm/pwmchip0/pwm2/duty_cycle` auf `0` geschrieben | Rücklesung `0` um 18:23:45,964705 |
| 18:23:45,968807 | `/sys/class/pwm/pwmchip0/pwm2/enable` auf `1` geschrieben | Rücklesung `1` um 18:23:45,972551 |
| 18:23:45,977138 | `pinctrl set 18 a3` angefordert | Rückgabecode 0 um 18:23:45,983487 |
| 18:23:45,990501 | Gesamten Sollzustand zurückgelesen | 0 %, 25 kHz, normale Polarität; GPIO18 als `a3`, `PWM0_CHAN2`, Low |
| 18:23:56,002468 | Angeforderte Wartezeit von 10 s abgeschlossen | PWM- und Pinzustand erneut unverändert zurückgelesen |

Das zeitweilige Digital-Low ermöglicht den Wechsel auf die bereits auf 0 ns
gesetzte Hardware-PWM-Konfiguration. Danach bleibt der PWM-Kanal aktiviert;
die Tastzeit ist null. Es wurde kein mittlerer Tastgrad oder Betriebspunktlauf
neu angefahren. Der ausgelesene Low-Pegel ist kein Oszilloskopnachweis am Lüfter.

**Aktueller belegter Softwarezustand: 0 % bei 25 kHz, GPIO18 in Funktion a3.**
Direkt nach der zehnsekündigen Wartezeit war mechanischer Stillstand noch
unbestätigt; die spätere Nutzerantwort bestätigt ihn als Sichtbeobachtung.
`rpm_measured` bleibt im Journal `null`; ohne bestätigten Anschluss wurde kein
Tachosignal des Prüflüfters gemessen. Ein Drehzahlwert des eigenen Pi-Kühlers
wird dem Prüflüfter nicht zugeordnet. Der nun gewünschte Sollwert von 25 % wurde
noch nicht angefahren.

Das [Herstellerdatenblatt des P12 Pro PST](https://www.arctic.de/media/2c/de/c6/1750758983/Spec_Sheet_P12_Pro_PST_EN.pdf)
weist am **Lüfterstecker** Pin 1 als GND, Pin 2 als +12 V, Pin 3 als Tachoausgang
und Pin 4 als PWM-Eingang aus. Diese Nummern bezeichnen weder die physischen
Pi-Stiftleistenpins noch GPIO-Nummern. Zu klären ist, mit welchem Steckerkontakt
GPIO18 über den vorhandenen Adapter tatsächlich verbunden ist und ob Pin 3
zusätzlich zu einem anderen, geeigneten Eingang führt. Die Nutzerantwort
„Ja GPIO18“ wird deshalb nicht als bestätigter Tachoanschluss übernommen.

## Damaliger Klärungsbedarf vor Eingang der abschließenden Nutzerangabe

- Sensorbefestigungsmittel, genauer Montageort und Achsausrichtung;
  Lüfterbefestigung und Unterlage sowie Bestätigung unveränderter Montage.
- Tatsächliche Steckerzuordnung des vorhandenen GPIO18-Anschlusses und des
  behaupteten Tachos; die Steuerausgangszuordnung wird nicht als Eingang für
  Drehzahlerfassung verwendet.
- Frühere Ausgangs-/Zielwerte der Halbierung und ihre Skala bleiben getrennt zu
  dokumentieren, soweit erinnerlich.
  Eine nicht mehr bekannte historische Vorgabe bleibt unbekannt.
- Für einen tatsächlich angeschlossenen Tacho: separater GPIO,
  Beschaltung/Pull-up-Spannung und bekannte Impulse je Umdrehung. Ohne diesen
  Nachweis bleibt die Drehzahl ungemessen.

Stillstand und nächster Sollwert sind bereits beantwortet und müssen ohne
weitere Zustandsänderung nicht erneut erfragt werden. Die Bestätigung ersetzt
keinen gemessenen RPM-Wert; 0 % bleibt eine Stellgröße. Die neue Festlegung
von 25 % ist von der weiterhin ungeklärten historischen Halbierung getrennt.

Die nachträgliche Aussage zum ausgeschalteten Lüfter im früheren Durchlauf
bleibt erhalten. Auslaufzeit, Berührungen, Fremdschwingungen und Änderungen
zwischen damaligen Aufnahmen waren jedoch nicht zeitgleich bestätigt und
werden nicht nachträglich als kontrolliert erklärt.

Nach Montageklärung und geklärter Steckerzuordnung wird bei weiterhin
bestätigtem Stillstand der Beginn der **30-s-
Stillstandsaufnahme** ausdrücklich angekündigt. Die korrigierte ADXL345-
Erfassung verwendet zunächst 200 Hz ODR, Full Resolution, ±2 g und FIFO.
Die Aufnahme erhält den Zweck `pilot`, nicht `training`.

Erst anschließend wird der konkrete Betriebspunkt **D₁ = 25 %** angekündigt.
Die Software übernimmt das Einschalten und hält den Betriebspunkt konstant.
Die geplante Einlaufphase beträgt zunächst **30 s**; anschließend folgt die
Startansage für den **30-s-Betriebspiloten**. Laufstabilität muss anhand der
beobachteten beziehungsweise gemessenen Bedingungen beurteilt werden und ist
nicht allein durch eine abgelaufene Wartezeit nachgewiesen. Während jeder
Aufnahme bleiben Montage und Betriebspunkt unverändert. Die vorhandene
erkennungsabhängige Abschaltdemonstration wird für den Methodenvergleich nicht
gestartet.

Stillstands-/Betriebspiloten, Signalqualitäts- und Spektralprüfung, begründete
endgültige Messparameter, neue Trainings-/Validierungsaufnahmen und unabhängige
Tests stehen weiterhin aus. Bis zum Stand dieses Nachtrags wurde keine neue
Sensoraufnahme und kein neues Training gestartet. Für den zweiten normalen
Betriebspunkt bleiben Modelle, Skalierung und sämtliche Schwellen unverändert.

## Worddatei und Nachweisgrenzen

Vor der nächsten Wordüberarbeitung wurde die vorhandene Fassung gesichert:
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_steuerungsuebernahme_20260909.docx`.
SHA-256: `e3ecba898af615b8c6975801e97573e61cb68668b9a3a86305506db6297ac614`.
Die zuvor bereits gesicherte ursprüngliche Fassung bleibt zusätzlich erhalten.

Die Kapitelquelle `docs/implementierung_20260909.md` integriert Zustandsänderung,
Pinzuordnung, ausgeführte Abschaltung und offene mechanische Bestätigung in
die bestehenden Abschnitte. Aussagen über fehlende Steuerzugriffe beziehen sich
ausdrücklich auf die frühere ausschließlich lesende Phase. Die Übertragung in
die Worddatei sowie die anschließende Format-, Tabellen- und Nummerierungsprüfung
sind abgeschlossen und im abschließenden Abschnitt dieses Nachtrags belegt. Evaluationsergebnisse oder erfüllte Hypothesen werden
aus diesen Steuerbefunden nicht abgeleitet.

## Implementierter gemeinsamer Steuerweg und Softwareprüfung

`src/fan_pwm.py` verwendet den vorhandenen Kernel-Hardware-PWM-Kanal ohne
zusätzliche PWM-Pythonbibliothek. Vor einem Stellbefehl werden RP1-Gerätepfad,
GPIO18/physischer Pin 12, Kanal 2, 40.000-ns-Periode und normale Polarität geprüft.
Eine gemeinsame Sperre verhindert den gleichzeitigen Zugriff kooperierender
Controller. Import und Konstruktion greifen nicht auf Hardware zu. Der offene
Kontext hält die Sperre und protokolliert lesende Prüfungen; das Schließen dieses
Kontexts lässt die letzte Vorgabe bestehen. Nur `set_percent()` und `stop()`
ändern den Ausgang. Nach Fehlern erfolgt kein stillschweigender Ersatzbefehl.

`FanController` in `live_monitor.py` und der Entwicklungsmodus in
`live_tflite_fan_control.py` nutzen jetzt diesen gemeinsamen Steuerweg. Beim
Programmstart setzt der Adapter ausdrücklich seine Vorgabe; beim Beenden
fordert er 0 % bei aktiviertem PWM-Kanal an und gibt die Sperre frei. Das gilt
auch beim Abbruch der Erfassung. Sein historischer Attributname `is_running`
bezeichnet ausschließlich eine bestätigte Vorgabe größer null. Nach einem nicht
bestätigten Stellbefehl ist der Status unbekannt (`None`), nicht „Stillstand“.
Die GUI wird erst beim Aufruf des GUI-Hauptprogramms eingerichtet. Direkte
`pinctrl`-/Sysfs-Zugriffe anderer Programme umgehen die Sperre weiterhin; die
Prozessprüfung vor Aufnahmen bleibt erforderlich.

Die abschließende hardwarefreie Regression bestand mit **113 Tests und zwölf
Untertests** (`software_tests_final_v5.xml` in `results/fan_control_20260909`).
Davon prüfen 28 Fälle das Backend und 24 den Adapter einschließlich Fehler- und
Abschlusspfaden. Temporäre Sysfs-Nachbildungen und simulierte Pinrückmeldungen
ersetzen dabei die Hardware. Der erste gemeinsame Lauf zeigte drei Fehler durch
einen GUI-Backendwechsel beim Import; `software_tests_final.xml` bleibt als
Fehlerbeleg erhalten. Nach Verlagerung der GUI-Einrichtung an den Programmeinstieg
bestanden 104 Tests, anschließend mit zwei zusätzlichen Abschlussprüfungen 106.
Der neue Backend-Steuerweg wurde auf dem realen Pi bisher nur mit `verify(0)`
lesend geprüft (`backend_read_only_check.json` und zugehöriges Journal).
Keiner dieser Tests hat den Lüfter eingeschaltet oder Sensordaten aufgenommen.

Die unabhängige Quelltextprüfung fand keine blockierenden Fehler im Backend oder
in dessen 28 Prüffällen. Eine solche Prüfung belegt keine elektrische Signalform,
Drehzahl oder Eignung der mechanischen Messkette. Sämtliche neuen Stellfunktionen
benötigen ihre noch ausstehende reale Prüfung in der angekündigten Pilotfolge.

Die anschließende Adapterprüfung fand einen übersprungenen Aktorabschluss bei
Fehlern aus `acquisition.stop()`, eine veraltete Abschlussmeldung sowie eine
falsch als Dry-Run bezeichnete Zeitbasis bei real fehlgeschlagenem Stopbefehl.
Diese drei Befunde wurden behoben. Sieben zusätzliche Tests decken die
Abschlussfehler, die Trennung von simulierten und realen Befehlen und die
Aussagegrenzen der Ereignisse ab. Bei einem Fehler in einer neuen Testnachbildung
fehlte zunächst deren nominelle Samplingrate; dieser Fixturefehler ist korrigiert.
Der Endlauf bestand mit 113 Tests und zwölf Untertests. Frühere Testberichte
bleiben als Entwicklungsverlauf erhalten; maßgeblich ist die Fassung v5.

Die erneute ausschließlich lesende Abschlussprüfung bestätigte die unveränderte
0-%-Vorgabe bei aktivierter 25-kHz-PWM und GPIO18 in `a3`. Es waren keine passenden
Steuer-/Erfassungsprozesse und keine Halter der geprüften Geräte erkennbar. Die
293 im Ausgangsmanifest erfassten Daten-/Modell-/Ergebnisdateien blieben
hashidentisch (`preservation_and_state_final.json`). Dieses Ergebnis betrifft
Dateierhaltung und ausgelesene Konfiguration, keine mechanische Messqualität.

### Abgeschlossene Word-Aktualisierung nach Steuerungsübernahme

Die überarbeitete Nutzerdatei `docs/Akz_Masterarbeit_Bericht(3).docx` wurde nach
Hashprüfung der gesicherten Vorfassung atomar ersetzt. Kapitel 6 dokumentiert
jetzt die Steuerungsübernahme, die visuelle Stillstandsbestätigung, den neu
gewählten Sollwert von 25 %, die weiterhin offenen Montage-/Tachoangaben und die
geprüfte Implementierung einschließlich der 113 Tests und zwölf Untertests.
Die beiden Ausgangskopien bleiben unverändert. Ziel-SHA-256:
`a1f5c1e52ccd0c0babb64d3cc4035e70323fb1fe564d960f1cf6bbb6cf78c995`.

Die neue Layout-PDF umfasst 55 Seiten; Kapitel 6 belegt die arabischen Seiten
29–40. Die 187 XML-Blöcke der Kapitel 1–5 und drei Formelobjekte sind unverändert.
Die fünf neuen Tabellen 6-1 bis 6-5, Überschriften 6.1 bis 6.7, Inhalts- und
Tabellenverzeichnis wurden strukturell und visuell geprüft. Alle fünf neuen
Tabellen stehen vollständig auf jeweils einer Seite; Zelltexte sind nicht
abgeschnitten. 76 Seitenverweise wurden aktualisiert; zwei Renderläufe liefern
identische Positionen für 109 Lesezeichen. Die Prüfung erfolgte mit LibreOffice
und eingebetteten Ersatzschriften, nicht in Microsoft Word selbst.

Belege: `results/fan_control_20260909/docx_final_verification.json`,
`docx_structure_check_final_v2.json` und `word_layout_final_v2/report.pdf` im
selben Ergebnisordner. Der Dokumentrenderer wurde danach beendet. Im
Evaluationskapitel wurden keine Mess- oder Güteergebnisse ergänzt. Ein neuer
Commit oder Push wurde nicht erstellt.

## Abschließende Hardwareklärung und weitere Softwareprüfung

Der Nutzer hat GPIO18 ausdrücklich als Anschluss zur Lüfteransteuerung bestätigt.
Der ADXL345 ist entsprechend der vorgesehenen I²C-Beschaltung angeschlossen und
an einer Ecke des Lüfterrahmens befestigt, um die dort auftretenden Vibrationen
zu erfassen. Diese Angaben werden als feste Randbedingungen übernommen. Die
bisherigen Rückfragen zu Steueranschluss und Sensorbefestigung sind damit erledigt;
ein erneuter Nachweis der Steckerzuordnung oder ein Neuaufbau wird nicht verlangt.
Die generische Montagekennung `fan_frame_corner_adxl345_gpio18_v1` bezeichnet
diesen Aufbau, ohne eine nicht mitgeteilte Ecke, Achsausrichtung oder konkrete
Befestigungsmittel zu erfinden.

Die Bestätigung beschreibt den Aufbau, nicht dessen bereits gemessene
Signalqualität. GPIO18 wird als Steueranschluss geführt; daraus entsteht kein
separater Tachokanal oder Drehzahlmesswert. Die frühere Antwort „Ja GPIO18“ bleibt
als historischer Wortlaut erhalten. Eine unabhängige Drehzahl liegt weiterhin
nicht vor; das Feld bleibt `null`. Dies ist eine Aussagegrenze der Auswertung
und kein erneutes Hardware-TODO zu den bestätigten Punkten.

Die geplante Pilotfolge sowie Training und Evaluation bleiben als nachfolgende
Messaufgaben erhalten. Der jetzige Auftrag betrifft ausdrücklich die weitere
Softwareprüfung und die Wordbearbeitung. Während dieser Arbeit werden keine
PWM-Stellbefehle, Sensoraufnahmen oder Trainingsläufe ausgeführt. Frühere
Messprotokolle werden nicht verändert und frühere Daten nicht rückwirkend als
kontrollierte Stillstandsreferenz eingestuft.

Vor der DOCX-Bearbeitung wurde die letzte geprüfte Fassung gesichert unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_hardwarebestaetigung_20260909.docx`.
Ihre SHA-256 lautet
`a1f5c1e52ccd0c0babb64d3cc4035e70323fb1fe564d960f1cf6bbb6cf78c995`.
Die aktuelle Nutzerangabe und der Sicherungsnachweis liegen gesondert unter
`results/hardware_confirmation_20260909/user_confirmation_and_backup.json`.

### Abgeschlossene Prüfung der FFT-Eingangskontrolle

Die rein softwareseitige Prüfung zeigte, dass `fft_pilot.analyze()` zuvor
unbekannte/leere Qualitätsflags, fraktionale Zeit-/Indexangaben und einen von
der CSV abweichenden Manifest-Samplezähler akzeptieren konnte. Ein nichtendlicher
Schlusswert außerhalb vollständiger FFT-Segmente führte erst nach Schreiben von
`spectra.csv` zum Fehler. Diese Fälle wurden ausschließlich an künstlichen
CSV-Dateien reproduziert; keine Bestandsaufnahme wurde verändert.

Die neue Vorprüfung liest CSV-Felder zunächst als Text, verlangt bekannte
fehlerfreie Flags, die vollständige Indexfolge ab null, passende Samplezahl,
ganzzahlige monotone Hostzeiten und endliche XYZ-Werte einschließlich Segmentrest.
Host-Nanosekunden werden ohne Float-Zwischenkonvertierung verarbeitet. ODR und
Segmentlänge werden ebenfalls geprüft. Ungültige Eingaben scheitern vor Anlage
des Ergebnisordners. Dies verbessert die technische Eingangskontrolle, ohne
bereits eine ausreichende Signalqualität der Messkette zu behaupten.

Die 81 FFT-Tests einschließlich 79 neuer Fälle bestanden. Der erste Gesamtlauf
zeigte drei GUI-Importfehler nach vorheriger FFT-Grafikausgabe. Die TFLite-GUI
wählt deshalb ihren interaktiven Grafikmodus nun erst im Hauptprogramm; ihre
Klassen lassen sich ohne Grafikmoduswechsel importieren. Der abschließende
Gesamtlauf bestand mit **192 Tests und zwölf Untertests**. Belege:
`results/hardware_confirmation_20260909/software_tests.xml` (erster Lauf) und
`software_tests_final.xml` (erfolgreicher Endlauf). Eine reale GUI-Sichtprüfung
oder Prüfung der mechanischen Messqualität wurde damit nicht durchgeführt.

## Fortsetzung der ursprünglich vereinbarten Messfolge

Nach Abschluss der Software- und Wordphase wurden die bestätigten
Hardwarebedingungen für die bereits beauftragte Stillstandsaufnahme übernommen.
Die rein lesende Vorprüfung bestätigte bei unveränderter Boot-ID weiterhin
0 % / 25 kHz / aktivierten PWM-Kanal und GPIO18 in Funktion a3. Es waren keine
konkurrierenden Gerätehalter erkennbar. Der Dokumentrenderer war vor der
Sensoraufnahme vollständig beendet. Die frühere visuelle Stillstandsbestätigung
wurde als weiterhin geltende Nutzerangabe geführt; kein nachfolgender Zustands-
oder Montagewechsel war mitgeteilt. Die Sensoraufnahme wurde ausdrücklich
angekündigt, ohne einen PWM-Stellbefehl auszuführen.

Am **09.09.2026 ab 20:08:39 UTC** wurde die neue 30-s-Aufnahme
`data/controlled_20260909/standstill_20260909_200838.csv` erstellt. Sie ist als
`pilot` und `controlled_standstill` gekennzeichnet. Label −1 bedeutet hier keine
Zuordnung zu einer Normal-/Anomalie-Trainingsklasse; die physische Referenz ist
Stillstand. Sie wird nicht für das Normaltraining des laufenden Lüfters verwendet.

| Größe | Tatsächlicher Befund dieser neuen Aufnahme |
|---|---|
| Status / Samples | completed / 6.193 |
| ODR-Vorgabe / beobachteter FIFO-Durchsatz | 200 Hz / 206,479669 Werte/s |
| Größte Hostzeitdifferenz / FIFO-Füllstand | 7,103851 ms / ein Eintrag |
| Gap / Overrun / Sättigung | jeweils null gesetzte Flags |
| AC-RMS X/Y/Z | 0,006465 / 0,005462 / 0,009024 g |
| Betrag des Achsenmittelwertvektors | 1,100864 g, ohne Offset-/Skalierungskorrektur |
| FFT-Segmentierung | 23 Segmente, Hann, 512 Samples, Schritt 256 |
| Frequenzstützstellenabstand | 0,403281 Hz aus beobachtetem Durchsatz |
| Größte PSD-Stützstelle X/Y/Z | 55,653 / 80,253 / 75,010 Hz; keine Rotationszuordnung |

CSV-SHA-256:
`1f2f5f24ff34ca1f6c1c863daa4d325ef9e98f2e929a66eaf47adb81c5ec25cb`.
Belege in `results/hardware_confirmation_20260909/`:
`standstill_20260909_200838_session.json`, zugehöriges Fan-Journal,
`standstill_quality.json` und `standstill_fft/`. Vor und nach der Aufnahme wurde
0 % zurückgelesen. Null Flags beweisen keine exakte Zahl physikalisch verlorener
Werte. Die Hintergrundaufnahme allein belegt weder Betriebs-SNR noch ausreichendes
Nutzband oder endgültige Messparameter. Die historischen Messprotokolle und Labels
bleiben unverändert.

Danach wurde **Lüfter AN, 25 % PWM bei 25 kHz, zunächst 30 s Einlaufzeit, danach
30 s Aufnahme** angekündigt. Der Nutzer antwortete ausdrücklich **„Ja, bereit“**.
Am **20:11:58 UTC** setzte `FanPWM.set_percent(25)` den Tastgrad auf 10.000 ns bei
40.000 ns Periode; die Rücklesung bestätigte aktivierten Kanal und Hardware-PWM-
Pinzuordnung. Dies war der erste reale Stellaufruf des neuen Backendmoduls.
Die mindestens 30-s-Einlaufphase ist abgeschlossen. Die Betriebsaufnahme wartet
noch auf die separat angefragte Sichtbeobachtung des tatsächlichen Laufs; ein
PWM-Readback wird dafür nicht als Drehzahl- oder Laufnachweis ausgegeben.
Der Steuerprozess hält dabei exklusiv die gemeinsame Sperre. Dies ist eine
Zustandsprüfung nach dem Einschalten, keine erneute Frage zur abgeschlossenen
Verkabelung oder Sensorbefestigung.

### Wordabschluss mit neuem Stillstandsbeleg und aktueller Messbereitschaft

Die Worddatei enthält nun die abschließend bestätigten Hardwarebedingungen,
die erweiterte Softwareprüfung (192 Tests und zwölf Untertests), die neue
kontrollierte Stillstandsaufnahme und den anschließend eingestellten 25-%-
Betriebspunkt. Die Betriebsaufnahme selbst ist weiterhin nicht begonnen; der
Steuerprozess wartet auf die Sichtbestätigung des tatsächlichen Laufs. Daraus
werden keine Betriebs-SNR-, Drehzahl-, Trainings- oder Evaluationsergebnisse
abgeleitet.

Die vor diesem Messnachtrag gespeicherte Wordfassung ist gesichert unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_stillstandsnachtrag_20260909.docx`
(SHA-256 `6d24b0263be60b3845be4e994b66e1bd54f94ef17991caa4e232662e22977f72`).
Die neue Zieldatei hat SHA-256
`b5fb09c6df5bd4020cc6786cd8057a19d6ebb513b780a56131f331e6722e8139`.
Die PDF-Layoutprüfung umfasst 57 Seiten; Kapitel 6 liegt auf den arabischen
Seiten 29–42. Kapitel 1–5 mit 187 XML-Blöcken und drei Formeln sind unverändert.
Fünf neue Tabellen, Überschriften und Verzeichnisse sind strukturell und visuell
geprüft; die Seitenpositionen beider Renderläufe stimmen überein. Prüfbelege:
`results/hardware_confirmation_20260909/standstill_word/word_update_final.json`
und die zugehörigen Render-/Auditdateien. Alle Dokumentrenderer sind beendet.

Für die Fortsetzung hält der laufende Steuerprozess exklusiv den PWM-Lock bei
25 %; keine Sensorerfassung läuft parallel. Der Zustand und die Fortsetzungssperre
sind in `results/hardware_confirmation_20260909/pending_operating_pilot.json`
festgehalten. Erst eine positive Sichtbeobachtung und die Aufnahmeansage geben
die Betriebsaufnahme frei. Die bereits bestätigten GPIO18-/Montageangaben werden
nicht erneut erfragt. Alle 293 im ursprünglichen Erhaltungsmanifest erfassten
Daten-, Modell- und Ergebnisdateien sind weiterhin hashidentisch. Kein Commit
oder Push wurde erstellt.

## Bestätigter Betriebspilot bei 25 % PWM

Der Nutzer bestätigte anschließend ausdrücklich: „Ja, der Lüfter läuft sichtbar
gleichmäßig. Sensor und Montage sind unverändert. Du kannst die Betriebsaufnahme
ankündigen und starten.“ Damit ist die zuvor ausstehende Zustandsbeobachtung
beantwortet. Nach erneuter Aufnahmeansage wurde die vorgesehene 30-s-Betriebsaufnahme
am **09.09.2026, 20:24:35 UTC (22:24:35 CEST)** begonnen und vollständig beendet.

Datei: `data/controlled_20260909/operating25_20260909_201158.csv`. Der Dateiname
enthält den Beginn der Steuersitzung, nicht den Beginn der Erfassung. Letzterer
steht im Aufnahmejournal. CSV-SHA-256:
`a8c882263a69be2290883cfaf959063a2b1a124ed76b97bb631f528abbbee583`.
Die Aufnahme enthält **6.205 Werte**, beobachteten FIFO-Durchsatz
**206,846521 Werte/s**, maximale Hostzeitdifferenz **6,008778 ms** und maximal
einen FIFO-Eintrag. Gap-, Overrun- und Sättigungsflags sind jeweils null.
Sensorvorgaben und Registerrücklesung entsprechen dem Stillstandspiloten:
200 Hz ODR, Full Resolution, ±2 g, FIFO-Stream, I²C-Konfiguration 100 kHz.

Die erste Stabilisierungsphase dauerte 30,000110 s. Wegen der anschließenden
Wartezeit auf die Sichtbestätigung lagen zwischen dem Einstellen der 25 %
und dem Aufnahmebeginn insgesamt **756,907159 s**. Diese tatsächliche Dauer
ersetzt im Versuchsbericht nicht nachträglich die Mindestplanung; beide Größen
werden getrennt angegeben. Der PWM-Tastgrad wurde währenddessen nicht geändert.
Vor und nach der Aufnahme bestätigte die Rücklesung 10.000 ns Tastzeit bei
40.000 ns Periode, `enable=1` und GPIO18 in `a3/PWM0_CHAN2`.

Der Steuerprozess hat nach Abschluss seinen Lock freigegeben und den letzten
Stellwert von 25 % beibehalten. Der Sensorzugriff wurde geschlossen. Die
Sichtbeobachtung belegt tatsächlichen Lauf, aber keine gemessene oder exakt
konstante Drehzahl. RPM bleibt ungemessen. Belege:
`results/hardware_confirmation_20260909/operating25_20260909_201158_session.json`
und zugehöriges Fan-Journal sowie `results/operating_confirmation_20260909/`.
Die Paaranalyse und die Entscheidung über die endgültigen Messparameter folgen;
noch wurde kein neues Modell trainiert.


## Wiederholter Betriebspilot und erneute Abschaltung

Wegen der geringen Betriebs-/Stillstandstrennung wurde eine zweite 30-s-
Betriebsaufnahme bei unverändert **25 % PWM und 25 kHz** angekündigt und am
09.09.2026 ab **20:32:10 UTC** durchgeführt. Datei:
`data/controlled_20260909/operating25_repeat_20260909_203210.csv`.
Sie enthält 6.205 Werte bei einem beobachteten FIFO-Durchsatz von
206,862884 Werten/s. Das größte Hostintervall beträgt 6,057078 ms;
Gap-, Overrun- und Sättigungsflags sind jeweils null, der größte beobachtete
FIFO-Füllstand beträgt einen Eintrag. Der Vektor-AC-RMS beträgt 0,012954 g.
Die fortgeltende Nutzerbeobachtung eines gleichmäßigen Laufs und unveränderter
Montage ist im neuen Aufnahmejournal als Quelle genannt. Eine unabhängige
Drehzahl wurde nicht erfasst. Während beider Betriebsaufnahmen blieb die Vorgabe
konstant; keine Erkennungsentscheidung steuerte den Lüfter.

Nach Abschluss wurde der Lüfter wie angekündigt durch `FanPWM.stop()` am
**20:32:40,281593 UTC** auf **0 % PWM** gestellt. Zehn Sekunden Auslaufzeit
wurden abgewartet; Rücklesung: Tastzeit 0 ns, Periode 40.000 ns, `enable=1`,
GPIO18 `a3/PWM0_CHAN2`. Der Steuerprozess ist beendet und hat die gemeinsame
Sperre freigegeben; auch der Sensorzugriff ist geschlossen. Die Einstellung
wird nicht als mechanischer Stillstand bezeichnet. Für die nachfolgende
30-s-Stillstandsaufnahme S₁ steht eine neue Sichtbestätigung aus. Die alte
Bestätigung vor S₀ gilt nicht automatisch nach diesem zwischenzeitlichen Betrieb.
Belege: `results/operating_confirmation_20260909/operating25_repeat_20260909_203210_session.json`
und das zugehörige `_fan.jsonl`.

Die erste Paaranalyse liegt unter `results/paired_pilots_20260909/`.
Der Vektor-AC-RMS steigt zwischen S₀ und B₁ von 0,012371 auf 0,013099 g;
die Wertebereiche der 5-s-Abschnitte überlappen. Die summierte XYZ-Bandleistung
ist in den Diagnosebändern 1–90 Hz beziehungsweise 5–80 Hz um 0,510 und
0,592 dB höher. Die nur unter unverändertem, additivem und unkorreliertem
Hintergrund definierten Überschuss-SNR-Schätzungen betragen −9,042 und
−8,353 dB. Das sind keine unabhängig gemessenen Lüfter-SNR-Werte oder zuvor
festgelegte Freigabegrenzen. Einzelne schwache Spektralkandidaten werden geprüft;
weder vollständige Abwesenheit eines Lüftersignals noch ein ausreichend
abgesichertes Nutzband wird behauptet. Aus dem ersten Paar folgt keine
Trainingsfreigabe. S₁ soll mögliche zeitliche Änderungen des Hintergrundes prüfen.

### Softwareprüfung und Vorbereitung ohne Modellbildung

`common_comparison.calibrate` prüft deklarierte Sidecar-Prüfsummen jetzt vor
der Übernahme des Aufnahmezustands. Eine als geprüft deklarierte Messkette
benötigt Profilhashes und vollständige Qualitätsbelege; ohne diese entsteht
kein als `verified` gekennzeichnetes Bundle. Die erweiterte Regression umfasst
**200 bestandene Tests und zwölf Untertests**; Beleg:
`results/operating_confirmation_20260909/software_tests_final.xml`.
Die Tests greifen für diese Integritätsfälle auf temporäre Daten zurück und
belegen keine physikalische Messqualität.

Ein nicht ausführbarer Vorbereitungssatz für sechs Trainings- und zwei
Validierungsaufnahmen à 60 s und den gemeinsamen Methodenvergleich liegt unter
`results/operating_confirmation_20260909/training_and_independent_test_preparation.*`.
Die Freigabe bleibt falsch. Parameterentscheid, zweiter normaler PWM-Wert und
zukünftige Modellhashes werden nicht erfunden. Für den zweiten normalen
Betriebspunkt müssen Modelle, Skalierung und Schwellen des ersten Punktes
unverändert bleiben. Neue Trainings-/Validierungsaufnahmen und Modelle wurden
noch nicht erstellt. Die bestätigte GPIO18-Steuerung und die Sensorbefestigung
an einer Ecke des Lüfterrahmens bleiben feststehende Randbedingungen.


### Dreifachauswertung und vorläufiger Parameterentscheid

Die Ergänzung `results/paired_pilots_20260909/repeat_bracketing/` vergleicht S₀,
B₁ und B₁-Wiederholung bei unveränderten Diagnosebändern. In der Wiederholung
betragen die summierten XYZ-Bandleistungsverhältnisse gegenüber S₀ 0,347 dB
für 1–90 Hz und 0,371 dB für 5–80 Hz. Das bereits aus B₁ ausgewählte X-Band
um 71,51 Hz (±0,8 Hz) bleibt erhöht: 4,102 dB in der Wiederholung gegenüber
3,382 dB in B₁; alle sechs Wiederholungsabschnitte liegen über der ersten
Stillstandsreferenz. Das belegt einen wiederkehrenden spektralen Befund,
keine Drehzahl oder abschließende Eignung für die Anomaliedetektion.

Der vorläufige Entscheid unter
`results/operating_confirmation_20260909/provisional_parameter_decision.*`
bindet die drei CSV-Dateien und Begleitprotokolle über SHA-256. Für die noch
ausstehende S₁-Referenz bleiben 200 Hz ODR, FIFO, Full Resolution, ±2 g und
30 s erhalten, damit die Vergleiche dieselbe Konfiguration verwenden.
H = S = 128 bleibt die aktuelle Modelleingabe; deren endgültige Eignung ist
noch offen. Der Entscheid erteilt keine Trainingsfreigabe. Die begründeten
technischen Eingangskriterien sind erfüllt; neue Signal-, Drift- oder
Bandbreitengrenzen werden nicht nachträglich als bereits erfüllt behauptet.

Die Erhaltungsprüfung nach der Betriebswiederholung bestätigte alle **293**
ursprünglich geschützten Daten-, Modell- und Ergebnisdateien unverändert.
Zusätzlich sind die sechs neuen CSV-/JSON-Dateien des kontrollierten Piloten
gehasht. Beleg:
`results/operating_confirmation_20260909/preservation_after_operating_repeat.json`.
Der vorbereitete S₁-Runner erfordert eine neue tatsächlich erhaltene positive
Sichtbestätigung; er wurde nicht ausgeführt. Es läuft keine Sensoraufnahme.


## Wordabschluss nach beiden Betriebspiloten und Fortsetzungszustand

Die vor dem Betriebsnachtrag gesicherte Wordfassung liegt unter
`docs/backups/Akz_Masterarbeit_Bericht(3)_vor_betriebsnachtrag_20260909.docx`
(SHA-256 `b5fb09c6df5bd4020cc6786cd8057a19d6ebb513b780a56131f331e6722e8139`).
Die aktualisierte Zieldatei `docs/Akz_Masterarbeit_Bericht(3).docx` hat SHA-256
`a9a5d7d17b28098f554240a3e1650881e252db679f33319a1d11164b3246cbb8`.
Kapitel 6 enthält die tatsächlich abgeschlossenen Piloten S₀, B₁ und B₁-W,
die vorläufige Analyse, 200 Tests und zwölf Untertests sowie den zusätzlichen
Integritätsnachweis. Anforderungen und Hypothesen werden dadurch nicht pauschal
als erfüllt ausgegeben. S₁, die endgültige Messparameterfreigabe, neue Trainings-
und Validierungsaufnahmen sowie unabhängige Evaluation bleiben ausdrücklich offen.

Die Strukturprüfung bestätigt 187 unveränderte XML-Blöcke der Kapitel 1–5 und
drei unveränderte Formeln. Die PDF-Layoutprüfung umfasst 58 Seiten; Kapitel 6
liegt auf den arabischen Seiten 29–43. Alle 15 Kapitelseiten und die drei
Verzeichnisseiten wurden visuell geprüft. Tabellen 6-1 bis 6-5, Überschriften
6.1 bis 6.7 und Seitenverweise stimmen. Beide finalen Renderläufe liefern
identische Seitenpositionen für 109 Bookmarks; 76 Seitenverweisfelder wurden
mit passenden Cachewerten versehen. Die Prüfung erfolgte mit LibreOffice und
PDF-Rendering, nicht mit einer nativen Microsoft-Word-Sitzung. Beleg:
`results/operating_confirmation_20260909/word_update/word_update_final.json`.

Alle Dokument-, Sensor- und Steuerprozesse sind beendet. Die abschließende
reine Rücklesung bestätigt **0 % PWM bei 25 kHz**, GPIO18 in `a3/PWM0_CHAN2`
und aktivierten PWM-Kanal. Kein weiterer Stellbefehl wurde dabei ausgeführt.
Ein mechanischer Stillstand nach der letzten Abschaltung wird ohne die noch
fehlende neue Nutzerbeobachtung nicht behauptet. Der Fortsetzungsbeleg lautet
`results/operating_confirmation_20260909/final_checkpoint.json`.
Nach der Sichtbestätigung ist die angekündigte 30-s-Referenz S₁ bei unveränderter
Montage vorgesehen. Der vorbereitete Runner benötigt einen tatsächlichen neuen
Bestätigungsbeleg; bislang wurde er nicht ausgeführt. Es wurde kein Commit oder
Push durch den Agenten erstellt.
