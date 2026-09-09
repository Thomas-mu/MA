# Messkette und nächste Versuche – 09.09.2026

## Tatsächliche Plattform und Grenzen der Altaufnahmen

Die Arbeiten laufen auf `edgepi`, Raspberry Pi 5 Model B Rev 1.0, ARM64,
Debian 13, Python 3.13.5. I²C-Bus 1 ist laut seinem Device-Tree-Knoten auf
100.000 Hz konfiguriert. Das ist ein Konfigurationsnachweis, keine elektrische
SCL-Messung. Die Gerätekennung an 0x53 ist 0xE5. Beim Erstzugriff standen
BW_RATE=0x0A, POWER_CTL=0x00, DATA_FORMAT=0x00 und FIFO_CTL=0x00:
100-Hz-ODR, Standby, feste 10-Bit-Auflösung bei ±2 g, FIFO aus.
Diese Feststellung gilt für den aktuellen Zugriff und beweist nicht die
Registerwerte während früherer Aufnahmen.

Die alten Profile deklarieren 500 Softwareabfragen/s. Ihre Herkunftshinweise
benennen bereits die unkonfigurierte interne ODR. Rund 79 % unmittelbar gleiche
XYZ-Tupel und einzelne große Host-Zeitlücken verstärken den Prüfbedarf.
Gleiche quantisierte Tupel können dennoch verschiedene Sensormessungen sein;
die Wiederholungsquote ist weder ein Frischwerttest noch eine exakte ODR-Messung.
Altaufnahmen und Modelle bleiben unverändert und wissenschaftlich explorativ.

## Neue Erfassung

`src/adxl345.py` setzt und liest BW_RATE, DATA_FORMAT, FIFO_CTL, POWER_CTL
und INT_ENABLE zurück. Standard ist 200 Hz, Full Resolution, ±2 g,
FIFO-Stream mit 32 Plätzen. 500 Hz ist keine verfügbare ADXL345-ODR und wird
abgelehnt. Eine höhere ODR als nach der konfigurierten I²C-Geschwindigkeit
zulässig wird vor dem Öffnen der Messung abgewiesen. Bei unbekannter Busfrequenz
gilt konservativ höchstens 200 Hz. Die bestehenden Hardware-/Bootparameter
wurden nicht verändert.

Vor jedem XYZ-Burst wird der FIFO-Füllstand geprüft. Nur bei mindestens einem
Eintrag wird gelesen. INT_SOURCE wird vor dem Datenlesen auf Overrun geprüft.
Voller FIFO und eine Lesepause über seiner Zeitkapazität markieren
Verlustverdacht; die exakte Zahl verlorener Sensorwerte bleibt unbekannt.
Sättigung wird konservativ an den digitalen Bereichsgrenzen einschließlich
eines kleinen Randes erkannt. Ein Prozess-Lock verhindert gleichzeitige
Zugriffe durch die neuen Erfassungsprogramme. Andere, fremde I²C-Programme
beachten diesen Lock nicht automatisch.

Die Aufnahmegrenze verwirft bewusst noch nicht aufgezeichnete Vorlaufwerte:
Standby, FIFO leeren, alte Statusflags durch Datenlesen löschen, Stream/Messung
wieder einschalten. Danach zählen alle gelesenen Werte. Beim geordneten
Schließen werden die vorherigen Konfigurationsregister restauriert.

