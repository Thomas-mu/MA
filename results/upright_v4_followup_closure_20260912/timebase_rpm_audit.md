# Abschlussprüfung der Drehzahl- und Sensorzeitbasisnachweise

Stand: 12.09.2026. Diese Prüfung wertet vorhandenen Quellcode, gespeicherte Konfigurationen, abgeschlossene Berichte und Herstellerquellen aus. Es wurden keine GPIOs, PWM-Vorgaben oder Sensorregister gelesen oder verändert, kein Gerät geöffnet und keine neue Aufnahme gestartet. Bestehende Dateien und das eingefrorene Modellpaket bleiben unverändert.

## Ergebnis und tatsächlich abschließbarer Umfang

Die vorhandene Softwareprüfung ist abgeschlossen: Es gibt keinen belegten Faktor-drei-Zählfehler, keinen falschen ODR-Registercode und keinen nachgewiesenen Fehler, der etwa 207 XYZ/s künstlich erzeugt. Der beobachtete Durchsatz ist korrekt als Hostbefund dokumentiert. Eine Abweichung des internen Sensortakts bleibt die durch Herstellerinformationen gestützte Erklärung; sie ist am konkreten Sensor noch nicht unabhängig gemessen.

Die tatsächliche Drehzahl des Prüflüfters wurde bislang nicht erfasst. Ein Tachosignal ist weder einem separaten Eingang noch einem dokumentierten Messgerät zugeordnet. Diese beiden physikalischen Nachweise können durch weitere Dateiauswertung allein nicht abgeschlossen werden. Dafür fehlen ein geeigneter externer Zeitbezug und eine tatsächliche Drehzahlmessung. GPIO18 ist bereits als PWM-Ausgang belegt und wird nicht zum Tachoeingang umgewidmet.

## 1. Quellenbasis und gesicherte Softwarebefunde

Geprüft wurden insbesondere [adxl345.py](../../src/adxl345.py), [pilot_sensor_source.py](../../src/pilot_sensor_source.py), [collect_real_data.py](../../src/collect_real_data.py), [fan_pwm.py](../../src/fan_pwm.py), die [Verkabelungs-/Steuerungsdokumentation](../../docs/steuerungsuebernahme_20260909.md), der [frühere Zeitbasisaudit](../mount_v2_review_20260911_085505/software_timebase_audit.json) und die [abschließende Laufzeitanalyse](../upright_v4_finalization_20260912_103145/runtime_analysis/analysis.json). Frühere Montageversionen werden hier ausschließlich als getrennte technische Historie betrachtet, nicht als gemeinsame Normalreferenz für v4.

| Gegenstand | Belegter Stand | Was daraus nicht folgt |
|---|---|---|
| Nominelle Sensor-ODR | `BW_RATE=0x0B`, Normal-Power-Modus; Softwarevorgabe 200 Hz | Keine kalibrierte Istfrequenz |
| Messbereich/Datenformat | `DATA_FORMAT=0x08`, Full Resolution, ±2 g, 0,0039 g/LSB als vorhandener Umrechnungsfaktor | Keine neue Empfindlichkeitskalibrierung |
| FIFO und Messmodus | `FIFO_CTL=0x90` = Stream mit Watermark 16; FIFO-Kapazität 32; `POWER_CTL=0x08` | Watermark 16 bedeutet weder 16 Hz noch 16 Messpunkte je CSV-Zeile |
| Interruptausgabe | `INT_ENABLE=0x00`; bisheriger Weg prüft Status per I²C | DATA_READY liegt deshalb nicht als bereits aktiviertes Messsignal an INT1/INT2 vor |
| Ein Datenpunkt | FIFO-Status > 0, danach ein Burst ab 0x32 mit sechs Bytes, Entpacken mit `<hhh`, genau eine XYZ-Zeile | Drei Achsenwerte sind kein dreifacher zeitlicher Durchsatz |
| Aufnahmedauer | Monotone Hostzeit begrenzt die Leseschleife; kein Sollzähler für 6.205 oder 62.000 Zeilen | Keine künstliche Festlegung auf 207 Hz |
| Nominale Zeitspalte | `sample_index / 200` | Kein zweiter Zeitmesser; der Index zählt erfolgreiche Softwarelesungen |
| Tatsächliche CSV-Zeit | `host_monotonic_ns` unmittelbar nach dem sechs Byte umfassenden Datenburst | Keine Wandlungszeitstempel des Sensors |
| Laufzeitquelle | `pilot_sensor_source.py` startet die 300-s-Dauer nach FIFO-Reset; der tatsächliche Versatz zum Stellbefehl bleibt separat dokumentiert | Kein Nullversatz zum PWM-Befehl; Modellabschnitt [180,300) bleibt auf den Stellbefehl bezogen |
| I²C-Konfiguration | 100 kHz aus dokumentierter Device-Tree-Konfiguration | Keine elektrisch gemessene SCL-Frequenz |

