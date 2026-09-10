# Stillstand, 25 % und 50 % PWM: neue Pilotmessungen vom 10.09.2026

**Die angeforderte Messfolge ist abgeschlossen.** Die zweite Stillstandsaufnahme und zwei getrennte Betriebsaufnahmen bei 50 % PWM wurden auf dem Raspberry Pi `edgepi` erstellt. Anschließend wurde die Vorgabe auf **0 % bei 25 kHz** gestellt und zurückgelesen. Ein vollständiger mechanischer Stillstand nach dieser letzten Abschaltung ist nicht bestätigt. Es wurde kein neues Modell trainiert.

## Durchführung und Zuordnung

Beim Einstieg lag nur die erste kontrollierte Stillstandsaufnahme S0 vom Vortag vor. GPIO18 war als Digitalausgang Low konfiguriert, während im PWM-Subsystem 25 % gespeichert waren. Der Agent kündigte die Wiederherstellung an und setzte über `FanPWM.stop()` zuerst die Tastzeit auf null und GPIO18 wieder auf die Hardware-PWM-Funktion `a3/PWM0_CHAN2`. GPIO18 ist BCM18 beziehungsweise physischer Pin 12. Die gespeicherte alte Vorgabe wurde nicht als ausgegebenes Signal behandelt.

Der Nutzer bestätigte anschließend vollständigen Stillstand; die Montage blieb nach Nutzerangabe unverändert. S1 wurde bei 0 % erfasst. Danach stellte der Agent 50 % bei 25 kHz ein und wartete mindestens 30 s. Die Betriebsaufnahme begann erst nach der Nutzerbeobachtung eines sichtbar gleichmäßigen Laufs. Wegen der Wartezeit auf diese Bestätigung betrug die tatsächliche Zeit seit dem Einstellen der 50 % vor der ersten Aufnahme **1205,848 s**. Das ist eine protokollierte Wartezeit und kein gemessener Verlauf einer Drehzahlstabilisierung.

| Aufnahme | Beginn, Europe/Berlin | PWM | XYZ-Messpunkte | Einzelne Achsenwerte | Beobachteter Durchsatz / s | Vektor-AC-RMS / g |
|---|---|---:|---:|---:|---:|---:|
| S0 | 09.09.2026 22:08:39 | 0 % | 6193 | 18579 | 206,479669 | 0,012371 |
| S1 | 10.09.2026 09:03:28 | 0 % | 6201 | 18603 | 206,749042 | 0,012711 |
| B25_1 | 09.09.2026 22:24:35 | 25 % | 6205 | 18615 | 206,846521 | 0,013099 |
| B25_2 | 09.09.2026 22:32:10 | 25 % | 6205 | 18615 | 206,862884 | 0,012954 |
| B50_1 | 10.09.2026 09:24:26 | 50 % | 6207 | 18621 | 206,952481 | 0,014416 |
| B50_2 | 10.09.2026 09:25:23 | 50 % | 6207 | 18621 | 206,942340 | 0,014680 |

Alle Aufnahmen hatten eine vorgesehene Erfassungsdauer von 30 s. Die tatsächlichen Zeitstempel, Rohdatenpfade, CSV-/Sidecar-Prüfsummen, vollständigen Sensorparameter und Qualitätszusammenfassungen stehen in `report.json` und `recording_metrics.csv`. Die neuen Rohdateien sind:

- `data/controlled_20260910/standstill_post_operation_20260910_070328.csv` mit gleichnamigem JSON-Begleitprotokoll.
- `data/controlled_20260910/operating50_first_20260910_072426.csv` mit gleichnamigem JSON-Begleitprotokoll.
- `data/controlled_20260910/operating50_second_20260910_072523.csv` mit gleichnamigem JSON-Begleitprotokoll.

Die beiden 50-%-Dateien sind getrennte Erfassungen mit neu gesetzter FIFO-Aufnahmegrenze. Der Lüfter lief dazwischen bei unveränderten 50 % weiter; die Messungen sind daher keine unabhängigen Neustartversuche. Es lief jeweils nur eine Sensorerfassung; die Steuerung hielt über die gesamte Folge die gemeinsame Prozesssperre. Vor und nach jeder Aufnahme wurden Tastgrad, aktivierter PWM-Kanal und Pinfunktion geprüft. Es gab keine erkennungsabhängige Regelung und keine Änderung der Montage. Die Rückstellung auf 0 % ist für **10.09.2026 09:25:53 Uhr** dokumentiert. Befehle und Rücklesungen: `results/pwm50_investigation_20260910/measurement_sequence_20260910_070328_fan.jsonl`.

## Erfassungsqualität und Abtastrate