Die Implementierung folgt dem [ADXL345-Datenblatt, insbesondere I²C,
FIFO und Registerbeschreibung](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf)
und der [FIFO-Anwendungsschrift AN-1025](https://www.analog.com/en/resources/app-notes/an-1025.html).
Die Auswahl von 200 Hz ist eine technische Piloteinstellung; die ausreichende
Nutzbandbreite am Prüfstand ist dadurch noch nicht nachgewiesen.

## Zeitachsen und Rohdaten

`host_monotonic_ns` ist der Zeitpunkt nach dem abgeschlossenen Datenburst;
`timestamp_s` ist dessen relative Hostzeit. Der Sensor liefert selbst keinen
Zeitstempel je FIFO-Wert. `sensor_time_estimate_s = sample_index / ODR` ist
ausdrücklich eine nominelle Schätzung. FIFO-Rückstände führen zu ungleichmäßigen
Host-Leseintervallen, auch bei regelmäßiger Sensorwandlung. Es erfolgt kein
stilles Resampling auf 500 Hz und kein Ersetzen der gemessenen Hostzeitachse.

`collect_real_data.py` schreibt CSV und ein JSON-Begleitprotokoll mit Laufkennung,
Konfiguration, Zustandslabel, Montage, Quellcodehashes, Python-Paketen,
CSV-Hash, Abschlussstatus und Qualitätsstatistik. CSV-Dateien werden exklusiv
neu angelegt. SIGINT, SIGTERM und I²C-Fehler erhalten bereits gelesene Werte;
Teilfenster bleiben enthalten. Geordneter Abschluss führt Flush/fsync aus.
Stromausfall oder SIGKILL sind damit nicht als verlustfrei nachgewiesen.

PWM-Vorgabe und Drehzahl sind getrennte Felder. `--fan-pwm-setpoint` dokumentiert
eine externe Vorgabe und steuert keinen Ausgang. `--rpm-measured` benötigt eine
angegebene Messmethode; diese Zahl wird vom Bediener geliefert. Ein Tachoeingang
ist im Repository bisher nicht nachgewiesen. Unbekannte Drehzahl bleibt `null`.
Ein PWM-Tastgrad darf nie als gemessene Drehzahl ausgegeben werden.

## Durchgeführte technische Prüfungen

Die Belege liegen unter `results/verification_20260909/`:

| Prüfung | Tatsächlicher Befund | Aussagegrenze |
|---|---|---|
| 15 s FIFO, ODR 200 Hz | 3.098 Werte; Host-Durchsatz 206,4913/s; maximal zwei FIFO-Werte | Prüfstandzustand unbestätigt, kein Normaldatensatz |
| Zeitfolge dieser Probe | monotone Hostzeiten; P99 Hostintervall 5,8038 ms; Maximum 10,3793 ms | Hostintervalle sind nicht Sensorwandlungsintervalle |
| Qualitätsflags dieser Probe | 0 Overrun-, 0 Gap-, 0 Sättigungsflags | keine Behauptung exakt null physikalischer Verluste |
| Absichtliche 250-ms-Lesepause | FIFO-Überlauf erkannt | technischer Fehlerfall, keine mechanische Anomalie |
| Vorlauf länger als FIFO-Kapazität, danach Reset | erster neuer Wert ohne alten Überlaufstatus | technische Startgrenze bestätigt |
| SIGTERM an laufende Erfassung | Teilaufnahme samt JSON `interrupted` erhalten | kein Stromausfalltest |
| Schließen nach den Fehlerproben | Originalregister wiederhergestellt | nur geprüfte Register und dieser Lauf |

Die Rate von 206,49/s wird nicht zu 200/s umbenannt. Sie beschreibt den
beobachteten FIFO-Durchsatz; eine unabhängige Prüfung des Sensortaktes fehlt.

Technische Prüfungen ohne Aktoransteuerung reproduzieren:

```bash
.venv/bin/python -m pytest -q tests/test_acquisition.py tests/test_fft_pilot.py
.venv/bin/python tests/manual_sensor_checks.py --output results/NEUER_hardwarecheck
.venv/bin/python src/collect_real_data.py --seconds 15 --odr 200 --label unknown --state technical_probe_unconfirmed --purpose pilot --output results/NEUE_sensorprobe.csv
```

## FFT-Pilot

`src/fft_pilot.py` nutzt den vorhandenen Mittelwert-/rfft-Ansatz aus
`preprocessing.calculate_features` als Ausgangspunkt. Es ergänzt dreiachsige
Analyse, Qualitätsprüfung, Hann-Fenster, einseitige Amplituden- und PSD-Skalierung,
getrennte Metadaten und eine exportierbare Grafik. Es akzeptiert nur vollständig
abgeschlossene und ausdrücklich als `pilot` deklarierte FIFO-Aufnahmen mit
passendem CSV-Hash und ohne markierte Lücken, Überlauf oder Sättigung.

```bash
.venv/bin/python src/fft_pilot.py --input results/verification_20260909/sensor_fifo_200hz_probe.csv --output results/NEUE_fft_analyse --segment-samples 512
```

Die erste Analyse liegt unter `results/verification_20260909/fft_probe/`.
Sie verwendet 512 Samples, 50 % Überlappung, symmetrisches Hann und
Mittelwertentfernung je Segment. Mit der gemessenen Durchsatzschätzung ergeben
sich ca. 2,480 s Segmentdauer und 0,4033 Hz Abstand der Frequenzstützstellen.
Das ist keine Aussage über tatsächliche spektrale Trennschärfe.
Die Frequenzachse setzt eine zusammenhängende FIFO-Folge und hinreichend stabilen
Sensortakt voraus. Host-Lesezeiten werden nicht als gleichmäßig behauptet.
Es werden weder Drehzahl noch Fehlerursache aus Spektralspitzen abgeleitet.
SNR bleibt mangels kontrollierter Referenzmessung `null`; Aliasingfreiheit
und ausreichendes Nutzband sind weiterhin offen.

## Kontrollierte Pilotfolge – nächster notwendiger Eingriff

Die technische Arbeit erfordert zunächst diese Rückmeldung am Prüfstand:

1. Lüfter ausschalten und vollständigen Stillstand abwarten. Sensorbefestigung
   und Montage unverändert lassen, während der Messung nicht berühren.
2. Stillstand bestätigen und Befestigung/Montage beschreiben.
3. Mitteilen, ob das Drehzahlsignal angeschlossen ist, an welchem GPIO und mit
   welcher Beschaltung. Ohne diesen Nachweis bleibt Drehzahl ungemessen.

Erst nach dieser Bestätigung wird eine neue Stillstandsreferenz aufgenommen.
Anschließend folgen separat bestätigte normale Betriebspunkte mit dokumentierter
PWM und Drehzahl. Der Zustand wird zwischen Aufnahmen hergestellt und bestätigt;
die unbekannte technische Probe wird nicht nachträglich als Stillstand gelabelt.

Für die Pilotfolge werden vor der abschließenden Testserie folgende Kriterien
festgelegt und im Versuchsprotokoll eingefroren: betrachtetes Frequenzband,
SNR-Definition und Mindestwert, zulässige Ratenschwankung/Hostlücken,
Sättigungsausschluss, Montage, Aufnahmedauer, H/S und Anzahl unabhängiger Läufe.
Lücken, Überlauf und Sättigung werden in der neuen Kalibrierung bereits
konservativ abgewiesen. Die übrigen Grenzen sind noch offen und dürfen nicht
anhand späterer Testgüte gewählt werden. Bei unzureichender Bandbreite ist
zunächst die bestehende Messkette zu prüfen; zusätzliche Sensoren/Plattformen
sind derzeit nicht eingeführt.

## Abschließende Versuche vorbereiten

Der Kernvergleich wird nach Abschluss der Pilotparameterwahl eingefroren:
neues Profil aus ganzen normalen Trainings- und getrennten normalen
Validierungsaufnahmen; identische XYZ-Fenster; trainingsbasierter Scaler;
RMS über die standardisierten 3H Werte, flacher IF-Eingang und Float32-TFLite-AE.
P99 verwendet die lineare empirische Quantilsregel. Keine manuelle Schwelle,
keine erkennungsgesteuerte Abschaltung während vergleichbarer Aufnahmen.

Vorbereiteter Plan (Entwurf, noch kein durchgeführter Versuch):

| Rolle | Vorgesehene Aufnahmen | Label/Zustand |
|---|---|---|
| Training N0 | sechs eigenständige Normalaufnahmen | `normal_reference`, 0 |
| Validierung N0 | zwei weitere Normalaufnahmen | `normal_reference`, 0 |
| Unabhängiger Test N0 | mindestens drei neue Aufnahmen | `normal_reference`, 0 |
| Unabhängiger Test N1 | mindestens drei neue Aufnahmen bei zweiter PWM, identische Montage | `normal_second_operating_point`, 0 |
| Unabhängiger Anomalietest | mindestens drei neue Aufnahmen je vorab definierter, rücksetzbarer Anomalie | konkreter Zustandsname, 1 |

Dauer und konkrete Anomaliezustände werden nach der Pilotprüfung festgelegt.
Der Entwurf autorisiert keine improvisierte Veränderung am rotierenden Lüfter.
Die neue Testserie wird erst nach bestätigtem Aufbau und festgelegtem Protokoll
begonnen. Nach Zustandsübergängen wird eine festgelegte Einschwingzeit verworfen,
danach beginnt eine neue Datei. Physischer Zustand gilt für die gesamte Datei.
Zur Kontrolle von Zeitdrift soll N0 nach N1 erneut aufgenommen werden.

Für N1 bleiben dasselbe Bundle, Modell, Scaler und alle drei P99-Schwellen wie
bei N0 erhalten. `fan_25` und `fan_50` sind separat trainierte Bestandsprofile
und ersetzen diesen Versuch nicht. Testdaten werden nicht in Training,
Parameterwahl, Bandwahl oder Schwellenkalibrierung zurückgeführt.
Kennzahlen werden pro Aufnahme und Zustand sowie gemeinsam ausgegeben;
aufeinanderfolgende Fenster zählen nicht als unabhängige Versuchsreplikate.
H1 und H3 sind bis zu dieser Serie unbestätigt. Ein Ressourcen-Replay oder ein
kurzer Live-Pilot bestätigt H2/A7 und Langzeitstabilität A8 nicht abschließend.