Der Abgleich mit dem Datenblatt bestätigt den Ratecode 0x0B, die zugehörige nominelle Bandbreite 100 Hz und die Empfehlung, 200 Hz nicht mit weniger als 100-kHz-I²C anzusteuern. Stream-Modus ist eine vom Hersteller genannte Lösung gegen asynchrone Datenregisterzugriffe. [Analog Devices, ADXL345 Rev. G](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf).

Die vollständigen Achsen werden zusammen gelesen. Zwischen aufeinanderfolgenden FIFO-Lesungen besteht durch I²C genügend Abstand für das Umschichten; die Anwendungsschrift erläutert die notwendige Wartezeit und den Zusammenhang zwischen FIFO-Status und abgeholten Daten. Ein entsprechender elektrischer Busmitschnitt dieses Prüfstands fehlt dennoch. [Analog Devices, AN-1025](https://www.analog.com/en/resources/app-notes/an-1025.html).

### 1.1 Tatsächlich beobachtete Rate

Die nachstehende Tabelle übernimmt die abgeschlossenen neun Sensorprozesse der Laufzeitmatrix; sie ist keine neue Aufnahme. Berechnung: `f_host = (N−1) / ((t_last_ns−t_first_ns)/1e9)`. Die fünfminütige Dauer bezieht sich auf den Leserstart. Alle neun Läufe sind Aufbau v4 bei 75 % PWM.

| Sensorprozess | XYZ-Punkte | Hostdurchsatz [XYZ/s] | Größter Hostabstand [ms] | Größter FIFO-Stand |
|---|---:|---:|---:|---:|
| RMS 1 | 62.126 | 207,088218 | 9,466 | 2 |
| Isolation Forest 1 | 62.125 | 207,085270 | 29,795 | 6 |
| Autoencoder 1 | 62.122 | 207,077267 | 8,945 | 2 |
| Isolation Forest 2 | 62.124 | 207,083938 | 29,517 | 6 |
| Autoencoder 2 | 62.130 | 207,103048 | 9,670 | 2 |
| RMS 2 | 62.126 | 207,087490 | 9,404 | 2 |
| Autoencoder 3 | 62.127 | 207,092912 | 10,088 | 2 |
| RMS 3 | 62.123 | 207,080149 | 9,226 | 2 |
| Isolation Forest 3 | 62.127 | 207,092741 | 30,278 | 6 |

Alle neun Analysen melden null Gap-, Overrun- und Sättigungsflags sowie streng zunehmende Hostzeitstempel. Größere Hostabstände im IF-Prozess gehen mit bis zu sechs gepufferten Werten einher. Das ist ein beobachteter Zusammenhang mit der Erfassung unter Rechenlast; er beweist keine verlorene Sensorwandlung. Quelle: [Laufzeitanalyse](../upright_v4_finalization_20260912_103145/runtime_analysis/analysis.json).

Die alten 30-s-Betriebsaufnahmen mit jeweils 6.205 Zeilen enthalten 6.205 vollständige XYZ-Punkte beziehungsweise 18.615 einzelne Achsenwerte. Für zwei solcher Aufnahmen wurden 206,8465 beziehungsweise 206,8629 XYZ/s aus den Hostzeiten berechnet. Die identische gerundete Punktzahl bedeutet keine identischen Zeitstempel. Eine letzte blockierende Lesung kann die Dauer geringfügig verlängern, erklärt aber nicht rund 205 zusätzliche Punkte. Auch ein maximal gefüllter, hier ohnehin zurückgesetzter FIFO könnte über 300 s nur etwa 0,107 XYZ/s zusätzlich erklären. [Vorhandener 30-s-Zähl- und Zeitaudit](../pwm50_investigation_20260910/sampling_rate_audit_before50.json).

Ein größerer Median der Hostleseabstände als der mittlere Abstand ist bei Polling und nachgeholten FIFO-Werten möglich. `1 / Median(Hostabstand)` ist daher kein Ersatz für den Durchsatz über die gesamte Aufnahme. Gleiche quantisierte XYZ-Tupel sind ebenso wenig ein unabhängiger Nachweis doppelter Messungen.

### 1.2 Gesicherter Kommentarfehler, keine belegte Ursache der Mehrpunkte

Der Kommentar in `adxl345.py:195` formuliert ungenau, wodurch Overrun gelöscht wird. Laut Registerbeschreibung werden DATA_READY, Watermark und Overrun durch Lesen der Datenregister gelöscht; andere Ereignisbits durch INT_SOURCE. Diese drei Statusfunktionen bleiben bei abgeschalteter Interruptausgabe wirksam. Der ausgeführte Code prüft INT_SOURCE tatsächlich **vor** dem Datenburst. Die Kommentarungenauigkeit widerlegt daher weder die Flagabfrage noch erklärt sie zusätzliche CSV-Zeilen. Sie war bereits im früheren Bericht offengelegt. [ADXL345, Register 0x2E–0x30, S. 26–27](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf).

Die Gap-Heuristik verwendet die nominelle Pufferzeit 32/200 = 160 ms. Bei angenommenen 207,09 XYZ/s wären 32 Perioden etwa 154,522 ms. Das ist eine begrenzte Empfindlichkeit dieser Heuristik, kein nachgewiesener Verlust in den vorhandenen Läufen: deren längster Hostabstand beträgt 30,278 ms und ihr größter beobachteter FIFO-Stand sechs. Statusabfrage und Datenburst sind außerdem keine atomare unabhängige Verlustzählung. `exact_lost_sensor_samples` bleibt deshalb `null`. Der eingefrorene Treiber und die bisherigen Fensterregeln werden nicht rückwirkend verändert.

## 2. Offene Ursachen und Aussagegrenzen

Ein originaler ADI-Mitarbeiterbeitrag nennt einen von der Kommunikationsuhr unabhängigen internen RC-Oszillator und eine Genauigkeitsstreuung von ±10 % über Temperatur und Drift. Der Beitrag empfiehlt DATA_READY als Zugang zur Messung der tatsächlichen ODR. Verwendet wurde die originale Antwort von ChrisM vom 07.01.2022, nicht die heute vorgeschaltete KI-Zusammenfassung. Das macht die hier beobachteten rund +3,54 % **plausibel**, beweist aber weder die konkrete Ursache noch eine garantierte individuelle Toleranz. [Originale ADI-Antwort](https://ez.analog.com/condition-based-monitoring/f/q-a/553781/adxl345---number-of-samples-for-odr---3200). Eine weitere originale Mitarbeiterantwort behandelt ausdrücklich unterschiedliche Exemplare bei eingestellten 200 Hz. [ADIApproved/Venkat, 05.06.2015](https://ez.analog.com/mems/f/q-a/86236/adxl345-tolerance).

Offen sind die unabhängige Frequenz des konkreten Sensors, die absolute Genauigkeit der Hostuhr, elektrische Übertragungsfehler jenseits der vorhandenen Meldungen sowie Einflüsse von Temperatur und tatsächlichem Bauteil. `CLOCK_MONOTONIC`, Nanosekundenauflösung, UTC-Uhr und NTP-Synchronisierung sind zusammen kein kalibrierter externer Sensortaktnachweis. Ein zweiter GPIO-Zähler auf demselben Pi kann Softwareabläufe gegenprüfen, liefert aber für sich keine unabhängige absolute Uhr.

Für die bisherigen RMS-/Modellvergleiche bleiben Eingabefenster, Vorverarbeitung und Abschnitte unverändert. Die Einordnung der Frequenzachse als hostgeschätzt bleibt bestehen. Insbesondere werden 200 Hz nicht in nachträglich „gemessene 207 Hz“ umbenannt, Rohdaten nicht neu abgetastet und alte Messungen nicht nach einem zukünftigen Befund umdatiert oder umklassifiziert.

## 3. Drehzahl: vorhandene Anschlüsse und tatsächlich fehlende Angaben

| Signal | Bestätigter Bezug | Noch nicht bestätigt |
|---|---|---|
| Lüfter-PWM | BCM-GPIO18, physischer Pi-Pin 12; RP1 PWM0_CHAN2, Funktion a3, Vorgabe 25 kHz | Elektrische Signalform direkt am Prüflüfter |
| Physischer Pi-Pin 18 | GPIO24, nicht GPIO18 | Kein belegter Prüflüfteranschluss |
| Tacho des Prüflüfters | Herstellerstecker Pin 3 | Verbindungsweg zu einem Eingang/Messgerät, Pegel, Pull-up-Beschaltung, Impulse je Umdrehung |
| Pi-Kühler/hwmon | Gehört ohne konkrete Zuordnung zum separaten Pi-Kühlsystem | Keine zulässige Ersatzdrehzahl für den ARCTIC-Prüflüfter |

Das ARCTIC-Datenblatt unterscheidet am **Lüfterstecker** Pin 1 GND, Pin 2 +12 V, Pin 3 Tacho und Pin 4 PWM. Es nennt einen Betriebsbereich 600–3000 rpm und einen Stoppbereich unter 5 % PWM. Daraus folgt kein tatsächlich gemessener RPM-Wert bei 75 % und kein beobachteter mechanischer Stillstand nach 0 %. Das betrachtete PDF spezifiziert keine Impulse je Umdrehung und keine Tacho-Pull-up-Spannung. Solche Werte werden nicht aus üblichen PC-Lüftern übernommen. [ARCTIC P12 Pro PST, Herstellerdatenblatt](https://www.arctic.de/media/2c/de/c6/1750758983/Spec_Sheet_P12_Pro_PST_EN.pdf).

Die Herstelleranleitung nennt für den **PWM-Eingang** 25 kHz als Ziel und 21–28 kHz als zulässigen Bereich. PWM-Eingangsangaben sind keine Spezifikation des separaten Tachoausgangs. [ARCTIC, DIY-Ansteuerung](https://support.arctic.de/p12-pro-pst).

Die Repositoryoptionen `--rpm-measured`/`--rpm-method` speichern bislang lediglich einen unabhängig gelieferten Messwert mit Herkunft. Es wurde kein automatischer Tacho-Erfasser gefunden. Alle zugehörigen Prüflüfter-Drehzahlen bleiben `null`.

## 4. Kleinste gezielte Messvorbereitung

### 4.1 Sensorzeitbasis: ein technischer 60-s-Versuch bei 0 % PWM

**Offene Frage:** Entsprechen die rund 207 pro Hostsekunde abgeholten XYZ-Sätze auch einer etwa 207-Hz-Datenbereitstellung gegen einen externen Zeitbezug?

Als kleinste zweckmäßige Vorbereitung eignet sich ein verfügbarer Logikanalysator oder ein Oszilloskop mit digitalem Export und dokumentierter Zeitbasisgenauigkeit. Für eine klare Zuordnung sind drei Kanäle vorgesehen: DATA_READY am erreichbaren INT1- oder INT2-Anschluss, SCL und SDA, zuzüglich gemeinsamer Masse. Die Verfügbarkeit dieser Anschlüsse am konkreten Sensormodul sowie Messgerättyp, zulässige Eingangspegel und Zeitbasisangaben sind noch mitzuteilen. Es ist kein Umbau der Sensorbefestigung und kein Lüfterstart erforderlich.

Die bereits dokumentierte I²C-Verbindung bleibt bestehen. Zusätzliche Messleitungen werden spannungsfrei angebracht und zugentlastet. Ein reiner passiver SCL/SDA-Mitschnitt ohne DATA_READY kann bereits die Buslesungen gegen eine unabhängige Uhr prüfen; er beweist alleine aber noch nicht jede Sensorwandlung.

Der vollständige technische Diagnoseversuch benötigt eine separat versionierte Instrumentierung: INT_MAP vorab sichern, DATA_READY gezielt auf den zugänglichen Interruptpin legen, nur dessen Interruptausgabe freischalten und sämtliche geänderten Register nachher wiederherstellen. Die bisherige 200-Hz-ODR, Auflösung, Messbereich und FIFO-Stream bleiben gleich. **Die Interruptausgabe wäre ausdrücklich eine dokumentierte Instrumentierungsänderung**, kein unveränderter eingefrorener Testlauf. Die entsprechende Rohaufnahme erhält das Label `technical_timebase_probe`, fließt nicht in Training, Normalvalidierung oder Modellauswertung ein und erhält ein eigenes Manifest. Die Software für diese zusätzliche Anbindung wird erst nach bestätigtem Messgerät/Anschluss konkret eingerichtet; hier wurde nichts aktiviert.

DATA_READY kann bei nicht vollständig abgeholten Werten über mehrere Perioden aktiv bleiben. Einfach alle Flanken zu zählen und jede fehlende Flanke als Verlust zu deuten wäre daher falsch. [ADXL345, DATA_READY und FIFO](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf). Vor der Auswertung wird festgelegt:

1. Alle Rohflanken und I²C-Bursts über 60 s erhalten; Analyzer-Überläufe und Geräteunsicherheit dokumentieren.
2. Erfolgreiche sechs Byte umfassende XYZ-Bursts zwischen CSV und Busmitschnitt zuordnen, Hostzeit gegen externe Zeit linear abgleichen und beide Raten separat berechnen.
3. Nur eindeutig aufgelöste DATA_READY-Zyklen mit nachgewiesener zwischenzeitlicher Rückkehr auf inaktiv zur Periodenmessung verwenden. Daueraktivität, fehlende Pulse und mehrdeutige Zuordnungen separat zählen und erhalten; keine Verlustfreiheit daraus ableiten.
4. Frequenz, Drift über Teilintervalle, Zahl eindeutig messbarer Perioden und Unsicherheit berichten. Sind die Datenbereitstellungen durch Daueraktivität nicht ausreichend getrennt, bleibt der unabhängige ODR-Nachweis offen; kein automatischer Wiederholungsstart.
5. Interpretation vorab: Übereinstimmung von externem DATA_READY-Takt und externer FIFO-Burstrate um 207 Hz würde die Sensortakterklärung stützen. Unterschiedlicher Host-/Analyzerzeitmaßstab würde den Hostzeitbezug in den Mittelpunkt stellen. Nicht zuordenbare Bursts/Statuswechsel würden eine gezielte Bus-/Lesepfadprüfung erfordern. Keine dieser Möglichkeiten wird vor der Messung als eingetreten dargestellt.

### 4.2 Drehzahl: bevorzugt zunächst berührungslos

Für den kleinsten Drehzahlnachweis eignet sich ein ausgeliehenes optisches Drehzahlmessgerät mit dokumentierter Messunsicherheit, soweit sein Messverfahren am bestehenden Lüfter ohne Veränderung der Auswuchtung und ohne Eingriff in den laufenden Rotor nutzbar ist. Gerätetyp, notwendige optische Referenz und Messort müssen bekannt sein. Ein Gerät, das eine neue Markierung an einer Rotorfläche verlangt, wird nicht ohne gesonderte Prüfung angebracht. Die bisherige Montage bleibt erhalten.

Alternativ wird der vorhandene Hersteller-Tachoanschluss verwendet. Dafür müssen **vor** einer Verbindung zum Pi Signalpegel und eventuelle Pull-up-Spannung elektrisch geprüft sein. Ein geeignetes Oszilloskop kann den tatsächlichen Pegel zunächst außerhalb eines Pi-GPIO erfassen. Ein freier Pi-Eingang wird erst nach Prüfung der realen Belegung benannt. GPIO18 bleibt PWM. Die Impulse je Umdrehung (PPR) müssen erst vor der Umrechnung in RPM aus einer passenden Herstellerbestätigung oder einer unabhängigen optischen Vergleichsmessung feststehen. Unbekannte PPR verhindern keine elektrisch korrekt vorbereitete Frequenzmessung; deren Ausgabe bleibt zunächst in Hz und RPM bleibt unbekannt. Raspberry-Pi-GPIOs arbeiten mit 3,3 V; ein unbekanntes Tachosignal wird nicht direkt angeschlossen. [Raspberry Pi, GPIO Usage](https://pip-assets.raspberrypi.com/categories/685-whitepapers-app-notes/documents/RP-006553-WP/A-history-of-GPIO-usage-on-Raspberry-Pi-devices-and-current-best-practices).

Mit bestätigten `p` Impulsen je Umdrehung gilt bei Flanken gleicher Polarität `rpm = 60 × f_tacho / p`; `p` wird nicht automatisch auf zwei gesetzt. Zählfenster, Flankenverluste, Impulsform und Umrechnungsunsicherheit werden separat berichtet.

**Minimaler anschließender Lauf:** einmal 300 s bei 75 % und 25 kHz, den ganzen Verlauf speichern und die unabhängige Drehzahl zusätzlich für [180,300) s in festgelegten 10-s-Abschnitten dokumentieren; anschließend 0 % und Rücklesung. Dieser zusätzliche Versuch liefert eine Drehzahlreferenz für seinen eigenen Lauf, keine rückwirkenden RPM-Werte der historischen Daten und keine allgemeine Drehzahlreproduzierbarkeit. Ein zweiter PWM-Punkt oder neue Defektversuche sind dafür nicht notwendig. Der Start erfolgt erst nach konkret vorbereiteter Messtechnik und der dann erforderlichen aktuellen Freigabe.

## 5. Abschlussentscheidung und Vorbereitung des Nutzers

Die Dateiauswertung und der Versuchsplan sind fertig. Die beiden Messnachweise bleiben bis zur tatsächlichen Referenzmessung offen. Der Nutzer muss als Nächstes lediglich mitteilen, ob ein **Logikanalysator/Oszilloskop mit Datenexport und ein optisches Drehzahlmessgerät** verfügbar oder aus dem Labor ausleihbar sind, jeweils mit Typbezeichnung. Sensor und Lüfter sollen bis dahin nicht neu befestigt und keine unbekannten Leitungen angeschlossen werden. Wenn nur ein Gerät verfügbar ist, wird zuerst der damit beantwortbare Teil durchgeführt; ein nicht verfügbarer Nachweis wird ausdrücklich als offen dokumentiert.

Der Aufwand hängt damit an konkreter Messtechnik statt an weiteren gleichartigen Normalstarts: ungefähr 1–3 Stunden für Import/Zeitsynchronisierung und Auswertung nach bekanntem Exportformat; 30–60 Minuten manuelle Instrumentierung; 60 s Sensorprobe ohne Lüfterstart und gegebenenfalls ein 300-s-Drehzahllauf plus dokumentierte Auszeit. Dies sind Planungsschätzungen, keine bereits erbrachte Arbeit. Es wird weder eine bestimmte Drehzahl noch eine bestandene Taktprüfung vorweggenommen.

## Digitale Bezugspunkte

Die gelesenen Quellmodule besitzen folgende SHA-256-Werte; durch diese Prüfung wurden sie nicht verändert:

- `src/adxl345.py`: `de7d7bb6df14a0a4499b843136ba9d47db6ef9e146709e827b9e40f0bcf9be84`
- `src/pilot_sensor_source.py`: `8c65868b8d160ffd4cd419b0c73151d73fca3b70dede4dc661412e4acfe7df4a`
- `src/collect_real_data.py`: `80175fcf85c2c39c7e1027f83a1e845d2262f92375a083cfcc30ad1db84e54b1`
- `src/fan_pwm.py`: `9ea26cf53849df32ca427d392bc7e8df202e4729255a24ac09a601bc0717b933`
- `runtime_analysis/analysis.json` der Abschlussmatrix: `7ace1857627cba0341f45858e2603137f851e0d073e9aa29894d2a79253d710b`

Die oben genannten Primärquellen wurden am 12.09.2026 geprüft. Alle Zahlen im Ergebnisabschnitt stammen aus bereits abgeschlossenen, verlinkten Dateien; die Messvorbereitung enthält keine neu erzeugten Hardwarewerte.