Die identische Konfiguration wurde in allen sechs Aufnahmen bestätigt: nominell 200 Hz ODR, Full Resolution, ±2 g, FIFO-Stream, Register BW_RATE = 0x0B und konfigurierte I²C-Taktrate 100 kHz. Die CSV-Prüfsummen stimmen; XYZ-Werte und Zeitstempel sind endlich, Indizes fortlaufend und Qualitätsflags ausdrücklich ausgewertet. In allen sechs Dateien sind **null Gap-, Overrun- und Sättigungsflags** gesetzt, der größte beobachtete FIFO-Füllstand beträgt einen Eintrag. Die größten Hostintervalle betragen in den neuen Aufnahmen S1/B50_1/B50_2 6,509/5,959/6,138 ms. Das sind positive technische Befunde, keine Garantie für exakt null physikalisch verlorene Werte oder Aliasfreiheit.

Eine Zeile enthält einen vollständigen XYZ-Messpunkt: ein FIFO-Eintrag wird als sechs Bytes gelesen und in drei vorzeichenbehaftete 16-Bit-Achsenwerte umgewandelt. **6.205 Zeilen sind 6.205 XYZ-Messpunkte beziehungsweise 18.615 einzelne Achsenwerte.** Jede Achse hat denselben zeitlichen Durchsatz; die drei Achsen verdreifachen nicht die Abtastrate.

Der beobachtete Durchsatz wird mit `f = (N−1) / (t_letzter−t_erster)` aus den ganzzahlig gelesenen monotonen Hostzeitstempeln berechnet. Die relative CSV-Zeitspalte liefert denselben Wert. Eine Ausgleichsgerade über alle Sampleindizes und Hostzeiten bestätigt die Größenordnung unabhängig von der Wahl der beiden Endpunkte. Beide Zeitspalten beruhen allerdings auf derselben Hostuhr; dies ersetzt keine unabhängige Zeitmessung am Sensor.

| Aufnahme | Zeit erster bis letzter Punkt / s | Durchsatz aus Endpunkten / s | Durchsatz aus Ausgleichsgerade / s | Abweichung von 200 Hz |
|---|---:|---:|---:|---:|
| S0 | 29,988424624 | 206,479669 | 206,481212 | +3,240 % |
| S1 | 29,988047104 | 206,749042 | 206,746816 | +3,375 % |
| B25_1 | 29,993252892 | 206,846521 | 206,855290 | +3,423 % |
| B25_2 | 29,990880366 | 206,862884 | 206,867459 | +3,431 % |
| B50_1 | 29,987560223 | 206,952481 | 206,951011 | +3,476 % |
| B50_2 | 29,989029800 | 206,942340 | 206,954170 | +3,471 % |

Bei exakt 200 XYZ-Messpunkten/s wären über 30 s ungefähr 6.000 Messpunkte zu erwarten. Die 6.205 Punkte der beiden 25-%-Aufnahmen entsprechen tatsächlich rund 206,85 beziehungsweise 206,86 Punkten/s: Die Registervorgabe ist 200 Hz, der beobachtete Durchsatz liegt etwa 3,4 % darüber. **Die Daten sind deshalb kein Nachweis einer exakt eingehaltenen 200-Hz-Zeitbasis.**

`collect_real_data.record` beendet die Erfassung anhand verstrichener monotoner Zeit. Es gibt weder eine feste Grenze von 6.205 Zeilen noch ein Auffüllen oder Beschneiden auf 6.000. Der letzte blockierende Frischwertabruf kann geringfügig über 30 s hinausreichen; diese wenigen Millisekunden erklären keine rund 205 zusätzlichen Messpunkte. Dass beide Wiederholungen dieselbe ganzzahlige Anzahl enthalten, passt zu nahezu gleichem Durchsatz und gleicher Dauer. Ihre Zeitabstände und CSV-Hashes unterscheiden sich. Auch bei 50 % sind beide Zählwerte gleich, diesmal 6.207, bei geringfügig verschiedenen beobachteten Raten.

Die Spalte `sensor_time_estimate_s` ist ausschließlich `sample_index/200`. Ihr letzter Wert beträgt bei den 6.205-Punkte-Dateien 31,02 s, obwohl die reale Erfassung rund 30 s dauerte. Sie darf daher nicht zur unabhängigen Bestätigung der Rate oder als gemessene Sensorzeit verwendet werden. Die bisherigen Rohdaten werden nicht nachträglich zeitlich umgeschrieben.

Analog Devices beschreibt einen internen RC-Takt des ADXL345 und nennt dafür eine Genauigkeit von ±10 % einschließlich Temperatur- und Zeitdrift. Damit ist die hier beobachtete Abweichung vereinbar. Das ist eine **plausible Erklärung**, keine unabhängig nachgewiesene Ursache an diesem konkreten Sensor. Der Hersteller empfiehlt für eine genauere Prüfung die Zeitmessung des DATA_READY-Signals. Grundlage ist die Antwort eines ADI-Mitarbeiters, nicht die automatisch erzeugte Zusammenfassung der Seite: [Analog Devices, ChrisM, 07.01.2022](https://ez.analog.com/condition-based-monitoring/f/q-a/553781/adxl345---number-of-samples-for-odr---3200). Register, FIFO-Verhalten und Schnittstellengrenzen sind im [ADXL345-Datenblatt Rev. G](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf) beschrieben.

Für die Pilotfrequenzachse wird der beobachtete Durchsatz genutzt und als Schätzung gekennzeichnet. H = 128 Punkte würden unter diesen Bedingungen etwa 0,619 s umfassen; 0,640 s ergibt sich nur aus der nominellen 200-Hz-Vorgabe. Es wurde keine Sensoreinstellung geändert, um die Messpunktezahl nachträglich passend zu machen.

## Mittelwert, Streuung und RMS ohne Gleichanteil

Für jede Achse wird ihr eigener Mittelwert über die jeweilige Aufnahme abgezogen. Die anschließend berechnete quadratische Mittelwertwurzel ist bei der verwendeten Normierung `ddof=0` identisch mit der Standardabweichung dieser Achse. Der Vektor-AC-RMS ist `sqrt(mean((x−μx)²+(y−μy)²+(z−μz)²)) = sqrt(σx²+σy²+σz²)`. Er ist nicht die Standardabweichung des Beschleunigungsbetrags und wird nicht durch √3 geteilt. Die Spalte `magnitude_ac_rms_g` dokumentiert letztere abweichende Betragsauswertung separat.

| Aufnahme | Mittel X / g | Mittel Y / g | Mittel Z / g | σX = AC-RMS X / g | σY = AC-RMS Y / g | σZ = AC-RMS Z / g |
|---|---:|---:|---:|---:|---:|---:|
| S0 | -0,152954 | 0,006333 | -1,090168 | 0,006465 | 0,005462 | 0,009024 |
| S1 | -0,153592 | 0,014099 | -1,091863 | 0,006495 | 0,005810 | 0,009254 |
| B25_1 | -0,154055 | 0,007122 | -1,089077 | 0,006860 | 0,005926 | 0,009455 |
| B25_2 | -0,154444 | 0,007158 | -1,088556 | 0,006906 | 0,005788 | 0,009307 |
| B50_1 | -0,154572 | 0,015246 | -1,091242 | 0,008406 | 0,006642 | 0,009646 |
| B50_2 | -0,154662 | 0,015286 | -1,091223 | 0,008547 | 0,006748 | 0,009844 |

Der Y-Mittelwert der Stillstandsreferenzen ändert sich von 0,006333 auf 0,014099 g. Diese Änderung zwischen Tagen ist wesentlich größer als die Y-Mittelwertänderung zwischen der heutigen Stillstandsreferenz und 50 %. Die Gleichanteile sind deshalb nicht als Schwingungsstärke zu interpretieren. Aus den Mittelwerten werden weder eine Montageänderung entgegen der Nutzerangabe noch eine bestimmte thermische Ursache abgeleitet. Eine absolute Sensorkalibrierung wurde nicht durchgeführt.

## Zustandsunterschiede gegenüber Wiederholungsstreuung

Jede Aufnahme erhält für diesen Vergleich dasselbe Gewicht. Als beobachtete Wiederholungsdifferenz dient der absolute Unterschied der zwei vollständigen 30-s-RMS-Werte je Zustand. Dies ist bei zwei Aufnahmen eine deskriptive Größe, keine verlässlich geschätzte Populationsstreuung oder Signifikanzprüfung. Die beiden Stillstandsaufnahmen liegen zudem an verschiedenen Tagen.

| Zustand | Mittlerer Vektor-AC-RMS / g | Unterschied der zwei Wiederholungen / g | Bereich aller 5-s-Abschnitte / g |
|---|---:|---:|---:|
| Stillstand | 0,012541 | 0,000340 | 0,011902–0,012959 |
| 25 % | 0,013026 | 0,000145 | 0,012404–0,013991 |
| 50 % | 0,014548 | 0,000264 | 0,014067–0,015316 |

| Vergleich | Abstand der Zustandsmittel / g | Größte zugehörige Wiederholungsdifferenz / g | Verhältnis Abstand/Differenz |
|---|---:|---:|---:|
| Stillstand → 25 % | 0,000485 | 0,000340 | 1,43 |
| Stillstand → 50 % | 0,002006 | 0,000340 | 5,90 |
| 25 % → 50 % | 0,001521 | 0,000264 | 5,77 |

Bei 50 % ist der mittlere RMS-Abstand zum Stillstand etwa 5,90-mal so groß wie die größte zugehörige Wiederholungsdifferenz. Gegenüber 25 % beträgt dieser Faktor 5,77. Damit sind die Zustandsunterschiede in dieser Messfolge größer als die Unterschiede zwischen den vollständigen Wiederholungsaufnahmen. Die größte Zunahme der Achsenstreuung zeigt sich auf X.

Bei 25 % beträgt der Faktor gegenüber den zusammengefassten Stillstandsreferenzen nur 1,43. Die 5-s-Bereiche überlappen deutlich. Gegenüber der heutigen Referenz allein beträgt der mittlere 25-%-Abstand nur rund 0,000315 g, weniger als die Differenz zwischen den zwei Stillstandsreferenzen von rund 0,000340 g. Die Aussage über 25 % bleibt daher wesentlich schwächer.

Für die 5-s-Abschnitte wird in jedem Abschnitt dessen eigener Achsenmittelwert entfernt. Die beobachteten Bereiche bei 50 % überlappen hier weder mit den Stillstands- noch mit den 25-%-Abschnitten. Der kleinste Abstand zwischen 50-%- und 25-%-Abschnitten beträgt jedoch nur rund 0,000075 g. Die Abschnitte sind zeitlich abhängig und ersetzen keine unabhängigen Versuchsreplikate. Auch bei unveränderter PWM schwankt die Schwingungsamplitude innerhalb einer Aufnahme; eine feste Vorgabe beweist keine exakt konstante Drehzahl.

## Eignung und empfohlener nächster Schritt

**Die Messgrundlage ist für weitere kontrollierte Pilotversuche geeignet; bei 50 % ist eine klarere Schwingungszunahme innerhalb dieser Messfolge belegt.** Die Erfassung ist technisch unauffällig, die Rate wurde anhand der Hostzeit überprüft und die RMS-Zunahme wiederholt sich in zwei Dateien. Ein universell ausreichendes Nutzband, unabhängige Langzeitstabilität und die Eignung konkreter Anomaliezustände sind damit nicht nachgewiesen. Eine bessere Trennung zwischen Stillstand und normalem Betrieb ist ausdrücklich **kein Nachweis erfolgreicher Anomalieerkennung**.

Als nächstes empfiehlt sich eine zeitlich eng zusammenliegende Kontrollfolge mit Stillstand, 25 %, 50 % und abschließendem Stillstand bei unveränderter Montage. Die Betriebszustände sollten in mehreren getrennt hergestellten Wiederholungen und vorab festgelegter Reihenfolge geprüft werden, damit Zustandswechsel und zeitliche Hintergrundänderung besser getrennt werden können. Der zweite normale Betriebspunkt bleibt später ein Test mit identischen Modellen, identischer Skalierung und unveränderten Schwellen; diese Piloten sind kein zweites separat zu trainierendes Profil.

Vor Modelltraining sind anschließend konkret definierte, reproduzierbare Anomaliepiloten erforderlich, um deren Signalabstand, Datenqualität und Sättigungsreserve zu prüfen. Eine Änderung der ODR ist aus der abweichenden Messpunktezahl allein nicht begründet. Falls genaue absolute Frequenzzuordnungen benötigt werden, ist eine unabhängige Prüfung der Sensorzeitbasis zweckmäßig. Es wurde in diesem Auftrag kein Hardwareumbau verlangt oder durchgeführt.

## Belege und Erhalt bestehender Dateien

Neue Dateien liegen ausschließlich unter `data/controlled_20260910/` und `results/pwm50_investigation_20260910/`. Die Worddatei und die 582 beim Einstieg gehashten bestehenden Dateien werden am Abschluss erneut auf Unverändertheit geprüft; der abschließende Nachweis liegt in `../final_verification.json`. Der Messablauf ist durch `../run_measurements.py`, das Sitzungsjournal und das Fan-Journal nachvollziehbar. Die Analyse ist mit `../analyze_conditions.py` dokumentiert und verwendet ausschließlich lesenden Zugriff auf Rohdaten.

`recording_metrics.csv` enthält die Aufnahmegrößen, `five_second_metrics.csv` die Abschnittsdiagnostik und `state_contrasts.csv` die Zustandsvergleiche. `comparison.png` und `comparison.pdf` zeigen RMS und Zeitbasis. `spectra.csv` enthält ergänzende 512-Punkte-Hann-Spektren mit Schritt 256 und achsenweiser Mittelwertentfernung je Segment. Daraus wird hier keine Drehzahl oder neue Modellrepräsentation abgeleitet.
